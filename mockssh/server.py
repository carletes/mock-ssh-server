import collections.abc
import errno
import logging
import os
import selectors
import socket
import subprocess
import threading
from queue import Queue

import paramiko

from mockssh import sftp
from mockssh.streaming import StreamTransfer
from typing import Dict

__all__ = [
    "Server",
]

SERVER_KEY_PATH = os.path.join(os.path.dirname(__file__), "server-key")


class UserData:
    """
    parameters:
      data: needs to either be a string (the path to the private key), or
            a dictionary of one of the following forms:
            {"type": "key",
             "private_key_path": <some appropriate value>,
             "key_type": # Optional. One of: "ssh-rsa", "ssh-dss",
                         # ECDSAKey format identifiers, or "ssh-ed25519"
            }
            or
            {"type": "password",
             "password": <some appropriate value>
            }
      public_key: The public key to use (rather than calculate).
            Useful if assigning to _users directly.

    """
    allowed_credential_types = ('key', 'password')

    def __init__(self, data, public_key=None):
        self.private_key_path = None
        self.key_type = None
        self.public_key = None
        self.password = None

        if isinstance(data, collections.abc.Mapping):
            if 'type' in data:
                if data['type'] in self.allowed_credential_types:
                    self.credential_type = data['type']
                else:
                    raise ValueError('Unrecognized credential type.')
            else:
                raise ValueError(
                    "users dictionary value is missing key 'type'."
                )
        else:
            # backwards-compatible, assume data is a path to private key
            self.credential_type = "key"
            data = {"type": "key",
                    "private_key_path": data,
                    "key_type": "ssh-rsa"
            }

        if self.credential_type == 'key':
            try:
                self.private_key_path = data["private_key_path"]
            except KeyError:
                raise ValueError(
                    "users dictionary value is missing key 'private_key_path'"
                )
            self.key_type = data.get("key_type", "ssh-rsa")
            if public_key is None:
                self.public_key = self.calculate_public_key(
                    self.private_key_path,
                    self.key_type
                )
            else:
                self.public_key = public_key # supports 'server._users = '
                                             # assignments...
        elif self.credential_type == 'password':
            try:
                self.password = data['password']
            except KeyError:
                raise ValueError(
                    "users dictionary value is missing key 'password'"
                )

    @staticmethod
    def calculate_public_key(private_key_path, key_type="ssh-rsa"):
        if key_type == "ssh-rsa":
            public_key = paramiko.RSAKey.from_private_key_file(
                private_key_path
            )
        elif key_type == "ssh-dss":
            public_key = paramiko.DSSKey.from_private_key_file(
                private_key_path
            )
        elif key_type in paramiko.ECDSAKey.supported_key_format_identifiers():
            public_key = paramiko.ECDSAKey.from_private_key_file(
                private_key_path
            )
        elif key_type == "ssh-ed25519":
            public_key = paramiko.Ed25519Key.from_private_key_file(
                private_key_path
            )
        else:
            raise Exception("Unable to handle key of type {}".format(key_type))
        return public_key


