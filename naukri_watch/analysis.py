"""Attempt tracking and failure rules, shared by the live and postmortem modes.

One Attempt = one job: opened -> Apply clicked -> chat-drawer Q&A -> Save -> verdict.
The bot's log gives its *belief*; in live mode the page (multiApplyResp code in the result
URL, banners, drawer DOM, real clicks) gives Naukri's *truth*. Incidents are the places
where a phase broke, stalled, or belief and truth disagree.
"""
import json
import os
import re
import sqlite3
import time
from collections import Counter, deque
from datetime import datetime

from .logtail import VERDICT_KINDS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO, "naukri_jobs.db")

# multiApplyResp={"<jobId>": code} on /myapply/... result pages (both seen live 2026-09-15).
RESP_KINDS = {200: "applied", 202: "external_redirect"}

# (from_mark, to_mark, limit_s, label): the normal flow, and how long each hop may take.
FLOW = [
    ("job_start", "job_loaded", 25, "open job page"),
    ("job_loaded", "apply_click", 15, "job page -> Apply"),
    ("apply_click", "drawer_open", 12, "Apply -> chat drawer"),
    ("drawer_open", "first_answer", 25, "drawer -> first answer"),
    ("first_answer", "save_click", 120, "answering questions"),
    ("save_click", "verdict", 20, "Save -> verdict"),
    ("verdict", "end", 20, "verdict -> next job"),
]
MARK_ORDER = [f for f, _, _, _ in FLOW] + ["end"]
ANSWER_GAP = 30          # seconds between two consecutive answers
BOT_SILENT_S = 300       # no bot log line outside cooldowns
FILL_CHECK_DELAY = 4.0   # after the bot logs an answer, check the DOM registered it
SPECIAL_KINDS = {        # widget formats the v1 bot has no (or known-broken) handling for
    "date_split": "high", "date": "high", "date_text": "high", "checkbox": "medium",
    "file": "medium", "unknown": "high", "select": "info",
}
SEVERITY_RANK = {"high": 0, "medium": 1, "info": 2}


def qkey(t):
    return " ".join((t or "").lower().split())[:90]


def same_q(a, b):
    ka, kb = qkey(a), qkey(b)
    if not ka or not kb:
        return False
    n = min(len(ka), len(kb), 50)
    return ka[:n] == kb[:n] or ka in kb or kb in ka


