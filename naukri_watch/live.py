"""Live mode: watch the running bot through its own Edge (CDP, read-only) + its log.

What it sends to the browser: Target discovery/attach, Runtime/Page/Network enable, one CDP
binding + a passive event recorder (recorder.js), and a ~15 ms read-only probe per second.
It never clicks, types, navigates, focuses, or pauses anything.
"""
import json
import os
import queue
import re
import time
from urllib.parse import urlparse

from . import logtail, report
from .analysis import Tracker
from .cdp import CDP, CDPClosed, CDPError, browser_ws_url, devtools_port

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO, "naukri_bot.log")
PROFILE_DIR = os.path.join(REPO, "browser_profile", "edge_default")
PROBE_SRC = open(os.path.join(REPO, "naukri_bot", "chatdrawer", "probe.js"), encoding="utf-8").read()
RECORDER_SRC = open(os.path.join(os.path.dirname(__file__), "recorder.js"), encoding="utf-8").read()
PROBE_EXPR = "(" + PROBE_SRC + ")({})"
PROBE_HTML_EXPR = "(" + PROBE_SRC + ")({withHtml: true})"

# Naukri XHRs worth keeping (apply flow, chatbot, uploads); never auth traffic.
INTERESTING = re.compile(r"apply|chatbot|questionnaire|workflow|upload|resume|myapply", re.I)
SECRETISH = re.compile(r"login|logout|auth|token|password|otp|captcha", re.I)


class Browser:
    """One CDP connection + one attached page session; reconnects when the bot restarts Edge."""

    def __init__(self, tracker):
        self.t = tracker
        self.cdp = None
        self.sid = None
        self.target = None
        self.up = None
        self.next_try = 0.0

    def ensure(self, now):
        if self.cdp is not None and not self.cdp.closed and self.sid:
            return True
        if now < self.next_try:
            return False
        self.next_try = now + 5
        try:
            if self.cdp is None or self.cdp.closed:
                self.cdp = CDP(browser_ws_url(devtools_port(PROFILE_DIR)))
                self.cdp.call("Target.setDiscoverTargets", {"discover": True})
            pages = [ti for ti in self.cdp.call("Target.getTargets")["targetInfos"]
                     if ti["type"] == "page" and ti["url"].startswith("http")]
            if not pages:
                return False
            self.target = pages[0]["targetId"]
            self.sid = self.cdp.call("Target.attachToTarget", {"targetId": self.target, "flatten": True})["sessionId"]
            for method, params in (("Runtime.enable", {}), ("Runtime.addBinding", {"name": "__nkw"}),
                                   ("Page.enable", {}), ("Page.addScriptToEvaluateOnNewDocument", {"source": RECORDER_SRC}),
                                   ("Network.enable", {"maxTotalBufferSize": 8_000_000, "maxResourceBufferSize": 2_000_000})):
                self.cdp.call(method, params, session_id=self.sid)
            self.cdp.evaluate(self.sid, RECORDER_SRC)
            if self.up is not True:
                self.t.on_browser(True, now, f"attached to {pages[0]['url'][:90]}")
            self.up = True
            return True
        except (OSError, CDPError, CDPClosed, KeyError, ValueError) as e:
            self.sid = None
            if self.up is not False:
                self.t.on_browser(False, now, f"bot's Edge not reachable ({type(e).__name__}: {str(e)[:80]})")
            self.up = False
            if self.cdp is not None:
                self.cdp.close()
                self.cdp = None
            return False

    def probe(self, with_html=False):
        raw = self.cdp.evaluate(self.sid, PROBE_HTML_EXPR if with_html else PROBE_EXPR, timeout=8)
        return json.loads(raw) if raw else None

    def drain(self, now, limit=400):
        if self.cdp is None:
            return
        for _ in range(limit):
            try:
                msg = self.cdp.events.get_nowait()
            except queue.Empty:
                return
            if msg is None:
                self.sid = None
                return
            self._handle(msg, now)

    def _handle(self, msg, now):
        m, p, sid = msg.get("method"), msg.get("params", {}), msg.get("sessionId")
        if m == "Runtime.bindingCalled" and p.get("name") == "__nkw":
            try:
                self.t.on_dom_event(json.loads(p.get("payload") or "{}"), now)
            except ValueError:
                pass
        elif m == "Network.requestWillBeSent" and sid == self.sid:
            req = p.get("request", {})
            url = req.get("url", "")
            host = urlparse(url).netloc
            if "naukri.com" not in host or SECRETISH.search(url):
                return
            if p.get("type") not in ("XHR", "Fetch", "Document") and req.get("method") != "POST":
                return
            rec = {"ts": now, "method": req.get("method"), "path": urlparse(url).path[:160],
                   "query": urlparse(url).query[:300] if INTERESTING.search(url) else "", "type": p.get("type")}
            if INTERESTING.search(url) and req.get("postData"):
                rec["post"] = req["postData"][:2000]
            self.t.pending_requests[p["requestId"]] = rec
        elif m == "Network.responseReceived" and p.get("requestId") in self.t.pending_requests:
            self.t.pending_requests[p["requestId"]]["status"] = p.get("response", {}).get("status")
        elif m in ("Network.loadingFinished", "Network.loadingFailed") and p.get("requestId") in self.t.pending_requests:
            rec = self.t.pending_requests.pop(p["requestId"])
            if m == "Network.loadingFailed":
                if p.get("canceled"):
                    return
                rec["failed"] = p.get("errorText", "failed")
            elif INTERESTING.search(rec["path"] + rec.get("query", "")) and rec.get("type") != "Document":
                try:
                    body = self.cdp.call("Network.getResponseBody", {"requestId": p["requestId"]},
                                         session_id=self.sid, timeout=4)
                    if not body.get("base64Encoded"):
                        rec["body"] = body.get("body", "")[:4000]
                except (CDPError, CDPClosed):
                    pass
            rec["took_ms"] = int((now - rec["ts"]) * 1000)
            self.t.on_network(rec, now)
        elif m == "Target.targetCreated":
            ti = p.get("targetInfo", {})
            if ti.get("type") == "page" and ti.get("targetId") != self.target:
                self.t.on_new_tab(ti.get("url", ""), now)
        elif m in ("Target.targetDestroyed", "Target.detachedFromTarget"):
            if p.get("targetId") == self.target or p.get("sessionId") == self.sid:
                self.sid = None

    def close(self):
        if self.cdp is not None:
            try:
                if self.sid:
                    self.cdp.call("Target.detachFromTarget", {"sessionId": self.sid}, timeout=3)
            except (CDPError, CDPClosed):
                pass
            self.cdp.close()


