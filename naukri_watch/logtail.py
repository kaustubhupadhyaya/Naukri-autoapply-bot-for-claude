"""Parse naukri_bot.log into typed events (shared by the live and postmortem modes).

Line format (run_naukri_unattended.py / main.py):
    2026-09-15 13:48:42,184 - INFO - <message>
Lines without a timestamp (==== separators, Selenium stacktraces) are continuations of the
previous event. The log is written live by the bot: it is only ever opened shared-read.
"""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

LINE_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) - ([A-Z]+) - (.*)$")

# (kind, pattern): first match wins. Patterns key on the words after an emoji, because some
# emoji carry an invisible U+FE0F variation selector.
MARKERS = [
    # chatdrawer v2 (naukri_bot/chatdrawer/__init__.py + engine.py); the "q#N" lines are an
    # end-of-drawer recap of the live "q kind=" lines and are ignored.
    ("v2_installed", r"chatdrawer v2 installed"),
    ("v2_outcome", r"^\[chat-v2\] outcome=(\w+) job=(\S+) reason='(.*)' answered=(\d+)"),
    ("v2_answer", r"^\[chat-v2\] q kind=(\w+) src=(\S+) verify=(\w+) ch=\S* ms=\d+ q='(.*)' a='(.*)'$"),
    ("v2_discard", r"^\[chat-v2\] discard: (\S+) - (.*)$"),
    ("v2_recap", r"^\[chat-v2\] q#\d+ "),
    ("tab_cleanup", r"tab cleanup took ([\d.]+)s"),
    ("run_start", r"Setting up high-speed browser"),
    ("cycle_start", r"ALL-DAY SEARCH CYCLE #(\d+)"),
    ("cooldown", r"Entering all-day cooldown|Next search cycle starts at|Rate limit pause"),
    ("search_keyword", r"Searching for: (.+)$"),
    ("search_page", r"^\W*Page (\d+)$"),
    ("candidates", r"Found (\d+) new Easy-Apply candidate"),
    ("no_new_jobs", r"No new jobs on this page|No jobs found on this page"),
    ("job_start", r"^Job (\d+)/(\d+)$"),
    ("job_loaded", r"^\U0001F4CB (.+) at (.+)$"),
    ("reload", r"Reloading page \(attempt|Page load timed out"),
    ("already_applied", r"Page shows already applied|Page already shows applied state"),
    ("apply_found", r"Found Easy Apply button"),
    ("apply_js", r"JS fallback clicked Apply control \('(.*)'\)|Apply control already clicked via JS fallback"),
    ("external_skip", r"No Easy Apply\W+external skipped"),
    ("instant_apply", r"Easy Apply completed instantly"),
    ("no_drawer", r"No chatbot drawer element"),
    ("drawer_found", r"Chatbot drawer found"),
    ("drawer_identity", r"Drawer identity: <(\w+)> id='([^']*)' class='([^']*)'"),
    ("answer_text", r"^Chatbot Q: '(.*)' -> A: '(.*)'$"),
    ("answer_radio", r"^Chatbot radio: '(.*)' -> '(.*)' \((LLM|safe default)\)$"),
    ("answer_chip", r"^Chatbot chip clicked(?: \(using existing resume\))?: '(.*?)'(?: -> '(.*)')?$"),
    ("answer_select", r"^Chatbot select: '(.*)' -> '(.*)'$"),
    ("unanswered", r"Chatbot radio UNANSWERED/DISCARDED: '(.*)'|Mandatory question unanswered: '(.*)'"),
    ("opts_mismatch", r"Question/options mismatch \(stale q\): '(.*)' vs (\[.*?\])"),
    ("llm_answer", r"\[([^\]]+)\]: Q='(.*)' -> (?:Chosen Option|Answer)='(.*)'"),
    ("llm_failed", r"\[AI Answering Failed\]|Gemini API error"),
    ("resume_attach", r"Resume file attached via input\[type=file\].*verified files=(-?\d+)"),
    ("resume_fail", r"files\.length=0|Resume file input not"),
    ("save_disabled", r"Save present but disabled"),
    ("save_hold", r"Open question\(s\) awaiting answers"),
    ("save_click", r"Chatbot questions answered\W+Clicking Save now"),
    ("save_page_wide", r"Found Save button\W+waiting for enabled state"),
    ("save_target", r"Save target: <(\w+)> text='([^']*)' class='([^']*)'"),
    ("save_retry", r"Drawer still open after Save click"),
    ("rejected", r"Application rejected due to incomplete information: '(.*)'"),
    ("unconfirmed", r"NO applied-state evidence"),
    ("confirmed_drawer", r"Chatbot application submitted & confirmed via Save"),
    ("confirmed_nodrawer", r"Save submission CONFIRMED|verification unclear\W+counting as applied|Submit form closed"),
    ("applied_despite", r"Page shows applied despite unconfirmed Save"),
    ("discard_dump", r"Discard drawer dump: '(.*)"),
    ("discard_nosave", r"Chatbot finished without confirmed Save submission"),
    ("drawer_close", r"Closing/canceling chatbot drawer"),
    ("job_discarded", r"Chatbot incomplete / rejected\W+discarding job"),
    ("no_modal", r"No modal form present"),
    ("submit_not_found", r"Could not find submit button"),
    ("app_failed", r"Application failed$"),
    ("app_success", r"Application (\d+) successful"),
    ("login", r"Login attempt|Already logged in|All login attempts failed|Failed to find email field"),
    ("driver_error", r"invalid session id|no such window|session not created|Renderer|web view not found"
                     r"|High-speed driver setup error|error managing MicrosoftEdge"),
]
_COMPILED = [(k, re.compile(p)) for k, p in MARKERS]

