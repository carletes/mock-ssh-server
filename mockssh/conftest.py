import logging
import os
import shutil
import tempfile

from pytest import fixture

from mockssh import Server
import mockssh.server
from paramiko.sftp_client import SFTPClient
from typing import Iterator

__all__ = [
    "server",
]


SAMPLE_USER_KEY = os.path.join(os.path.dirname(__file__), "sample-user-key")
SAMPLE_USER_PASSWORD = "greeneggs&spam"

@fixture
def user_key_path() -> str:
    return SAMPLE_USER_KEY


@fixture(scope="function")
def server() -> Iterator[mockssh.server.Server]:
    users = {
        "sample-user": SAMPLE_USER_KEY,
        "sample-user2": {"type": "password", "password": SAMPLE_USER_PASSWORD},
        "sample-user3": {"type": "key",  "private_key_path": SAMPLE_USER_KEY},
    }
    with Server(users) as s:
        yield s


@fixture
def sftp_client(server: mockssh.server.Server) -> Iterator[SFTPClient]:
    uid = tuple(server.users)[0]
    c = server.client(uid)
    yield c.open_sftp()


@fixture
def tmp_dir() -> Iterator[str]:
    if hasattr(tempfile, "TemporaryDirectory"):
        # python 3
        with tempfile.TemporaryDirectory() as td:
            yield td
    else:
        # python 2
        td = tempfile.mkdtemp()
        yield td
        shutil.rmtree(td)


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(threadName)s %(name)s %(message)s")
