import codecs
import locale
import platform
import sys
import threading
from queue import Queue
from typing import Tuple

import paramiko
import pytest
from pytest import raises

import mockssh
from _pytest.monkeypatch import MonkeyPatch
from mockssh.server import Server


def test_ssh_session(server: Server):
    for uid in server.users:
        print('Testing multiple connections with user', uid)
        print('=================================================')
        with server.client(uid) as c:
            assert isinstance(c, paramiko.SSHClient)


def test_ssh_exec_command(server: Server):
    is_windows = sys.platform == "win32"
    encoding = locale.getpreferredencoding(False)

    for uid in server.users:
        with server.client(uid) as c:
            if is_windows:
                _, stdout, _ = c.exec_command("cmd /c echo %OS%")
                output = codecs.decode(stdout.read(), encoding, errors="replace")
                assert "Windows" in output
            else:
                _, stdout, _ = c.exec_command("ls /")
                assert "etc" in (codecs.decode(bit, "utf8")
                                 for bit in stdout.read().split())

            hostname_cmd = "hostname" if is_windows else "uname -n"
            _, stdout, _ = c.exec_command(hostname_cmd)
            assert (codecs.decode(stdout.read().strip(), encoding, errors="replace") ==
                    platform.node())


def test_ssh_failed_commands(server: Server):
    is_windows = sys.platform == "win32"
    encoding = locale.getpreferredencoding(False)

    for uid in server.users:
        with server.client(uid) as c:
            if is_windows:
                _, _, stderr = c.exec_command("type C:\\nonexistent_file_12345")
            else:
                _, _, stderr = c.exec_command("ls /nonexistent_dir_12345")
            stderr_output = codecs.decode(stderr.read(), encoding, errors="replace")
            assert stderr_output.strip()


def test_concurrent_connections(server: Server):
    results: Queue[Tuple[str, int, str]] = Queue()
    threads = []
    user = list(server.users)[0]

    def connect_and_execute(thread_id: int):
        try:
            with server.client(user) as c:
                _, stdout, _ = c.exec_command("echo hello")
                output = codecs.decode(stdout.read().strip(), "utf8")
                results.put(("success", thread_id, output))
        except Exception as e:
            results.put(("error", thread_id, str(e)))

    for i in range(5):
        t = threading.Thread(target=connect_and_execute, args=(i,))
        t.daemon = True
        t.start()
        threads.append(t)

    for i, t in enumerate(threads):
        t.join(timeout=30)
        if t.is_alive():
            raise RuntimeError(f"Thread {i} timed out")

    assert results.qsize() == 5

    errors = []
    outputs = []
    for _ in range(5):
        status, thread_id, msg = results.get()
        if status == "error":
            errors.append(f"Thread {thread_id}: {msg}")
        else:
            outputs.append((thread_id, msg))

    if errors:
        raise AssertionError(f"Errors: {'; '.join(errors)}")

    for thread_id, output in outputs:
        assert output == "hello"


@pytest.mark.parametrize("trial", range(5))
def test_sequential_exec_command(server: Server, trial: int):
    user = list(server.users)[0]
    with server.client(user) as c:
        _, stdout, _ = c.exec_command("echo hello")
        output = codecs.decode(stdout.read().strip(), "utf8")
        assert output == "hello"


def test_invalid_user(server: Server):
    with raises(KeyError) as exc:
        server.client("unknown-user")
    assert exc.value.args[0] == "unknown-user"


def test_add_user(server: Server, user_key_path: str):
    with raises(KeyError):
        server.client("new-user")

    server.add_user("new-user", user_key_path)
    with server.client("new-user") as c:
        _, stdout, _ = c.exec_command("echo 42")
        assert codecs.decode(stdout.read().strip(), "utf8") == "42"


def test_overwrite_handler(server: Server, monkeypatch: MonkeyPatch):
    class MyHandler(mockssh.server.Handler):
        def check_auth_password(self, username, password):
            if username == "foo" and password == "bar":
                return paramiko.AUTH_SUCCESSFUL
            return paramiko.AUTH_FAILED
    monkeypatch.setattr(server, 'handler_cls', MyHandler)
    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        with raises(paramiko.ssh_exception.AuthenticationException):
            client.connect(server.host, server.port, "fooooo", "barrrr")
