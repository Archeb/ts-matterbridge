from cmath import exp
import json
import requests
import threading
import time
import traceback

from queue import Queue


class MatterBridgeConnection:
    _send_queue = Queue()
    _recv_queue = Queue()
    _connected = False
    _running = False

    def __init__(self, api, authToken, gateway):
        self._api = api
        self._authHeaders = {'Authorization': 'Bearer ' + authToken}
        self._gateway = gateway

    def run(self):
        self._running = True

        self.connect()

        self._recv_thread = threading.Thread(target=self.listen)
        self._recv_thread.start()

    def connect(self):
        print("[MatterBridge] Connecting...")
        self._connected = False

        try:

            r = requests.get(self._api + "/stream",
                             headers=self._authHeaders, stream=True)

            if r.encoding is None:
                r.encoding = 'utf-8'

            rlines = r.iter_lines(decode_unicode=True)

            initInfo = json.loads(next(rlines))

            if(initInfo["event"] == "api_connected"):
                print("[MatterBridge] Connected")
                self._rlines = rlines
                self._connected = True
            else:
                print("[MatterBridge] Failed to connect")

        except:
            self._connected = False
            print("[MatterBridge] Failed to connect")
            print(traceback.format_exc())
            return

    def listen(self):
        while self._running:
            while not self._connected:
                self.connect()
                time.sleep(5)
            try:
                for line in self._rlines:
                    if line:
                        message = json.loads(line)
                        if(message["text"].startswith("!ts ")):
                            self._recv_queue.put(
                                ("GLOBALMSG", message["username"],
                                 message["protocol"],
                                 message["text"][4:]))
                        else:
                            self._recv_queue.put(
                                ("MSG", message["username"], message["protocol"], message["text"]))
            except:
                print(
                    "[MatterBridge] Error while fetching message from MatterBridge API")
                print(traceback.format_exc())
                self._connected = False
                return

    def relay_message(self, user, msg):
        if not self._connected:
            return

        data = {
            "text": msg,
            "username": "[TeamSpeak] " + user,
            "gateway": self._gateway
        }

        try:
            requests.post(self._api + "/message",
                          headers=self._authHeaders, json=data, timeout=1)
        except:
            print("[MatterBridge] Error while sending message to MatterBridge API")
            print(traceback.format_exc())

    def send_text(self, text):
        if not text:
            return

        data = {
            "text": text,
            "username": "[TeamSpeak Server] ",
            "gateway": self._gateway
        }
        try:
            requests.post(self._api + "/message",
                          headers=self._authHeaders, json=data, timeout=1)
        except:
            print("[MatterBridge] Error while sending message to MatterBridge API")
            print(traceback.format_exc())

    def send_raw(self, text):
        msg = "%s\r\n" % (text, )
        self._send_queue.put(msg)

    def poll(self):
        if self._recv_queue.empty():
            return None

        return self._recv_queue.get()

    def disconnect(self):
        self._running = False
        self._connected = False

    def running(self):
        return self._running
