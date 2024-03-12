from typing import Optional

import click

from mimikeepass.client import MimiKeepassClient
import mimikeepass.daemon


@click.group
def main(): ...


@main.command()
@click.argument("files", nargs=-1)
@click.option("--socket", "socket_path")
@click.option("--idle", type=float, default=0)
def serve(files: str, socket_path: Optional[str], idle: float = 0):
    mimikeepass.daemon.serve(files=files, socket_path=socket_path, idle=idle)


@main.command()
@click.option("--title", type=str, default=None)
@click.option("--url", type=str, default=None)
@click.option("--username", type=str, default=None)
def password(title=None, url=None, username=None) -> Optional[str]:
    """
    Get a password from mimikeepass server
    """
    client = MimiKeepassClient()
    try:
        res = client.get_password(title=title, url=url, username=username)
        if res is None:
            exit(1)
        print(res)
    finally:
        client.close()


if __name__ == "__main__":
    main()
