#!/usr/bin/python3

import subprocess
from os import environ
from sys import argv
from re import compile
from dataclasses import dataclass
from typing import Optional

from mimikeepass.askpass.core import ask_pass
from mimikeepass.client import MimiKeepassClient


PASSWORD_AUTH_PROMPT_RE = compile("^([^\s]+)@([^@\s]+)'s password: $")


@dataclass
class PasswordAuthenticationRequest:
    username: str
    host: str


def parse_password_authentication_prompt(
    prompt: str,
) -> Optional[PasswordAuthenticationRequest]:
    match = PASSWORD_AUTH_PROMPT_RE.match(prompt)
    if match is None:
        return None
    return PasswordAuthenticationRequest(username=match.group(1), host=match.group(2))


def get_password_mimikeepass(title=None, url=None, username=None) -> Optional[str]:
    """
    Get a password from mimikeepassd
    """
    client = MimiKeepassClient()
    try:
        return client.get_password(title=title, url=url, username=username)
    finally:
        client.close()


def resolve_password(prompt: str) -> Optional[str]:

    if environ.get("SSH_ASKPASS_PROMPT"):
        return ask_pass(prompt, variable="MIMIKEEPASS_SSH_ASKPASS")

    password: Optional[str] = None

    req = parse_password_authentication_prompt(prompt)
    if req is not None:

        host = req.host
        username = req.username

        url = "ssh://" + host

        password = get_password_mimikeepass(url=url, username=username)
        if password is not None:
            return password

        # WALLIX WAB support,
        # Process username like target_user@???@target_hostname:SSH:???:real_user@auth_system
        if ":" in username:
            password = get_password_mimikeepass(
                url=url, username=username.split(":")[-1]
            )
            if password is not None:
                return password

        # Fallback to terminal or MIMIKEEPASS_ASKPASS:
        return ask_pass(prompt, variable="MIMIKEEPASS_SSH_ASKPASS")

    else:
        return ask_pass(prompt, variable="MIMIKEEPASS_SSH_ASKPASS")


def main():
    prompt = argv[1]
    password = resolve_password(prompt)
    if password:
        print(password)
    else:
        exit(1)


if __name__ == "__main__":
    main()
