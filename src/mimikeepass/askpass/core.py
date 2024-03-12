from getpass import getpass
from typing import Optional
from os import environ
import subprocess


def check_tty_available() -> bool:
    try:
        tty = open("/dev/tty", "rb")
        tty.close()
        return True
    except:
        return False


def ask_pass_terminal(prompt: str) -> Optional[str]:
    """
    Ask password using the terminal
    """
    try:
        # TODO, add terminal notification?
        return getpass(prompt)
    except:
        return None


def ask_pass_program(prompt: str, program: Optional[str] = None) -> Optional[str]:
    if program is None:
        program = environ.get("MIMIKEEPASS_SSH_ASKPASS")
    if program is None:
        raise Exception("Missing program name")
    res = subprocess.run([program, prompt], capture_output=True)
    if res.returncode != 0:
        return None
    password = res.stdout.decode("UTF-8")
    if password.endswith("\n"):
        password = password[:-1]
    return password


def ask_pass(prompt: str, variable: str) -> Optional[str]:
    """
    Ask password (or something else)
    """

    program = environ.get(variable)
    require = environ.get(variable + "_REQUIRE")
    has_gui = environ.get("DISPLAY") is not None

    if program is None:
        return ask_pass_terminal(prompt)

    if require == "never":
        return ask_pass_terminal(prompt)

    if require == "prefer":
        if has_gui:
            return ask_pass_program(prompt, program=program)
        else:
            return ask_pass_terminal(prompt)

    if require == "force":
        return ask_pass_program(prompt, program=program)

    if not has_gui:
        return ask_pass_terminal(prompt)

    if check_tty_available():
        return ask_pass_terminal(prompt)
    else:
        return ask_pass_program(prompt, program=program)
