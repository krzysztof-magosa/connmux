#!/usr/bin/env python


import socket
import select
import sys
import json
import base64
import itertools
import Queue


class App:
    def __init__(self, host, port, mode):
        self.host = host
        self.port = port
        self.mode = mode

        self.id = itertools.count()
        self.id2s = dict()
        self.s2id = dict()

        self.mux_in = sys.stdin
        self.mux_out = sys.stdout

        self.sockets = set([self.mux_in])
        self.buffers = dict()
        self.listener = None

        if mode == "server":
            self.init_server()

    def init_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host, self.port))
        sock.listen(100)

        self.sockets.add(sock)
        self.listener = sock

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        return sock

    def register_socket(self, sock, id=None):
        if id is None:
            id = next(self.id)

        self.sockets.add(sock)
        self.buffers[sock] = Queue.Queue()
        self.s2id[sock] = id
        self.id2s[id] = sock

        return id

    def unregister_socket(self, sock):
        id = self.s2id[sock]
        self.sockets.remove(sock)
        del self.s2id[sock]
        del self.id2s[id]

    def accept_client(self, listener):
        sock, address = listener.accept()
        id = self.register_socket(sock)
        self.mux_event(id=id, type="connect", payload="{}:{}".format(*address))

    def mux_event(self, id, type, payload):
        frame = dict(
            id=id,
            type=type,
            payload=base64.b64encode(payload)
        )
        self.mux_out.write("{}\n".format(json.dumps(frame)))
        self.mux_out.flush()

    def process_mux_input(self, data):
        frame = json.loads(data)

        if frame["type"] == "connect":
            sock = self.connect()
            self.register_socket(sock, id=frame["id"])
        else:
            sock = self.id2s.get(frame["id"])
            if sock:
                self.buffers[sock].put(frame)

    def process_socket_input(self, sock, data):
        id = self.s2id[sock]
        self.mux_event(id=id, type="data", payload=data)

    def handle_conn_drop(self, sock):
        if sock in self.sockets:
            sock.close()
            id = self.s2id.get(sock)
            self.mux_event(id=id, type="disconnect", payload="")
            self.unregister_socket(sock)

    def handle_read(self, sock):
        if sock == self.listener:
            self.accept_client(sock)
        else:
            if sock == self.mux_in:
                data = sock.readline()
                self.process_mux_input(data)
            else:
                data = sock.recv(4096)
                if not data:
                    self.handle_conn_drop(sock)
                    return

                self.process_socket_input(sock, data)

    def handle_write(self, sock):
        try:
            frame = self.buffers[sock].get()
            if frame["type"] == "disconnect":
                sock.close()
                self.unregister_socket(sock)
            elif frame["type"] == "data":
                sock.sendall(base64.b64decode(frame["payload"]))
        except socket.error:
            self.handle_conn_drop(sock)

    def handle_exception(self, sock):
        self.handle_conn_drop(sock)

    def poll(self):
        waiting_for_write = set()
        for sock, buffer in self.buffers.items():
            if not buffer.empty():
                waiting_for_write.add(sock)

        readable, writable, exceptional = select.select(self.sockets, waiting_for_write, self.sockets)

        for sock in readable:
            self.handle_read(sock)

        for sock in writable:
            self.handle_write(sock)

        for sock in exceptional:
            self.handle_exception(sock)

    def loop(self):
        while True:
            self.poll()


app = App(host=sys.argv[1], port=int(sys.argv[2]), mode=sys.argv[3])
app.loop()