# Bot verdict per attempt, as the bot itself believed it (the watcher checks it against Naukri).
VERDICT_KINDS = {
    "confirmed_drawer": "bot_confirmed", "confirmed_nodrawer": "bot_confirmed_pagewide",
    "instant_apply": "bot_confirmed", "applied_despite": "bot_confirmed",
    "rejected": "bot_saw_oops", "unconfirmed": "bot_unconfirmed", "discard_nosave": "bot_discarded",
    "external_skip": "bot_external_skip", "already_applied": "bot_already_applied",
    "opts_mismatch": "bot_discarded", "unanswered": "bot_discarded", "submit_not_found": "bot_discarded",
}


@dataclass
class LogEvent:
    ts: float
    level: str
    kind: str
    msg: str
    groups: tuple = ()
    extra: list = field(default_factory=list)

    @property
    def clock(self):
        return datetime.fromtimestamp(self.ts).strftime("%H:%M:%S")

    def line(self, width=160):
        return f"{self.clock} {self.level[:4]} {self.msg}"[:width]


def classify(level, msg):
    for kind, rx in _COMPILED:
        m = rx.search(msg)
        if m:
            return kind, tuple(g for g in m.groups() if g is not None)
    if level in ("ERROR", "CRITICAL"):
        return "error", ()
    if level == "WARNING":
        return "warning", ()
    return "info", ()


def parse_line(line):
    m = LINE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    stamp, ms, level, msg = m.groups()
    ts = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp() + int(ms) / 1000.0
    kind, groups = classify(level, msg)
    return LogEvent(ts=ts, level=level, kind=kind, msg=msg, groups=groups)


def read_since(path, since_ts=0.0):
    """Whole-file scan (the log has no rotation); events at or after since_ts."""
    out, last = [], None
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.decode("utf-8", errors="replace")
            ev = parse_line(line)
            if ev is None:
                if last is not None and line.strip() and len(last.extra) < 12:
                    last.extra.append(line.rstrip()[:200])
                continue
            last = ev
            if ev.ts >= since_ts:
                out.append(ev)
    return out


class Follower:
    """Tail -f for the live log: shared-read, tolerant of partial lines and truncation."""

    def __init__(self, path, from_end=True):
        self.path = path
        self.pos = os.path.getsize(path) if (from_end and os.path.exists(path)) else 0
        self._buf = b""
        self._last = None

    def poll(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if size < self.pos:
            self.pos, self._buf = 0, b""
        if size == self.pos:
            return []
        with open(self.path, "rb") as fh:
            fh.seek(self.pos)
            data = fh.read(size - self.pos)
        self.pos = size
        data = self._buf + data
        lines = data.split(b"\n")
        self._buf = lines.pop()  # incomplete tail, finished next poll
        out = []
        for raw in lines:
            line = raw.decode("utf-8", errors="replace")
            ev = parse_line(line)
            if ev is None:
                if self._last is not None and line.strip() and len(self._last.extra) < 12:
                    self._last.extra.append(line.rstrip()[:200])
                continue
            self._last = ev
            out.append(ev)
        return out
