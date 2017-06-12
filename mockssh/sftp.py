import logging
import os
from errno import EACCES, EDQUOT, ENOENT, ENOTDIR, EPERM, EROFS

import paramiko
from paramiko import SFTPAttributes


__all__ = [
    "SFTPServer",
]


class SFTPHandle(paramiko.SFTPHandle):

    log = logging.getLogger(__name__)

    def __init__(self, file_obj, flags=0):
        super(SFTPHandle, self).__init__(flags)
        self.file_obj = file_obj

    @property
    def readfile(self):
        return self.file_obj

    @property
    def writefile(self):
        return self.file_obj


def returns_sftp_error(func):

    LOG = logging.getLogger(__name__)

    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OSError as err:
            LOG.debug("Error calling %s(%s, %s): %s",
                      func, args, kwargs, err, exc_info=True)
            errno = err.errno
            if errno in {EACCES, EDQUOT, EPERM, EROFS}:
                return paramiko.SFTP_PERMISSION_DENIED
            if errno in {ENOENT, ENOTDIR}:
                return paramiko.SFTP_NO_SUCH_FILE
            return paramiko.SFTP_FAILURE
        except Exception as err:
            LOG.debug("Error calling %s(%s, %s): %s",
                      func, args, kwargs, err, exc_info=True)
            return paramiko.SFTP_FAILURE

    return wrapped


class SFTPServerInterface(paramiko.SFTPServerInterface):

    log = logging.getLogger(__name__)

    def __init__(self, server, *largs, **kwargs):
        self._root = kwargs.pop('root', None)
        super(SFTPServerInterface, self).__init__(server, *largs, **kwargs)

    def _path_join(self, path):
        return os.path.realpath(
            os.path.join(self._root, os.path.normpath(path)))

    def list_folder(self, path):
        path = self._path_join(path)
        result = []
        for filename in os.listdir(path):
            stat_data = os.stat(os.path.join(path, filename))
            item = SFTPAttributes.from_stat(stat_data)
            item.filename = filename
            result.append(item)
            print(result)
        return result

    def session_started(self):
        pass

    def session_ended(self):
        pass

    @returns_sftp_error
    def open(self, path, flags, attr):
        fd = os.open(path, flags)
        self.log.debug("open(%s): fd: %d", path, fd)
        if flags & (os.O_WRONLY | os.O_RDWR):
            mode = "w"
        elif flags & (os.O_APPEND):
            mode = "a"
        else:
            mode = "r"
        mode += "b"
        self.log.debug("open(%s): Mode: %s", path, mode)
        return SFTPHandle(os.fdopen(fd, mode), flags)

    @returns_sftp_error
    def stat(self, path):
        st = os.stat(path)
        return paramiko.SFTPAttributes.from_stat(st, path)


class SFTPServer(paramiko.SFTPServer):

    def __init__(self, channel, name, server, sftp_si=SFTPServerInterface,
                 *largs, **kwargs):
        kwargs["sftp_si"] = SFTPServerInterface
        super(SFTPServer, self).__init__(
            channel, name, server, *largs, **kwargs)
