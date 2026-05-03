import random
import string
import sys
import os

from mockssh.server import Server


def first_user(server: Server) -> str:
    return next(iter(server.users))


def random_string() -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(20))


def _cat_command(stderr=False):
    if sys.platform == "win32":
        script = os.path.join(os.path.dirname(__file__), "_cat.py")
        cmd = f'"{sys.executable}" "{script}"'
        if stderr:
            cmd += " --stderr"
        return cmd
    else:
        if stderr:
            return "cat 1>&2"
        return "cat"


def streaming_test(server: Server, command: str, tested_fd: int, number_of_inputs: int=1):
    with server.client(first_user(server)) as c:
        fds = stdin, stdout, stderr = c.exec_command(command)
        for i in range(number_of_inputs):
            channel_input = random_string() + "\n"
            stdin.write(channel_input)
            channel_output = fds[tested_fd].readline()
            assert channel_output == channel_input


def test_stdin_to_stdout(server: Server):
    return streaming_test(server, _cat_command(), 1)


def test_stdin_to_stderr(server: Server):
    streaming_test(server, _cat_command(stderr=True), 2)


def test_streaming_output(server: Server):
    streaming_test(server, _cat_command(), 1, 100)
