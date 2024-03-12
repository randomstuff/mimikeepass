from typing import Optional, cast, Dict, Any
from socket import socket, SOCK_STREAM, AF_UNIX
from os import environ

from mimikeepass.environ import resolve_socket_path
from mimikeepass.socket import JsonSocket, FramingSocket


class MimiKeepassClient:

    _vsock: JsonSocket

    def __init__(self, sock: Optional[socket] = None):
        if sock is not None:
            pass
        else:
            socket_path = resolve_socket_path()
            sock = socket(SOCK_STREAM, AF_UNIX)
            try:
                sock.connect(socket_path)
            except:
                sock.close()
                raise
        self._vsock = JsonSocket(FramingSocket(sock, separator=b"\0"))

    def get_password(self, title=None, url=None, username=None) -> Optional[str]:
        parameters = {}
        if title is not None:
            parameters["title"] = title
        if url is not None:
            parameters["url"] = url
        if username is not None:
            parameters["username"] = username

        self._vsock.send(
            {"method": "fr.urdhr.mimikeepass.GetEntry", "parameters": parameters}
        )
        response = self._vsock.recv()
        if not isinstance(response, dict):
            return None
        res = cast(Dict[str, Any], response).get("password")
        if not isinstance(res, str):
            return None
        return res

    def close(self) -> None:
        if self._vsock is not None:
            self._vsock.close()
