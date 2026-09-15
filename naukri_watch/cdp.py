"""Minimal Chrome DevTools Protocol client for the watcher.

Attaches to the bot's Edge beside Selenium's own connection (Edge/Chrome accept several
CDP clients at once). The watcher only reads: it never sends input, navigates, focuses
the window, or pauses targets.
"""
import itertools
import json
import os
import queue
import threading
import urllib.request

import websocket


class CDPError(Exception):
    pass


class CDPClosed(Exception):
    pass


def devtools_port(profile_dir):
    """Port Edge wrote for this profile (msedgedriver launches it with --remote-debugging-port=0)."""
    with open(os.path.join(profile_dir, "DevToolsActivePort"), encoding="ascii") as fh:
        return int(fh.readline().strip())


def browser_ws_url(port, timeout=3):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as r:
        return json.load(r)["webSocketDebuggerUrl"]


class CDP:
    """Browser-level connection; page sessions are attached in flatten mode (sessionId)."""

    def __init__(self, ws_url, timeout=10):
        # suppress_origin: Edge rejects DevTools websockets whose Origin isn't allow-listed.
        self._ws = websocket.create_connection(
            ws_url, timeout=timeout, suppress_origin=True, enable_multithread=True)
        self._ws.settimeout(None)
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = threading.Lock()
        self.events = queue.Queue()
        self.closed = False
        self._reader = threading.Thread(target=self._read_loop, name="cdp-reader", daemon=True)
        self._reader.start()

    def _read_loop(self):
        try:
            while True:
                msg = json.loads(self._ws.recv())
                if "id" in msg:
                    with self._lock:
                        slot = self._pending.pop(msg["id"], None)
                    if slot is not None:
                        slot["msg"] = msg
                        slot["done"].set()
                else:
                    self.events.put(msg)
        except Exception:
            pass
        finally:
            self.closed = True
            with self._lock:
                for slot in self._pending.values():
                    slot["done"].set()
                self._pending.clear()
            self.events.put(None)  # wake the consumer

    def call(self, method, params=None, session_id=None, timeout=10):
        if self.closed:
            raise CDPClosed(method)
        mid = next(self._ids)
        slot = {"done": threading.Event(), "msg": None}
        with self._lock:
            self._pending[mid] = slot
        frame = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            frame["sessionId"] = session_id
        try:
            self._ws.send(json.dumps(frame))
        except Exception as e:
            with self._lock:
                self._pending.pop(mid, None)
            raise CDPClosed(f"{method}: {e}")
        if not slot["done"].wait(timeout):
            with self._lock:
                self._pending.pop(mid, None)
            raise CDPError(f"{method}: timed out after {timeout}s")
        msg = slot["msg"]
        if msg is None:
            raise CDPClosed(method)
        if "error" in msg:
            raise CDPError(f"{method}: {msg['error'].get('message')}")
        return msg.get("result", {})

    def evaluate(self, session_id, expression, timeout=10):
        """Run read-only JS in the page; returns the by-value result (None on JS exception)."""
        res = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": False,
            "silent": True}, session_id=session_id, timeout=timeout)
        if res.get("exceptionDetails"):
            return None
        return res.get("result", {}).get("value")

    def close(self):
        self.closed = True
        try:
            self._ws.close()
        except Exception:
            pass
