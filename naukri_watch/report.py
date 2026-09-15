"""report.md for a watch run: what failed, why, how often, and where the time went."""
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime

from .analysis import DB_PATH, SEVERITY_RANK, clock


def _pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]


def _db_counts(since_ts):
    if not os.path.exists(DB_PATH):
        return []
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)
        since = datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S")
        rows = con.execute("SELECT status, COUNT(*) FROM applied_jobs WHERE application_date >= ? "
                           "GROUP BY status ORDER BY 2 DESC", (since,)).fetchall()
        con.close()
        return rows
    except Exception:
        return []


def write(tracker, path, window_start, window_end, header):
    t = tracker
    inc = sorted(t.incidents, key=lambda i: (SEVERITY_RANK.get(i["severity"], 3), i["class"]))
    by_class = Counter((i["severity"], i["class"]) for i in t.incidents)
    causes = Counter((i["class"], i["cause"][:110]) for i in t.incidents if i["severity"] != "info")
    L = [f"# Naukri watch report - {header}", "",
         f"Window: {clock(window_start)} -> {clock(window_end)} ({(window_end - window_start) / 60:.1f} min), "
         f"mode: **{t.mode}**, attempts: **{len(t.attempts)}**, incidents: **{len(t.incidents)}**", ""]

    outcome = Counter()
    for a in t.attempts:
        truth = (a.server or {}).get("kind")
        outcome[(a.bot_verdict() or "none", truth or "-")] += 1
    L += ["## Outcomes (bot belief vs Naukri truth)", "",
          "| bot verdict | Naukri says | jobs |", "|---|---|---|"]
    L += [f"| {b} | {s} | {n} |" for (b, s), n in outcome.most_common()]
    if t.mode == "postmortem":
        L += ["", "_Postmortem has no page access, so 'Naukri says' is '-'. Run live mode to get Naukri's own verdict._"]

    L += ["", "## Incidents by class", "", "| severity | class | count |", "|---|---|---|"]
    L += [f"| {s} | {c} | {n} |" for (s, c), n in sorted(by_class.items(), key=lambda x: (SEVERITY_RANK.get(x[0][0], 3), -x[1]))]

    L += ["", "## Top causes (non-info)", ""]
    L += [f"- **{n}x** `{c}`: {cause}" for (c, cause), n in causes.most_common(15)] or ["- none"]

    gaps = defaultdict(list)
    for a in t.attempts:
        for lab, took, lim, _, _ in a.gaps():
            gaps[(lab, lim)].append(took)
    L += ["", "## Where the time goes (seconds per hop)", "", "| hop | n | p50 | p90 | max | limit | over |",
          "|---|---|---|---|---|---|---|"]
    for (lab, lim), v in gaps.items():
        L.append(f"| {lab} | {len(v)} | {_pct(v, 50):.1f} | {_pct(v, 90):.1f} | {max(v):.1f} | {lim} | "
                 f"{sum(1 for x in v if x > lim)} |")

    qs = Counter()
    kinds = {}
    for a in t.attempts:
        for x in a.answers:
            qs[x["q"][:90]] += 1
            kinds.setdefault(x["q"][:90], x["via"])
        for rec in a.questions.values():
            kinds[rec["q"][:90]] = rec["kind"]
            qs[rec["q"][:90]] += 0
    if qs:
        L += ["", "## Chat-window questions seen", "", "| question | control | times |", "|---|---|---|"]
        L += [f"| {q.replace('|', '/')} | {kinds.get(q, '?')} | {n} |" for q, n in qs.most_common(40)]

    L += ["", "## Attempts (latest 60)", "",
          "| # | start | job | apply | drawer | answers | bot verdict | Naukri | incidents |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a in t.attempts[-60:]:
        L.append(f"| {a.n} | {clock(a.marks['job_start'])} | {(a.title or a.job_id or '?')[:48].replace('|', '/')} | "
                 f"{'y' if 'apply_click' in a.marks else '-'} | {'y' if 'drawer_open' in a.marks else '-'} | "
                 f"{len(a.answers)} | {a.bot_verdict() or '-'} | {(a.server or {}).get('kind', '-')} | "
                 f"{', '.join(sorted({i['class'] for i in a.incidents if i['severity'] != 'info'})) or '-'} |")

    db = _db_counts(window_start)
    if db:
        L += ["", "## DB rows written in the window", "", "| status | rows |", "|---|---|"]
        L += [f"| {s} | {n} |" for s, n in db]

    L += ["", "## High-severity incidents (latest 25)", ""]
    for i in [x for x in inc if x["severity"] == "high"][-25:]:
        ev = {k: v for k, v in i["evidence"].items() if v not in (None, [], "", {})}
        L.append(f"- `{i['ts']}` **{i['class']}** {i.get('title') or i.get('job_id') or ''} - {i['cause']}")
        if ev:
            L.append(f"  - evidence: `{str(ev)[:600]}`")
    L += ["", "Files: `incidents.jsonl` (all findings + evidence), `questions.jsonl` (every chat question and its "
          "control type), `network.jsonl` (Naukri apply/chatbot requests, live only), `samples/` (drawer HTML per "
          "new format, live only)."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return path
