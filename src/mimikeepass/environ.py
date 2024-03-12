from os import environ, getuid
from typing import Optional


def get_runtime_directory() -> str:
    return environ.get("XDG_RUNTIME_DIR") or (f"/run/user/{getuid()}")


def resolve_socket_path(socket_path: Optional[str] = None) -> str:
    socket_path = (
        socket_path
        or environ.get("MIMIKEEPASS_SOCKET")
        or get_runtime_directory() + "/mimikeepass.varlink"
    )
    if "/" not in socket_path:
        socket_path = get_runtime_directory() + socket_path
    return socket_path
