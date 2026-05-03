import socket
import sys
import threading
import selectors


class Stream:
    def __init__(self, fd, read, write, flush):
        self.fd = fd
        self.read = read
        self.write = write
        self.flush = flush

    def transfer(self):
        data = self.read()
        self.write(data)
        self.flush()
        return data

    def drain(self):
        while True:
            if not self.transfer():
                return


class StreamTransfer:
    BUFFER_SIZE = 1024

    def __init__(self, ssh_channel, process):
        self.process = process
        self.streams = [
            self.ssh_to_process(ssh_channel, self.process.stdin),
            self.process_to_ssh(self.process.stdout, ssh_channel.sendall),
            self.process_to_ssh(self.process.stderr, ssh_channel.sendall_stderr),
        ]

    def ssh_to_process(self, channel, process_stream):
        return Stream(channel, lambda: channel.recv(self.BUFFER_SIZE), process_stream.write, process_stream.flush)

    @staticmethod
    def process_to_ssh(process_stream, write_func):
        return Stream(process_stream, process_stream.readline, write_func, lambda: None)

    def run(self):
        if sys.platform == "win32":
            self._run_with_threads()
        else:
            self._run_with_selectors()

    def _run_with_selectors(self):
        with selectors.DefaultSelector() as selector:
            for stream in self.streams:
                selector.register(stream.fd, selectors.EVENT_READ, data=stream)

            self.transfer(selector)
            self.drain(selector)

    def _run_with_threads(self):
        error_queue = []
        lock = threading.Lock()
        stop_event = threading.Event()

        stdin_stream = self.streams[0]
        stdout_stream = self.streams[1]
        stderr_stream = self.streams[2]

        stdin_stream.fd.settimeout(0.5)

        def stdin_thread():
            try:
                while not stop_event.is_set():
                    try:
                        data = stdin_stream.fd.recv(self.BUFFER_SIZE)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    try:
                        stdin_stream.write(data)
                        stdin_stream.flush()
                    except (OSError, ValueError):
                        break
                try:
                    self.process.stdin.close()
                except (OSError, ValueError):
                    pass
            except Exception as e:
                with lock:
                    error_queue.append(e)

        def output_thread(stream):
            try:
                stream.drain()
            except Exception as e:
                with lock:
                    error_queue.append(e)

        stdin_t = threading.Thread(target=stdin_thread, daemon=True)
        stdout_t = threading.Thread(target=output_thread, args=(stdout_stream,), daemon=True)
        stderr_t = threading.Thread(target=output_thread, args=(stderr_stream,), daemon=True)

        stdin_t.start()
        stdout_t.start()
        stderr_t.start()

        stdout_t.join()
        stderr_t.join()

        stop_event.set()
        stdin_t.join(timeout=5)

        if error_queue:
            raise error_queue[0]

    @staticmethod
    def ready_streams(selector):
        return (key.data for key, _ in selector.select(timeout=-1))

    def transfer(self, selector):
        while self.process.poll() is None:
            for stream in self.ready_streams(selector):
                stream.transfer()

    def drain(self, selector):
        for stream in self.ready_streams(selector):
            stream.drain()
