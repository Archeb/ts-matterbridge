from pydoc import cli
import socket
import threading
import time
import copy
import traceback

from queue import Queue


class TSConnection:
    _send_queue = Queue()
    _recv_queue = Queue()
    _connected = False
    _running = False
    _client_map = {}
    _channel_map = {}
    _log = None
    _client_channel_moved = False

    def __init__(self, server, port, nick, username, password):
        self._server = server
        self._port = port
        self._nick = nick
        self._username = username
        self._password = password
        self._socket = socket.socket()

    def run(self):
        self._log = open("ts.log", 'a', 1)

        self._running = True

        self.connect()

        self._recv_thread = threading.Thread(target=self.listen)
        self._recv_thread.start()

        self._send_thread = threading.Thread(target=self.process_send_queue)
        self._send_thread.start()

        self._keep_alive_thread = threading.Thread(target=self.keepalive)
        self._keep_alive_thread.start()

    def keepalive(self):
        while self._running:
            if self._connected:
                if(hasattr(self, "_botclid") and self._client_channel_moved == False):
                    # move the bot itself to channel 1
                    print("[TS] Moving myself to channel 1")
                    self._socket.send(
                        bytes("clientmove clid=%s cid=1\n" % (self._botclid,), 'UTF-8'))
                    self._client_channel_moved = True

                self._socket.send(bytes("clientlist\n", 'UTF-8'))
                self._socket.send(bytes("channellist\n", 'UTF-8'))
                self._socket.send(
                    bytes("servernotifyregister event=channel id=1\n", 'UTF-8'))

            time.sleep(1)

    def connect(self):
        print("[TS] Connecting...")
        self._connected = False

        try:
            self._socket = socket.socket()
            self._socket.connect((self._server, self._port))

            self._socket.send(bytes("login %s %s\n" %
                                    (self._username, self._password), 'UTF-8'))
            self._socket.send(bytes("use 1\n", 'UTF-8'))
            self._socket.send(
                bytes("servernotifyregister event=textchannel id=1\n", 'UTF-8'))
            self._socket.send(
                bytes("servernotifyregister event=textserver id=1\n", 'UTF-8'))
            self._socket.send(
                bytes("servernotifyregister event=channel id=1\n", 'UTF-8'))
            self._socket.send(
                bytes("servernotifyregister event=server id=1\n", 'UTF-8'))
            self._socket.send(
                bytes("clientupdate client_nickname=%s\n" % self._nick, 'UTF-8'))
            self._socket.send(
                bytes("clientlist\n", 'UTF-8'))
            print("[TS] Connected")
            self._connected = True
        except:
            self._connected = False
            print("connect to %s on port %s failed.\n" %
                  (self._server, self._port))
            print(traceback.format_exc())
            return

    def listen(self):
        while self._running:
            try:
                while not self._connected:
                    self.connect()

                data = self._socket.recv(4096)

                if len(data) == 0:
                    print("connection to %s lost. Attempting to reconnect...\n" % (
                        self._server, ))
                    self._connected = False
                    continue

                data = data.decode("UTF-8")

                data.strip()

                #print(data + "\n")

                parts = data.split()

                command = parts[0]

                args = {}

                for pair in parts[1:]:
                    bits = pair.partition("=")
                    args[bits[0]] = bits[2]

                if command == "notifytextmessage":
                    msg = self.decode(args["msg"])
                    msg_from = self.decode(args["invokername"])

                    if msg_from.startswith("[Bridge]"):
                        continue

                    self._recv_queue.put(("MSG", msg_from, "", msg))
                elif command == "notifycliententerview":
                    msg_from = self.decode(args["client_nickname"])
                    #self._client_map[args["clid"]]["client_nickname"] = msg_from
                    self._recv_queue.put(("CONNECT", msg_from, ""))
                elif command == "notifyclientleftview":
                    msg_from = self.decode(self._client_map[args["clid"]]["client_nickname"])
                    del self._client_map[args["clid"]]
                    self._recv_queue.put(("QUIT", msg_from, ""))
                elif command.startswith("cid"):
                    data = data.split("\n\r")[0]
                    for channel in data.split("|"):
                        args = {}
                        for pair in channel.split():
                            bits = pair.partition("=")
                            args[bits[0]] = bits[2]
                        if "cid" in args:
                            self._channel_map[args["cid"]] = args if not args["cid"] in self._channel_map else {
                                **self._channel_map[args["cid"]], **args}
                elif command.startswith("clid"):
                    data = data.split("\n\r")[0]
                    # 清除原来的频道用户列表
                    for cid in self._channel_map:
                        self._channel_map[cid]["members"] = []
                    old_client_map = copy.deepcopy(self._client_map)  # 保存旧有用户信息，用于对比频道切换
                    for client in data.split("|"):
                        args = {}
                        for pair in client.split():
                            bits = pair.partition("=")
                            args[bits[0]] = bits[2]
                        if "clid" in args and "client_nickname" in args:
                            if args["client_nickname"] == self._nick:
                                self._botclid = args["clid"]
                            self._client_map[args["clid"]] = args
                            if args["cid"] in self._channel_map:
                                self._channel_map[args["cid"]]["members"].append(args["clid"])
                    # 检测用户是否切换频道
                    for client in self._client_map.items():
                        client = client[1]
                        if client["client_nickname"] != self._nick and client["clid"] in old_client_map and client["cid"] != old_client_map[client["clid"]]["cid"]:
                            from_channel = self._channel_map[old_client_map[client["clid"]]["cid"]]
                            from_channel_name = self.get_channel_name_with_relation(from_channel)
                            to_channel = self._channel_map[client["cid"]]
                            to_channel_name = self.get_channel_name_with_relation(to_channel)
                            self._recv_queue.put(
                                ("MOVE", self.decode(client["client_nickname"]),
                                 from_channel_name, to_channel_name))
            except:
                print(traceback.format_exc())

    def encode(self, data):
        data = data.replace('\\', '\\\\')
        data = data.replace('/', '\\/')
        data = data.replace(' ', '\\s')
        data = data.replace('|', '\\p')
        data = data.replace('\n', '\\n')
        data = data.replace('\r', '\\r')
        data = data.replace('\t', '\\t')
        return data

    def decode(self, data):
        data = data.replace('\\\\', '\\')
        data = data.replace('\\/', '/')
        data = data.replace('\\s', ' ')
        data = data.replace('\\p', '|')
        data = data.replace('\\a', '')
        data = data.replace('\\b', '')
        data = data.replace('\\f', '')
        data = data.replace('\\n', '\n')
        data = data.replace('\\r', '\r')
        data = data.replace('\\t', '    ')
        data = data.replace('\\v', '\n')
        data = data.replace('[URL]', '')
        data = data.replace('[/URL]', '')
        return data

    def relay_message(self, user, msg):
        msg = self.encode(msg)
        user = self.encode(user)

        self.send_raw("clientupdate client_nickname=[Bridge]" + user)
        self.send_raw("sendtextmessage targetmode=2 target=1 msg=" + msg)
        self.send_raw("clientupdate client_nickname=" + self._nick)

    def relay_global_message(self, user, msg):
        msg = self.encode(msg)
        user = self.encode(user)

        self.send_raw("clientupdate client_nickname=[Bridge]" + user)
        self.send_raw("sendtextmessage targetmode=3 target=1 msg=" + msg)
        self.send_raw("clientupdate client_nickname=" + self._nick)

    def send_text(self, text):
        if not text:
            return

        text = self.encode(text)
        self.send_raw("sendtextmessage targetmode=2 target=1 msg=" + text)

    def send_raw(self, text):
        msg = "%s\n" % (text, )
        self._send_queue.put(msg)

    def poll(self):
        if self._recv_queue.empty():
            return None

        return self._recv_queue.get()

    def process_send_queue(self):
        while self._running:
            if self._connected and not self._send_queue.empty():
                self._socket.send(bytes(self._send_queue.get(), 'UTF-8'))
                self._send_queue.task_done()

            time.sleep(0.01)

    def get_channel_name_with_relation(self, channel, channel_name=""):
        if(channel["pid"] != "0"):
            channel_name = " - " + self.decode(channel["channel_name"]) + channel_name
            return self.get_channel_name_with_relation(self._channel_map[channel["pid"]], channel_name)
        else:
            return self.decode(channel["channel_name"]) + channel_name

    def disconnect(self):
        print("[TS] Disconnecting")
        self._running = False
        self._connected = False
        self._socket.close()
        self._send_thread.join()
        self._recv_thread.join()

    def running(self):
        return self._running

    def client_map(self):
        return self._client_map

    def channel_map(self):
        return self._channel_map
