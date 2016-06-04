import codecs
import platform

from pytest import raises


def test_ssh_session(server):
    for uid in server.users:
        with server.client(uid) as c:
            _, stdout, _ = c.exec_command("ls /")
            assert "etc" in (codecs.decode(bit, "utf8")
                             for bit in stdout.read().split())

            _, stdout, _ = c.exec_command("hostname")
            assert (codecs.decode(stdout.read().strip(), "utf8") ==
                    platform.node())


def test_ssh_failed_commands(server):
    for uid in server.users:
        with server.client(uid) as c:
            _, _, stderr = c.exec_command("rm /")
            stderr = codecs.decode(stderr.read(), "utf8")
            assert (stderr.startswith("rm: cannot remove") or
                    stderr.startswith("rm: /: is a directory"))


def test_invalid_user(server):
    with raises(KeyError) as exc:
        server.client("unknown-user")

    user = exc.value.args[0]

    # py2.6
    if isinstance(user, tuple):
        user = user[0]

    assert user == "unknown-user"


def test_add_user(server, user_key_path):
    with raises(KeyError):
        server.client("new-user")

    server.add_user("new-user", user_key_path)
    with server.client("new-user") as c:
        _, stdout, _ = c.exec_command("echo 42")
        assert codecs.decode(stdout.read().strip(), "utf8") == "42"
