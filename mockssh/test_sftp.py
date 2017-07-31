import os
import tempfile

from pytest import fixture, raises


def files_equal(fname1, fname2):
    if os.stat(fname1).st_size == os.stat(fname2).st_size:
        with open(fname1, "rb") as f1, open(fname2, "rb") as f2:
            if f1.read() == f2.read():
                return True


def test_sftp_session(server):
    for uid in server.users:
        target_dir = tempfile.mkdtemp()
        target_fname = os.path.join(target_dir, "foo")
        assert not os.access(target_fname, os.F_OK)

        with server.client(uid) as c:
            sftp = c.open_sftp()
            sftp.put(__file__, target_fname, confirm=True)
            assert files_equal(target_fname, __file__)

            second_copy = os.path.join(target_dir, "bar")
            assert not os.access(second_copy, os.F_OK)
            sftp.get(target_fname, second_copy)
            assert files_equal(target_fname, second_copy)

            dir_contents = sftp.listdir(target_dir)
            assert len(dir_contents) == 2
            assert "foo" in dir_contents
            assert "bar" in dir_contents
            with raises(IOError):
                sftp.listdir("/123_no_dir")


@fixture(params=[("chmod", "/", 0o755),
                 ("chown", "/", 0, 0),
                 ("listdir_attr", "/"),
                 ("lstat", "/"),
                 ("mkdir", "/tmp/foo"),
                 ("readlink", "/etc"),
                 ("remove", "/etc/passwd"),
                 ("rename", "/tmp/foo", "/tmp/bar"),
                 ("rmdir", "/"),
                 ("symlink", "/tmp/foo", "/tmp/bar"),
                 ("truncate", "/etc/passwd", 0),
                 ("unlink", "/etc/passwd"),
                 ("utime", "/", (0, 0))])
def unsupported_call(request):
    return request.param


def _test_sftp_unsupported_calls(server, unsupported_call):
    for uid in server.users:
        with server.client(uid) as c:
            meth, args = unsupported_call[0], unsupported_call[1:]
            sftp = c.open_sftp()
            with raises(IOError) as exc:
                getattr(sftp, meth)(*args)
            assert str(exc.value) == "Operation unsupported"
