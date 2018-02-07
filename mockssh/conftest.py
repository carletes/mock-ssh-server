import tempfile
import logging
import shutil
import os

from pytest import fixture, yield_fixture

from mockssh import Server


__all__ = [
    "server",
]


SAMPLE_USER_KEY = os.path.join(os.path.dirname(__file__), "sample-user-key")


@fixture
def user_key_path():
    return SAMPLE_USER_KEY


@yield_fixture(scope="function")
def server():
    users = {
        "sample-user": SAMPLE_USER_KEY,
    }
    with Server(users) as s:
        yield s


@yield_fixture
def sftp_client(server):
    uid = tuple(server.users)[0]
    c = server.client(uid)
    yield c.open_sftp()


@yield_fixture
def tmp_dir():
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
