import logging
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
def server(tmpdir):
    root = tmpdir.join('sftp').mkdir().strpath
    users = {
        'sample-user': {
            'key': SAMPLE_USER_KEY,
            'passphrase': None,
        }
    }
    with Server(users, root=root) as s:
        yield s


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(threadName)s %(name)s %(message)s")
