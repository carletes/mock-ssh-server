import logging
import os

from pytest import yield_fixture

from mockssh import Server


__all__ = [
    "server",
]


@yield_fixture(scope="function")
def server():
    here = os.path.dirname(__file__)
    users = {
        "sample-user": os.path.join(here, "sample-user-key"),
    }
    with Server(users) as s:
        yield s


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(threadName)s %(name)s %(message)s")