def run(run_dir, minutes=None, poll_s=1.0):
    tracker = Tracker(run_dir, "live", echo=True)
    follower = logtail.Follower(LOG_PATH, from_end=True)
    br = Browser(tracker)
    start = time.time()
    deadline = start + minutes * 60 if minutes else None
    next_probe = next_tick = 0.0
    print(f"watching (Ctrl+C to stop){' for %d min' % minutes if minutes else ''}; run folder: {run_dir}", flush=True)
    try:
        while deadline is None or time.time() < deadline:
            now = time.time()
            for ev in follower.poll():
                tracker.on_log(ev)
            if br.ensure(now):
                br.drain(now)
                if now >= next_probe:
                    next_probe = now + poll_s
                    try:
                        snap = br.probe()
                        if snap:
                            tracker.on_snapshot(snap, now)
                            if tracker.want_html:
                                full = br.probe(with_html=True)
                                html = ((full or {}).get("drawer") or {}).get("html")
                                if html:
                                    with open(os.path.join(run_dir, "samples", f"drawer_{tracker.want_html}.html"),
                                              "w", encoding="utf-8") as fh:
                                        fh.write(f"<!-- {snap.get('url')} -->\n{html}")
                                tracker.want_html = False
                    except (CDPError, CDPClosed, ValueError):
                        br.sid = None
            if now >= next_tick:
                next_tick = now + 2
                tracker.tick(now)
            time.sleep(0.15)
    except KeyboardInterrupt:
        print("stopping...", flush=True)
    finally:
        end = time.time()
        br.close()
        tracker.finish(end)
        path = report.write(tracker, os.path.join(run_dir, "report.md"), start, end, "live")
    return tracker, path