class Handler(paramiko.ServerInterface):
    log = logging.getLogger(__name__)

    def __init__(self, server, client_conn):
        self.server = server
        self.thread = None
        self.command_queues = {}
        client, _ = client_conn
        self.transport = t = paramiko.Transport(client)
        t.add_server_key(paramiko.RSAKey(filename=SERVER_KEY_PATH))
        t.set_subsystem_handler("sftp", sftp.SFTPServer)

    def run(self):
        self.transport.start_server(server=self)
        while True:
            channel = self.transport.accept()
            if channel is None:
                break
            if channel.chanid not in self.command_queues:
                self.command_queues[channel.chanid] = Queue()
            t = threading.Thread(target=self.handle_client, args=(channel,))
            t.daemon = True
            t.start()

    def handle_client(self, channel):
        try:
            command = self.command_queues[channel.chanid].get(block=True)
            self.log.debug("Executing %s", command)
            with subprocess.Popen(command, shell=True,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as p:
                StreamTransfer(channel, p).run()
                channel.send_exit_status(p.returncode)
        except Exception:
            self.log.error("Error handling client (channel: %s)", channel,
                           exc_info=True)
        finally:
            try:
                channel.close()
            except EOFError:
                self.log.debug("Tried to close already closed channel")

    def check_auth_password(self, username, password):
        try:
            user_data = self.server._userdata[username]
        except KeyError:
            self.log.debug("Unknown user '%s'", username)
            return paramiko.AUTH_FAILED

        if user_data.credential_type != 'password':
            self.log.debug("User data for user '%s' is not of type "
                           "'password'; rejecting password."
            )
            return paramiko.AUTH_FAILED

        if user_data.password == password:
            self.log.debug("Accepting password for user '%s'", username)
            return paramiko.AUTH_SUCCESSFUL

        self.log.debug("Rejecting password for user '%s'", username)
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        try:
            user_data = self.server._userdata[username]
        except KeyError:
            self.log.debug("Unknown user '%s'", username)
            return paramiko.AUTH_FAILED

        if user_data.credential_type != 'key':
            self.log.debug("User data for user '%s' is not of type "
                           "'key'; rejecting public key."
            )
            return paramiko.AUTH_FAILED

        if user_data.public_key == key:
            self.log.debug("Accepting public key for user '%s'", username)
            return paramiko.AUTH_SUCCESSFUL

        self.log.debug("Rejecting public key for user '%s'", username)
        return paramiko.AUTH_FAILED

    def check_channel_exec_request(self, channel, command):
        self.command_queues.setdefault(channel.get_id(), Queue()).put(command)
        return True

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        ud = self.server._userdata[username]
        if ud.credential_type == 'key':
            return "publickey"
        else:
            return "password"


class Server(object):
    host = "127.0.0.1"
    handler_cls = Handler

    log = logging.getLogger(__name__)

    def __init__(self, users: Dict[str, str]) -> None:
        self._socket = None
        self._thread = None
        self._userdata = {}
        self._users_cached = None
        for uid, credential in users.items():
            user_data = UserData(credential)
            self._userdata[uid] = user_data


    @property
    def _users(self):
        if self._users_cached is None:
            self._users_cached = {
                k:(ud.private_key_path, ud.public_key)
                for k, ud in self._userdata.items() if ud.credential_type == 'key'
            }
        return self._users_cached

    @_users.setter
    def _users(self, value):
        # Questionable, but backwards compatible if someone ever set
        # this directly. Obviously only supports using private keys.
        self._users_cached = None
        self._userdata = {}
        for uid, data in value.items():
            private_key_path, public_key = data
            self._userdata[uid] = UserData(
                private_key_path,
                public_key=public_key
            )


    def add_user(self, uid: str, private_key_path: str, keytype: str="ssh-rsa") -> None:
        if keytype == "ssh-rsa":
            paramiko.RSAKey.from_private_key_file(private_key_path)
        elif keytype == "ssh-dss":
            paramiko.DSSKey.from_private_key_file(private_key_path)
        elif keytype in paramiko.ECDSAKey.supported_key_format_identifiers():
            paramiko.ECDSAKey.from_private_key_file(private_key_path)
        elif keytype == "ssh-ed25519":
            paramiko.Ed25519Key.from_private_key_file(private_key_path)
        else:
            raise Exception("Unable to handle key of type {}".format(keytype))
        
        self._users_cached = None # invalidate cache
        ud = {"type": "key",
              "private_key_path": private_key_path,
              "key_type": keytype 
            }

        user_data = UserData(ud)
        self._userdata[uid] = user_data

    def __enter__(self) -> "Server":
        self._socket = s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, 0))
        s.listen(5)
        self._thread = t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()
        return self

    def _run(self):
        sock = self._socket
        selector = selectors.DefaultSelector()
        selector.register(sock, selectors.EVENT_READ)
        while sock.fileno() > 0:
            self.log.debug("Waiting for incoming connections ...")
            events = selector.select(timeout=1.0)
            if events:
                try:
                    conn, addr = sock.accept()
                except OSError as ex:
                    if ex.errno in (errno.EBADF, errno.EINVAL):
                        break
                    raise
                self.log.debug("... got connection %s from %s", conn, addr)
                handler = self.handler_cls(self, (conn, addr))
                t = threading.Thread(target=handler.run)
                t.daemon = True
                t.start()

    def __exit__(self, *exc_info) -> None:
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except Exception:
            pass
        self._socket = None
        self._thread = None

    def client(self, uid):
        ud = self._userdata[uid]
        c = paramiko.SSHClient()
        host_keys = c.get_host_keys()

        key = paramiko.RSAKey.from_private_key_file(SERVER_KEY_PATH)
        host_keys.add(self.host, "ssh-rsa", key)
        host_keys.add("[%s]:%d" % (self.host, self.port), "ssh-rsa", key)
        c.set_missing_host_key_policy(paramiko.RejectPolicy())
        conn_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": uid,
            "allow_agent": False,
            "look_for_keys": False
        }
        if ud.credential_type == 'key':
            conn_kwargs["key_filename"] = ud.private_key_path
        else:
            conn_kwargs["password"] = ud.password

        c.connect(**conn_kwargs)
        return c

    @property
    def port(self) -> int:
        return self._socket.getsockname()[1]

    @property
    def users(self):
        return self._userdata.keys()
