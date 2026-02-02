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

        def transfer_thread(stream):
            try:
                stream.drain()
            except Exception as e:
                with lock:
                    error_queue.append(e)

        threads = [
            threading.Thread(target=transfer_thread, args=(stream,), daemon=True)
            for stream in self.streams
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

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
