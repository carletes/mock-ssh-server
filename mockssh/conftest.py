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
def server():
    users = {
        "sample-user": SAMPLE_USER_KEY,
    }
    with Server(users) as s:
        yield s


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(threadName)s %(name)s %(message)s")
