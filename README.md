# op-aws-vault

A aws-vault like utility built completely on 1Password.

## What is it?

Irritated by no aws-vault 1Password integration and finding 1Password AWS plugin a bit buggy, this was an itch I wanted to scratch.

It's a small python script/utility that emulates the behaviour of `aws-vault` but completely integrated in 1Password. It wraps around the 1Password CLI.

It requires a 1Password account and 1Password CLI. It's tested on MacOS and Linux. Probably doesnt work on Windows.

It uses your AWS credentials and OTP key as a means to accomplish the following:

* Exec into a shell with a (MFA'd) session of any role you can assume
* Login to the AWS console via Federation


It requires no on-disk configuration, all configuration is set up in 1Password, including roles to assume, AWS creds and One-Time-Password.

This means if you interact with AWS on different computers, you only need to set this up once in 1Password, no config setup, no key imports.


## How to install

Create Python Virtual Environment and `pip install op-aws-vault`

You need to have the 1Password CLI and GUI open and unlocked for it to work.

You may want to disable the 1Password aws plugin (`unalias aws`) as I find it interferes.
## Setup

You need to set up a 1Password item with the following attribute names (exactly):

* `access key id`(AWS Key ID)
* `secret access key` (AWS Secret Key)
* `mfa serial` (MFA Serial ARN - Optional with MFA - Recommended!)
* `one-time password` (TOTP Required for MFA)
* `default-region` (Default Region)

To assume roles you need to add text attributes with the ARNs of roles to assume with a `role-{role name}` pattern.

For example if you have a `dev` role, you would add a text attribute to 1Password item called `role-dev` and make the value the ARN of the role.

You can add as many roles as you wish.

Finally, you need to tag the item as `aws-credentials` - this allows `op-aws-vault` to find it.

## Usage

Each command requires a `role` as the first positional argument.

It can be any of the `role-{name}` roles in your 1Password or `default` for the top-level role.

Expect for 1Password to verify your identity at least once per session.

All commands accept the following optional arguments

`--region` AWS region to operate against

`--duration` Duration for session to be valid for. (1hr, 120mins etc.)



## op-aws-vault exec

This opens an authenticated shell with the role you choose

`op-aws-vault exec <role name>`

`op-aws-vault exec dev` would open a shell with

`op-aws-vault exec dev -- /bin/bash` would open a bash shell explicitly

Unlike `aws-vault`, `op-aws-vault` can be safely nested.



## op-aws-vault login

`op-aws-vault login dev` to open a web browser with a federated console Login for the `dev` role.

If you'd prefer to not open a browser, just get the URL, use the `--stdout` option to print to console.




