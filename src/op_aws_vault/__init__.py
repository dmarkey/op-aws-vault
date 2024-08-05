#!env python3
import webbrowser

import requests
import typer
from typing import Annotated
import os
from urllib.parse import urlencode
from typing import List, Optional
import boto3
import subprocess
import json
import platform
from pytimeparse2 import parse

from botocore.exceptions import ClientError

ONEPASSWORD_CLI = "op"

if os.name == "nt" or "WSL2" in platform.uname().release:
    ONEPASSWORD_CLI = "op.exe"

if os.name == "nt":
    DEFAULT_SHELL = "cmd.exe"
else:
    DEFAULT_SHELL = os.environ['SHELL']


def get_aws_context(config, role, duration, region):
    if region is None:
        region = config['credentials']['region']
    session = boto3.Session(aws_access_key_id=config['credentials']["aws_access_key_id"],
                            aws_secret_access_key=config['credentials']['aws_secret_access_key'], region_name=region)
    kwargs = {"DurationSeconds": duration}
    if config['credentials']["mfa_serial"]:
        kwargs['SerialNumber'] = config['credentials']["mfa_serial"]
        kwargs['TokenCode'] = config['credentials']['totp']

    try:

        sts = session.client("sts")

        if role == "default":
            response = sts.get_session_token(**kwargs)
            return response['Credentials']
        else:
            if role not in config['roles']:
                raise typer.BadParameter(f"Role {role} doesn't exist in 1Password")
            kwargs['RoleArn'] = config['roles'][role]
            kwargs['RoleSessionName'] = "op-aws-vault"
            response = sts.assume_role(**kwargs)
            return response['Credentials']
    except ClientError as e:
        raise Exception(
            f"Error communicating with AWS, "
            f"please check your credentials and or OTP.({e.response['Error']['Message']})")


app = typer.Typer(pretty_exceptions_show_locals=False)


def duration_callback(time):
    try:
        return int(time)
    except ValueError:
        pass

    parsed_time = parse(time)

    if not parsed_time:
        raise typer.BadParameter("Invalid time parameter.")

    return parsed_time


def tag_callback(tag: str):
    if ":" in tag:
        vault = tag.split(":")[0]
        tag = tag[len(vault) + 1:]
        args = [ONEPASSWORD_CLI, "item", "list", "--tags", tag, "--format=json", "--vault", vault]
    else:
        args = [ONEPASSWORD_CLI, "item", "list", "--tags", tag, "--format=json"]
    try:
        resp = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        raise Exception("Error communicating with 1Password, ensure the"
                        " `op` utility is installed and desktop app is open.")
    items = json.loads(resp)
    if len(items) == 0:
        raise typer.BadParameter(f"Can't find {tag} tagged item in 1Password")
    if len(items) > 1:
        raise typer.BadParameter(f"More than 1 item returned from 1Password for {tag}")
    try:
        values = json.loads(
            subprocess.check_output([ONEPASSWORD_CLI, "item", "get", items[0]['id'], "--format", "json"]))
        indexed = {x['label']: x for x in values['fields']}
        mfa_serial = totp = None
        if "mfa serial" in indexed:
            mfa_serial = indexed['mfa serial']['value']
            totp = indexed['one-time password']['totp']
        region = "us-east-1"
        if "default-region" in indexed:
            region = indexed["default-region"]["value"]

        roles = {i['label'][5:]: i['value'] for i in indexed.values() if i['label'].startswith('role-')}
        return {"credentials": {"aws_access_key_id": indexed['access key id']['value'],
                                "aws_secret_access_key": indexed['secret access key']['value'],
                                "mfa_serial": mfa_serial,
                                "totp": totp,
                                "region": region
                                },
                "roles": roles}
    except KeyError as e:
        raise typer.BadParameter(f"1Password item tagged {tag} missing item '{e.args[0]}'")


@app.command("exec")
def _exec(role: str, command: Annotated[List[str], typer.Argument()] = None,
          region: str = None,
          tag: Annotated[Optional[str], typer.Option(callback=tag_callback)] = "aws-credentials",
          duration: Annotated[str, typer.Option(callback=duration_callback)] = "1h"
          ):
    if not command:
        command = [DEFAULT_SHELL]
    credentials = get_aws_context(tag, role, duration, region)
    os.environ['AWS_ACCESS_KEY_ID'] = credentials['AccessKeyId']
    os.environ['AWS_SECRET_ACCESS_KEY'] = credentials['SecretAccessKey']
    os.environ['AWS_SESSION_TOKEN'] = credentials['SessionToken']
    os.environ['AWS_DEFAULT_REGION'] = region if region else tag['credentials']['region']
    os.environ.pop("AWS_CREDENTIAL_EXPIRATION", None)
    subprocess.run(command)


@app.command("login")
def login(role: str, tag: Annotated[Optional[str], typer.Option(callback=tag_callback)] = "aws-credentials",
          region: str = None,
          stdout: bool = False,
          duration: Annotated[str, typer.Option(callback=duration_callback)] = "1h"
          ):
    credentials = get_aws_context(tag, role, duration, region)
    session_data = {
        "sessionId": credentials["AccessKeyId"],
        "sessionKey": credentials["SecretAccessKey"],
        "sessionToken": credentials["SessionToken"],
    }
    aws_federated_signin_endpoint = "https://signin.aws.amazon.com/federation"

    # Make a request to the AWS federation endpoint to get a sign-in token.
    # The requests.get function URL-encodes the parameters and builds the query string
    # before making the request.
    response = requests.get(
        aws_federated_signin_endpoint,
        params={
            "Action": "getSigninToken",
            "SessionDuration": duration,
            "Session": json.dumps(session_data),
        },
    )
    signin_token = json.loads(response.text)
    region = region if region else tag['credentials']['region']
    # Make a federated URL that can be used to sign into the AWS Management Console.
    query_string = urlencode(
        {
            "Action": "login",
            "Issuer": "op-aws-vault",
            "Destination": f"https://{region}.console.aws.amazon.com/",
            "SigninToken": signin_token["SigninToken"],

        }
    )
    federated_url = f"{aws_federated_signin_endpoint}?{query_string}"
    if stdout:
        print(federated_url)
    else:
        webbrowser.open_new(federated_url)


def main_cli():
    app()
