from sys import stderr
from os import getuid, unlink, environ, chmod, getpid, stat, stat_result
from socket import socket, socketpair, SOCK_STREAM, AF_UNIX, SOL_SOCKET, SO_PEERCRED
from typing import Optional, List, Dict, Any, cast
import struct
import json
from threading import Thread, Lock
from selectors import DefaultSelector, EVENT_READ
from time import clock_gettime, CLOCK_MONOTONIC
from dataclasses import dataclass

import click
from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError

from mimikeepass.environ import resolve_socket_path
from mimikeepass.askpass.ssh import ask_pass
from mimikeepass.socket import FramingSocket, JsonSocket


class KeePassDatabase:
    filename: str
    password: str
    database: Optional[PyKeePass]
    statinfo: Optional[stat_result]

    def __init__(self, filename: str, password: str):
        self.filename = filename
        self.password = password
        self.database = PyKeePass(filename, password=password)
        self.statinfo = stat(self.filename)

    def refresh(self):
        statinfo = stat(self.filename)
        if (
            self.database is None
            or self.statinfo is None
            or statinfo.st_dev != self.statinfo.st_dev
            or statinfo.st_ino != self.statinfo.st_ino
            or statinfo.st_mtime != self.statinfo.st_mtime
        ):
            try:
                self.database = PyKeePass(self.filename, password=self.password)
                self.statinfo = stat(self.filename)
            except:
                # TODO, prompt for password again?
                self.database = None
                self.statinfo = None


def open_keepass(filename: str) -> KeePassDatabase:
    error: Optional[BaseException] = None
    for i in range(3):
        password = ask_pass(
            f"Password for keepass file {filename}: ", variable="SSH_ASKPASS"
        )
        if password is None:
            continue
        try:
            kp = KeePassDatabase(filename, password=password)
            return kp
        except CredentialsError as e:
            error = e
            stderr.write(f"Invalid password for {filename}\n")
            continue
    assert error is not None
    raise error


@dataclass
class Entry:
    title: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tags: Optional[List[str]] = None


class MimiKeepassDaemon:
    _kp: List[KeePassDatabase]
    _max_buffer_size = 4096
    _lock: Lock
    _connections_lock: Lock
    _connections: int
    _idle_duration: float
    _notify_read: socket
    _notify_write: socket
    _idle_timestamp: Optional[float]

    def __init__(self, kp: List[PyKeePass], idle: float = 0):
        self._kp = kp
        self._max_buffer_size = 4096
        self._lock = Lock()
        self._connections_lock = Lock()
        self._connections = 0
        self._idle_timestamp = clock_gettime(CLOCK_MONOTONIC)
        self._idle_duration = idle
        self._notify_read, self._notify_write = socketpair()
        self._notify_read.setblocking(False)

    def get_entry(
        self,
        username: Optional[str] = None,
        url: Optional[str] = None,
        uuid: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[Entry]:
        with self._lock:
            for kp in self._kp:
                kp.refresh()
                if kp.database is None:
                    continue
                args = {}
                if username is not None:
                    args["username"] = username
                if url is not None:
                    args["url"] = url
                if uuid is not None:
                    args["uuid"] = uuid
                if title is not None:
                    args["title"] = title
                entry = kp.database.find_entries(first=True, **args)
                if entry is None:
                    continue
                return Entry(
                    title=entry.deref("title"),
                    url=entry.deref("url"),
                    username=entry.deref("username"),
                    password=entry.deref("password"),
                    tags=entry.deref("tags"),
                )
        return None

    def handle_request(self, request: Dict[str, Any]) -> object:
        # TODO, handle exceptions
        method = request["method"]
        parameters = request["parameters"]
        if method == "fr.urdhr.mimikeepass.GetEntry":
            res = self.get_entry(
                username=parameters.get("username"),
                url=parameters.get("url"),
                uuid=parameters.get("uuid"),
                title=parameters.get("title"),
            )
            if res is None:
                return None
            else:
                return {
                    "title": res.title,
                    "url": res.url,
                    "username": res.username,
                    "password": res.password,
                    "tags": res.tags,
                }
        else:
            # TODO, handle this
            raise Exception("Invalid request")

    def serve_conn(self, conn: socket):
        vsock = JsonSocket(FramingSocket(conn, separator=b"\0"))
        try:
            while True:
                request = vsock.recv()
                if request is None or not isinstance(request, dict):
                    return
                oneway = request.get("oneway")
                response = self.handle_request(request)
                if not oneway:
                    conn.sendall(json.dumps(response).encode("UTF-8") + b"\0")
        finally:
            vsock.close()
            notify = False
            with self._connections_lock:
                self._connections -= 1
                if self._connections == 0:
                    self._idle_timestamp = clock_gettime(CLOCK_MONOTONIC)
                    notify = True
            if notify:
                self._notify_write.send(b"\0")

    def _get_timeout(self) -> Optional[float]:
        if self._idle_duration <= 0:
            return None
        with self._connections_lock:
            if self._idle_timestamp is None:
                return None
            else:
                idle_duration = clock_gettime(CLOCK_MONOTONIC) - self._idle_timestamp
                return self._idle_duration - idle_duration

    def accept_connections(self, socks: List[socket]):
        uid = getuid()

        selector = DefaultSelector()
        for sock in socks:
            sock.setblocking(False)
            selector.register(sock, EVENT_READ)

        selector.register(self._notify_read, EVENT_READ)

        while True:

            timeout = self._get_timeout()
            if timeout is not None and timeout <= 0:
                return

            for key, _ in selector.select(timeout):

                if key.fileobj == self._notify_read:
                    try:
                        while True:
                            self._notify_read.recv(1000)
                    except BlockingIOError as e:
                        pass
                    continue

                conn, addr = cast(socket, key.fileobj).accept()
                creds = conn.getsockopt(SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
                conn_pid, conn_uid, conn_gid = struct.unpack("3i", creds)
                if conn_uid != uid:
                    conn.close()
                    continue

                with self._connections_lock:
                    self._idle_timestamp = None
                    self._connections += 1

                thread = Thread(target=self.serve_conn, args=[conn])
                thread.run()


def get_listen_fds() -> Optional[int]:
    listen_pid_var = environ.get("LISTEN_PID")
    listen_pid = None if listen_pid_var is None else int(listen_pid_var)
    if listen_pid != getpid():
        return None
    listen_fds_var = environ.get("LISTEN_FDS")
    listen_fds = None if listen_fds_var is None else int(listen_fds_var)
    if listen_fds is None:
        return None
    del environ["LISTEN_FDS"]
    del environ["LISTEN_PID"]
    if "LISTEN_FDNAMES" in environ:
        del environ["LISTEN_FDNAMES"]
    return listen_fds


def serve(files: str, socket_path: Optional[str], idle: float = 0):
    if len(files) == 0:
        raise Exception("No files specified")

    try:
        daemon = MimiKeepassDaemon([open_keepass(file) for file in files], idle=idle)
    except CredentialsError as e:
        exit(1)

    listen_fds = get_listen_fds()
    socket_paths = []
    try:
        socks: List[socket] = []
        if listen_fds is not None:
            for i in range(listen_fds):
                sock = socket(fileno=i + 3)
                socks.append(sock)
        else:
            socket_path = resolve_socket_path(socket_path)

            sock = socket(SOCK_STREAM, AF_UNIX)
            sock.bind(socket_path)
            chmod(socket_path, 0o600)
            sock.listen(10)

            socket_paths.append(socket_path)
            socks.append(sock)

        daemon.accept_connections(socks)

    finally:
        for socket_path in socket_paths:
            try:
                unlink(socket_path)
            except:
                pass
