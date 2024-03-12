from typing import Optional, TypeVar, Protocol
from socket import socket
import json


T = TypeVar("T")


class Socket(Protocol[T]):
    def send(self, message: T) -> None: ...

    def recv(self) -> Optional[T]: ...

    def close(self) -> None: ...


class FramingSocket(Socket[bytes]):
    _sock: socket
    _buffer: bytes
    _max_buffer_size = 4096
    _separator: bytes

    def __init__(self, sock: socket, separator: bytes):
        self._sock = sock
        self._buffer = b""
        self._separator = separator

    def recv(self) -> Optional[bytes]:
        if len(self._buffer) > self._max_buffer_size:
            raise IOError("Message too long")
        while True:
            i = self._buffer.find(self._separator)
            if i >= 0:
                res = self._buffer[:i]
                self._buffer = self._buffer[i + len(self._separator) :]
                return res
            chunk = self._sock.recv(4096)
            if not chunk:
                return None
            if len(self._buffer) + len(chunk) > self._max_buffer_size:
                raise IOError("Message too long")
            self._buffer = self._buffer + chunk

    def send(self, message: bytes):
        self._sock.sendall(message + self._separator)

    def close(self):
        self._sock.close()


class JsonSocket(Socket[object]):
    _sock: Socket[bytes]

    def __init__(self, sock: Socket[bytes]):
        self._sock = sock

    def recv(self) -> Optional[object]:
        message = self._sock.recv()
        if message is None:
            return None
        return json.loads(message.decode("UTF-8"))

    def send(self, object):
        self._sock.send(json.dumps(object).encode("UTF-8"))

    def close(self):
        self._sock.close()