def clock(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def server_verdict(snap):
    resp = snap.get("applyResp") or {}
    code = None
    if resp:
        code = next(iter(resp.values()))
        try:
            code = int(code)
        except (TypeError, ValueError):
            pass
    banners = snap.get("banners") or []
    pick = lambda k: next((b["text"] for b in banners if b["kind"] == k), "")
    rej, red, ok = pick("reject"), pick("redirect"), pick("success")
    if rej or code == 406:  # 406 = "Oops! ... incomplete information" (seen live 2026-09-15)
        kind = "rejected"
    elif red or code == 202:
        kind = "external_redirect"
    elif ok or code == 200:
        kind = "applied"
    elif code is not None:
        kind = f"code_{code}"
    else:
        kind = "unknown"
    return {"kind": kind, "code": code, "banner": rej or red or ok, "url": snap.get("url", "")[:220]}


class Attempt:
    def __init__(self, n, ts, job_id=None, title="", url=None):
        self.n, self.job_id, self.title, self.url = n, job_id, title, url
        self.marks = {"job_start": ts}
        self.answers = []           # {ts, q, a, via}
        self.questions = {}         # live: qkey|kind -> widget record
        self.log = deque(maxlen=60)
        self.bot_verdicts = []
        self.server = None
        self.apply_seen = {}        # control kind -> first ts it was visible
        self.apply_inventory = []
        self.clicks = []
        self.flags = set()
        self.last_drawer = None
        self.pre_save_drawer = None
        self.pending_checks = []    # (due_ts, answer)
        self.stalled = set()
        self.incidents = []
        self.ended = None

    def mark(self, name, ts):
        if name not in self.marks:
            self.marks[name] = ts

    def last_mark(self):
        best = None
        for m in MARK_ORDER:
            if m in self.marks and (best is None or self.marks[m] >= self.marks[best]):
                best = m
        return best

    def bot_verdict(self):
        order = ["bot_confirmed", "bot_confirmed_pagewide", "bot_saw_oops", "bot_unconfirmed",
                 "bot_discarded", "bot_external_skip", "bot_already_applied"]
        for v in order:
            if v in self.bot_verdicts:
                return v
        return None

    def gaps(self):
        out = []
        for f, t, lim, lab in FLOW:
            if f in self.marks and t in self.marks:
                out.append((lab, self.marks[t] - self.marks[f], lim, f, t))
        return out

    def label(self):
        t = (self.title or "").strip()
        return f"job {self.job_id or '?'} \"{t[:60]}\"" if t else f"job {self.job_id or '?'}"


class Tracker:
    def __init__(self, run_dir, mode, echo=True):
        self.run_dir, self.mode, self.echo = run_dir, mode, echo
        os.makedirs(os.path.join(run_dir, "samples"), exist_ok=True)
        self._inc = open(os.path.join(run_dir, "incidents.jsonl"), "a", encoding="utf-8")
        self._qs = open(os.path.join(run_dir, "questions.jsonl"), "a", encoding="utf-8")
        self._net = open(os.path.join(run_dir, "network.jsonl"), "a", encoding="utf-8")
        self.attempts, self.incidents = [], []
        self.cur = None
        self.recent = deque(maxlen=40)
        self.last_log_ts = None
        self.in_cooldown = False
        self.silent_flagged = False
        self.pending_job_start = None
        self.formats_seen = set()
        self.want_html = False
        self.pending_requests = {}
        self.t0 = time.time()

    # ------------------------------------------------------------------ output
    def emit(self, cls_, sev, cause, attempt=None, **evidence):
        a = attempt if attempt is not None else self.cur
        inc = {"ts": clock(evidence.pop("ts", time.time())), "class": cls_, "severity": sev, "cause": cause,
               "job_id": a.job_id if a else None, "title": (a.title if a else "")[:100], "evidence": evidence}
        self.incidents.append(inc)
        if a is not None:
            a.incidents.append(inc)
        self._inc.write(json.dumps(inc, ensure_ascii=False, default=str) + "\n")
        self._inc.flush()
        if self.echo:
            who = f" {a.label()}" if a else ""
            print(f"{inc['ts']} [{sev.upper():6}] {cls_}{who} - {cause}", flush=True)
        return inc

    def question_record(self, rec):
        self._qs.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._qs.flush()

    def network_record(self, rec):
        self._net.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._net.flush()

    # ---------------------------------------------------------- attempt edges
    def start_attempt(self, ts, job_id=None, title="", url=None):
        if self.cur is not None and self.cur.ended is None:
            self.end_attempt(ts, "next job")
        a = Attempt(len(self.attempts) + 1, ts, job_id, title, url)
        if self.pending_job_start and ts - self.pending_job_start < 90:
            a.marks["job_start"] = self.pending_job_start
        self.pending_job_start = None
        self.attempts.append(a)
        self.cur = a
        return a

    def end_attempt(self, ts, reason):
        a = self.cur
        if a is None or a.ended is not None:
            return
        a.ended = ts
        a.mark("end", ts)
        self._judge(a, reason)
        self._record_questions(a)

    # --------------------------------------------------------------- log feed
    def on_log(self, ev):
        self.recent.append(ev)
        prev_ts, self.last_log_ts = self.last_log_ts, ev.ts
        if self.silent_flagged:
            self.silent_flagged = False
        k, g = ev.kind, ev.groups
        if k == "run_start" and prev_ts is not None and self.mode == "postmortem":
            last = [e for e in list(self.recent)[:-1]][-4:]
            if not any(e.kind in ("app_failed", "app_success", "cooldown") for e in last[-2:]):
                self.emit("BOT_RESTARTED", "medium", "bot relaunched with no clean exit line (silent death)",
                          attempt=None, ts=ev.ts, last_lines=[e.line() for e in last])
        if k == "cooldown":
            self.in_cooldown = True
        elif k in ("cycle_start", "search_keyword", "job_start"):
            self.in_cooldown = False

        if k == "job_start":
            if self.mode == "postmortem":
                self.start_attempt(ev.ts)
            else:
                self.pending_job_start = ev.ts
            return
        if k in ("cycle_start", "search_page", "run_start") and self.mode == "postmortem":
            if self.cur is not None and self.cur.ended is None:
                self.end_attempt(ev.ts, "search resumed")
            return
        a = self.cur
        if a is None or a.ended is not None:
            if k == "driver_error":
                self.emit("BOT_DRIVER_ERROR", "high", ev.msg[:160], attempt=None, ts=ev.ts)
            return
        a.log.append(ev)
        if k == "job_loaded":
            a.mark("job_loaded", ev.ts)
            title, company = (g + ("", ""))[:2]
            a.title = title if company == "Unknown" else f"{title} @ {company}"
            m = re.search(r"(\d{9,})", title)
            if m and not a.job_id:
                a.job_id = m.group(1)
        elif k in ("apply_found", "apply_js"):
            a.mark("apply_click", ev.ts)
        elif k == "drawer_found":
            a.mark("drawer_open", ev.ts)
        elif k == "no_drawer":
            a.flags.add("no_drawer")
        elif k.startswith("answer_"):
            q, ans = (g + ("", ""))[:2]
            if k == "answer_chip" and len(g) == 1:
                q, ans = "(resume/chip)", g[0]
            rec = {"ts": ev.ts, "q": q, "a": ans, "via": k[7:]}
            a.answers.append(rec)
            a.mark("first_answer", ev.ts)
            a.marks["last_answer"] = ev.ts
            if self.mode == "live":
                a.pending_checks.append((ev.ts + FILL_CHECK_DELAY, rec))
        elif k in ("save_click", "save_page_wide"):
            a.mark("save_click", ev.ts)
            if k == "save_page_wide":
                a.flags.add("pagewide_save")
        elif k == "discard_dump":
            body = g[0] if g else ""
            if 'Applied to "' in body:
                a.flags.add("dump_applied")
            if "Oops!" in body or "not accepted due to incomplete" in body:
                a.flags.add("dump_oops")
        elif k == "drawer_close":
            a.flags.add("bot_closed_drawer")
            a.marks["drawer_close"] = ev.ts
        elif k == "resume_fail":
            if "resume_fail" not in a.flags:
                a.flags.add("resume_fail")
                self.emit("RESUME_NOT_ATTACHED", "medium", "resume file input reported files.length=0", ts=ev.ts,
                          line=ev.line())
        elif k == "opts_mismatch":
            self.emit("QUESTION_OPTIONS_MISMATCH", "medium", "bot paired a question with another question's options",
                      ts=ev.ts, line=ev.line())
        elif k == "unanswered":
            self.emit("UNANSWERED_QUESTION", "medium", "bot had no answer for a question", ts=ev.ts,
                      question=(g[0] if g else ""))
        elif k == "llm_failed":
            self.emit("LLM_FAILED", "medium", "no model answered", ts=ev.ts, line=ev.line())
        elif k == "driver_error":
            self.emit("BOT_DRIVER_ERROR", "high", ev.msg[:160], ts=ev.ts)
        elif k == "error" and "Application rejected" not in ev.msg:
            self.emit("BOT_ERROR", "medium", ev.msg[:160], ts=ev.ts)
        if k in VERDICT_KINDS:
            a.bot_verdicts.append(VERDICT_KINDS[k])
            a.mark("verdict", ev.ts)
        if k in ("app_failed", "app_success"):
            a.marks["end"] = ev.ts
            if self.mode == "postmortem":
                self.end_attempt(ev.ts, "bot finished job")

    # -------------------------------------------------------------- live feed
    def on_snapshot(self, snap, now):
        phase, job = snap.get("phase"), snap.get("jobId")
        a = self.cur
        if phase == "job" and job and (a is None or a.job_id != job or a.ended is not None):
            a = self.start_attempt(now, job, "", snap.get("url"))
        if a is None or a.ended is not None:
            return
        if phase == "job":
            if snap.get("ready") in ("interactive", "complete"):
                a.mark("job_loaded", now)
            a.apply_inventory = snap.get("applyControls") or a.apply_inventory
            for c in snap.get("applyControls") or []:
                if c.get("visible"):
                    a.apply_seen.setdefault(c["kind"], now)
            if not a.title and snap.get("title"):
                a.title = snap["title"][:100]
        d = snap.get("drawer")
        if d:
            a.mark("drawer_open", now)
            a.last_drawer = d
            self._note_formats(a, d, now)
            for w in d.get("widgets", []):
                key = qkey(w.get("q")) + "|" + w["kind"]
                rec = a.questions.get(key)
                if rec is None:
                    rec = a.questions[key] = {"q": w.get("q", ""), "kind": w["kind"], "first_seen": clock(now),
                                              "options": [o.get("text") for o in (w.get("options") or [])][:30],
                                              "parts": [p.get("role") for p in (w.get("parts") or [])],
                                              "required": w.get("required"), "filled_ever": False}
                if w.get("filled"):
                    rec["filled_ever"] = True
                    rec["value"] = w.get("value", "")
        if phase == "result":
            v = server_verdict(snap)
            if a.server is None or (a.server["kind"] in ("unknown",) and v["kind"] != "unknown") or \
                    (v["kind"] == "rejected" and a.server["kind"] != "rejected"):
                a.server = v
            a.mark("verdict", now)
            a.mark("server_verdict", now)
        elif phase in ("search", "other") and a.ended is None and ("job_loaded" in a.marks or a.server):
            self.end_attempt(now, "left job page")
        self._run_fill_checks(a, now)

    def on_dom_event(self, ev, now):
        a = self.cur
        if a is None or a.ended is not None or not isinstance(ev, dict):
            return
        el = ev.get("el") or {}
        text = (el.get("text") or "").strip().lower()
        if ev.get("t") == "click":
            a.clicks.append({"ts": clock(now), "trusted": ev.get("trusted"), "el": el})
            if el.get("inDrawer"):
                if text in ("save", "submit", "save & apply", "send", "next", "done"):
                    a.mark("save_click", now)
                    a.pre_save_drawer = a.last_drawer
                    self._check_save(a, now, ev)
                elif re.search(r"close|cross", (el.get("cls") or "").lower()) or text in ("close", "x", "×"):
                    a.flags.add("drawer_closed_click")
                    a.marks["drawer_close"] = now
            elif "company site" in text:
                a.flags.add("clicked_external")
                a.mark("apply_click", now)
            elif text in ("apply", "apply now", "easy apply", "i am interested") or el.get("id") == "apply-button":
                a.mark("apply_click", now)
                a.flags.add("clicked_easy")
            elif text == "save" and not el.get("inDrawer"):
                a.flags.add("clicked_page_save")
        elif ev.get("t") == "change" and el.get("type") == "file":
            a.flags.add("file_chosen")
            self.emit("RESUME_FILE_CHOSEN", "info", f"file input got {ev.get('files')} file(s) {ev.get('names')}",
                      ts=now, trusted=ev.get("trusted"))

    def on_network(self, rec, now):
        self.network_record(rec)
        a = self.cur
        st = rec.get("status") or 0
        if rec.get("failed") or st >= 400:
            self.emit("NAUKRI_HTTP_ERROR", "medium", f"{rec.get('method')} {rec.get('path')} -> {st or rec.get('failed')}",
                      ts=now, body=(rec.get("body") or "")[:600])
        if a is not None and a.ended is None and re.search(r"upload|resume", rec.get("path", ""), re.I) \
                and rec.get("method") == "POST":
            a.flags.add("upload_request")

    def on_new_tab(self, url, now):
        if self.cur is not None and self.cur.ended is None:
            self.cur.flags.add("new_tab")
            self.emit("NEW_TAB_OPENED", "medium", f"a new tab opened during the attempt: {url[:120]}", ts=now)

    def on_browser(self, up, now, detail=""):
        if up:
            self.emit("BROWSER_ATTACHED", "info", detail or "attached to the bot's Edge", attempt=None, ts=now)
        else:
            self.emit("BROWSER_GONE", "high", detail or "bot's Edge is not reachable (bot restarted or crashed)",
                      attempt=None, ts=now)

    def tick(self, now):
        if self.last_log_ts and not self.in_cooldown and not self.silent_flagged \
                and now - self.last_log_ts > BOT_SILENT_S:
            self.silent_flagged = True
            self.emit("BOT_SILENT", "high", f"no bot log line for {int(now - self.last_log_ts)}s outside a cooldown",
                      attempt=None, ts=now, last_lines=[e.line() for e in list(self.recent)[-5:]])
        a = self.cur
        if a is None or a.ended is not None:
            return
        self._run_fill_checks(a, now)
        last = a.last_mark()
        nxt = next(((t, lim, lab) for f, t, lim, lab in FLOW if f == last), None)
        if nxt is None:
            return
        base = a.marks[last]
        limit, label = nxt[1], nxt[2]
        if last == "first_answer" and a.answers:
            gap_from_answer = now - a.answers[-1]["ts"]
            if gap_from_answer > ANSWER_GAP and ("answer", len(a.answers)) not in a.stalled:
                a.stalled.add(("answer", len(a.answers)))
                self._stall(a, now, f"waiting after answer #{len(a.answers)}", gap_from_answer, ANSWER_GAP)
        if now - base > limit and last not in a.stalled:
            a.stalled.add(last)
            self._stall(a, now, label, now - base, limit)

    def finish(self, now):
        if self.cur is not None and self.cur.ended is None:
            self.end_attempt(now, "watch ended")
        for fh in (self._inc, self._qs, self._net):
            try:
                fh.close()
            except Exception:
                pass

    # ------------------------------------------------------------- internals
    def _stall(self, a, now, label, took, limit):
        silent = now - self.last_log_ts if self.last_log_ts else None
        d = a.last_drawer or {}
        hints = self._gap_hints(a, a.marks.get(a.last_mark(), now), now)
        self.emit("STALL", "high" if took > 3 * limit else "medium",
                  f"{label}: {int(took)}s (limit {limit}s) - {hints}", ts=now,
                  bot_log_silent_s=None if silent is None else int(silent),
                  last_lines=[e.line() for e in list(a.log)[-4:]],
                  drawer_busy=d.get("busy"), drawer_quiet_ms=d.get("quietMs"),
                  pending_naukri_requests=len(self.pending_requests))

    def _gap_hints(self, a, t0, t1):
        inside = [e for e in a.log if t0 <= e.ts <= t1]
        kinds = Counter(e.kind for e in inside)
        hints = []
        if kinds.get("llm_answer") or kinds.get("llm_failed"):
            hints.append(f"LLM calls x{kinds.get('llm_answer', 0) + kinds.get('llm_failed', 0)}")
        if kinds.get("save_disabled") or kinds.get("save_hold"):
            hints.append("bot holding Save (settle/open-question gates)")
        if kinds.get("reload"):
            hints.append("page reloads")
        if kinds.get("drawer_close"):
            hints.append("closing the drawer")
        if not inside:
            hints.append("bot wrote nothing: blocked in a call (page load, implicit wait, HTTP timeout, tab switch)")
        return "; ".join(hints) or f"{len(inside)} log lines, none explain it"

    def _note_formats(self, a, d, now):
        sig = d.get("sig")
        kinds = sorted({w["kind"] for w in d.get("widgets", [])})
        if sig and sig not in self.formats_seen:
            self.formats_seen.add(sig)
            self.want_html = sig
            self.emit("NEW_DRAWER_FORMAT", "info", f"drawer widgets: {', '.join(kinds) or 'none'}", ts=now, sig=sig)
        for w in d.get("widgets", []):
            sev = SPECIAL_KINDS.get(w["kind"])
            key = ("kind", w["kind"], qkey(w.get("q")))
            if sev and key not in self.formats_seen:
                self.formats_seen.add(key)
                extra = {}
                if w["kind"] == "date_split":
                    extra["parts"] = [(p.get("role"), p.get("tag"), p.get("placeholder")) for p in w.get("parts", [])]
                if w["kind"] == "unknown":
                    extra["html"] = w.get("html", "")[:800]
                self.emit(f"FORMAT_{w['kind'].upper()}", sev,
                          f"'{(w.get('q') or '')[:80]}' uses a {w['kind']} control", ts=now, sig=sig, **extra)

    def _find_widget(self, d, q):
        ws = [w for w in (d or {}).get("widgets", []) if w["kind"] != "chips"]
        hit = [w for w in ws if same_q(w.get("q"), q)]
        if hit:
            return hit[-1]
        return ws[-1] if len(ws) == 1 else None

    def _run_fill_checks(self, a, now):
        if not a.pending_checks:
            return
        due = [c for c in a.pending_checks if c[0] <= now]
        a.pending_checks = [c for c in a.pending_checks if c[0] > now]
        d = a.last_drawer
        for _, ans in due:
            if not d:
                continue
            active = d.get("activeQuestion") or ""
            w = self._find_widget(d, ans["q"])
            still_asking = same_q(active, ans["q"])
            if w is None:
                continue
            kind = w["kind"]
            if kind in ("radio", "checkbox", "select", "date", "date_split", "date_text") and not w.get("filled"):
                self.emit("FILL_NOT_REGISTERED", "high",
                          f"bot logged '{ans['a'][:40]}' for a {kind} but the control shows nothing selected",
                          ts=now, question=ans["q"][:160], options=[o.get("text") for o in (w.get("options") or [])][:12])
            elif kind in ("composer", "text", "textarea") and still_asking:
                if w.get("filled"):
                    self.emit("ANSWER_NOT_SENT", "high", f"answer typed but never sent: '{w.get('value', '')[:40]}'",
                              ts=now, question=ans["q"][:160])
                elif not any(m["who"] == "user" and same_q(m["text"], ans["a"]) for m in d.get("messages", [])[-3:]):
                    self.emit("FILL_NOT_REGISTERED", "high", f"bot logged '{ans['a'][:40]}' but nothing was typed/sent",
                              ts=now, question=ans["q"][:160])

    def _check_save(self, a, now, ev):
        d = a.last_drawer or {}
        open_ws = [w for w in d.get("widgets", [])
                   if w["kind"] not in ("chips", "file") and w.get("filled") is False
                   and not (w["kind"] == "composer" and not d.get("activeQuestion"))]
        if open_ws:
            self.emit("SAVE_WITH_EMPTY_FIELDS", "high",
                      f"Save clicked while {len(open_ws)} control(s) were empty: "
                      + "; ".join(f"{w['kind']} '{(w.get('q') or '')[:50]}'" for w in open_ws[:3]),
                      ts=now, trusted=ev.get("trusted"))

    def _unfilled(self, d):
        # "file" excluded to match _check_save: a resume input's filled state is unreliable
        # (files.length is often 0 even on a successful attach), so it's never cited as the
        # cause of a rejection — only a control we can actually verify empty is.
        return [{"kind": w["kind"], "q": (w.get("q") or "")[:120], "value": w.get("value", "")}
                for w in (d or {}).get("widgets", [])
                if w["kind"] not in ("chips", "file") and w.get("filled") is False]

    def _db_status(self, job_id):
        if not job_id or not os.path.exists(DB_PATH):
            return None
        try:
            con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)
            row = con.execute("SELECT status FROM applied_jobs WHERE job_id=?", (job_id,)).fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _judge(self, a, reason):
        now = a.ended
        bv = a.bot_verdict()
        sv = a.server["kind"] if a.server else None
        live = self.mode == "live"

        # 1. Apply never pressed
        if "apply_click" not in a.marks and "drawer_open" not in a.marks and not a.server:
            if live:
                seen = a.apply_seen
                if "applied" in seen:
                    self.emit("APPLY_NOT_PRESSED", "info", "already applied (page shows Applied)", a, ts=now)
                elif "easy" in seen:
                    lead = seen["easy"] - a.marks.get("job_loaded", a.marks["job_start"])
                    stay = now - seen["easy"]
                    self.emit("APPLY_NOT_PRESSED", "high",
                              f"Easy-Apply button was visible ({lead:.1f}s after load, {stay:.1f}s before leaving) "
                              f"but the bot never clicked it", a, ts=now, bot_verdict=bv,
                              inventory=a.apply_inventory, last_lines=[e.line() for e in list(a.log)[-4:]])
                elif "external" in seen:
                    self.emit("APPLY_NOT_PRESSED", "info", "external-only job (Apply on company site): policy skip",
                              a, ts=now)
                else:
                    self.emit("APPLY_NOT_PRESSED", "medium",
                              "no Apply control ever rendered while the bot was on the page (hydration/page load)",
                              a, ts=now, inventory=a.apply_inventory, bot_verdict=bv)
            elif "job_loaded" in a.marks:
                if bv == "bot_external_skip":
                    self.emit("APPLY_NOT_PRESSED", "info", "bot classified the job as external", a, ts=now)
                elif bv == "bot_already_applied":
                    self.emit("APPLY_NOT_PRESSED", "info", "already applied", a, ts=now)
                elif not bv:
                    self.emit("APPLY_NOT_PRESSED", "medium", "job page loaded but no Apply attempt was logged", a,
                              ts=now, last_lines=[e.line() for e in list(a.log)[-4:]])

        # 2. Wrong Apply control
        if sv == "external_redirect" or "clicked_external" in a.flags:
            self.emit("EXTERNAL_APPLY_CLICKED", "high",
                      "bot clicked 'Apply on company site': Naukri redirected to the employer site "
                      f"(multiApplyResp {a.server['code'] if a.server else '?'}); nothing was applied", a, ts=now,
                      bot_verdict=bv)

        # 3. Belief vs truth
        confirmed = bv in ("bot_confirmed", "bot_confirmed_pagewide")
        if live and confirmed and sv != "applied":
            self.emit("FALSE_CONFIRM", "high", f"bot counted it as applied; Naukri says {sv or 'nothing (no result page)'}",
                      a, ts=now, db_status=self._db_status(a.job_id), flags=sorted(a.flags))
        elif not live and bv == "bot_confirmed_pagewide":
            self.emit("FALSE_CONFIRM", "high",
                      "counted as applied via a page-wide 'Save' with no chat drawer (bookmark button); "
                      "no proof anything was submitted", a, ts=now)
        if (live and sv == "applied" and not confirmed) or "dump_applied" in a.flags:
            self.emit("FALSE_DISCARD", "high", "Naukri shows the application went through, but the bot discarded it",
                      a, ts=now, bot_verdict=bv, db_status=self._db_status(a.job_id))

        # 4. Rejection ("Oops! ... incomplete information")
        if sv == "rejected" or bv == "bot_saw_oops" or "dump_oops" in a.flags:
            unfilled = self._unfilled(a.pre_save_drawer or a.last_drawer)
            # Compare against Naukri's result page, not the bot's own log verdict: v1 logs
            # "no evidence" BEFORE it closes the drawer, and the close is what makes Naukri
            # submit the half-answered questionnaire (406). Live 2026-09-15: 3/3 rejections.
            closed_first = "drawer_close" in a.marks and \
                a.marks["drawer_close"] <= a.marks.get("server_verdict", a.marks.get("verdict", now))
            if closed_first:
                cause = "bot closed the chat drawer before Naukri's verdict (abandoned questionnaire)"
            elif unfilled:
                cause = "submitted with empty fields: " + "; ".join(f"{u['kind']} '{u['q'][:50]}'" for u in unfilled[:3])
            else:
                cause = "rejected for incomplete information; no empty field visible at Save (see answers)"
            self.emit("APPLICATION_REJECTED", "high", cause, a, ts=now,
                      banner=(a.server or {}).get("banner", ""), code=(a.server or {}).get("code"),
                      answers=[(x["q"][:80], x["a"][:40], x["via"]) for x in a.answers][-8:],
                      unfilled=unfilled, flags=sorted(a.flags))

        # 5. Apply clicked but no outcome at all
        if "apply_click" in a.marks and not bv and not a.server and reason != "watch ended":
            self.emit("NO_VERDICT", "medium", "Apply was clicked but neither the bot nor Naukri produced a verdict", a,
                      ts=now, last_lines=[e.line() for e in list(a.log)[-5:]])

        # 6. Stalls (postmortem only: live raises them as they happen)
        if not live:
            for lab, took, lim, f, t in a.gaps():
                if took > lim:
                    self.emit("STALL", "high" if took > 3 * lim else "medium",
                              f"{lab}: {int(took)}s (limit {lim}s) - {self._gap_hints(a, a.marks[f], a.marks[t])}",
                              a, ts=a.marks[t])

    def _record_questions(self, a):
        for rec in a.questions.values():
            bot = next((x for x in a.answers if same_q(x["q"], rec["q"])), None)
            self.question_record({"job_id": a.job_id, "title": a.title, **rec,
                                  "bot_answer": bot["a"] if bot else None, "bot_via": bot["via"] if bot else None,
                                  "server": (a.server or {}).get("kind")})
        if self.mode == "postmortem":
            for x in a.answers:
                self.question_record({"job_id": a.job_id, "title": a.title, "q": x["q"], "kind": x["via"],
                                      "bot_answer": x["a"], "at": clock(x["ts"])})
