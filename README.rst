mock-ssh-server - An SSH server for testing purposes
====================================================

``mock-ssh-server`` packs a Python context manager that implements an SSH
server for testing purposes. It is built on top of `paramiko`_, so it does
not need OpenSSH binaries to be installed.


Sample usage
------------

As a `py.test`_ fixture::

    import os

    from pytest import yield_fixture

    import mockssh


    @yield_fixture()
    def server():
        users = {
            "sample-user": "/path/to/user-private-key,
        }
        with mockssh.Server(users) as s:
            yield s


    def test_ssh_session(server):
        for uid in server.users:
            with server.client(uid) as c:
                _, stdout, _ = c.exec_command("ls /")
                assert stdout.read()

    def test_sftp_session(server):
        for uid in server.users:
            target_dir = tempfile.mkdtemp()
            target_fname = os.path.join(target_dir, "foo")
            assert not os.access(target_fname, os.F_OK)

            with server.client(uid) as c:
                sftp = c.open_sftp()
                sftp.put(__file__, target_fname, confirm=True)
                assert os.access(target_fname, os.F_OK)


.. _paramiko: http://www.paramiko.org/
.. _py.test:  http://pytest.org/latest/
.. image:: https://travis-ci.org/carletes/mock-ssh-server.svg
	   :target: https://travis-ci.org/carletes/mock-ssh-server
