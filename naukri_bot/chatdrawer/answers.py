"""Decide what to put in a widget. No DOM access here — fillers.py acts, engine.py verifies.

One rule set for every widget that carries options (radio, checkbox, select, chips): the v1
policy stack via `hooks.classify_radio` (safe-default location/consent matches, PII/legal/
employer traps -> discard) and only then the LLM. Free-text widgets go through
`hooks.text_answer`, which already knows booleans, years-of-experience, the QA dictionary and
DOB (a single "DD/MM/YYYY" field, patched into v1 alongside this module). Date controls that
aren't a single text field (day/month/year selects or inputs) are answered here directly from
config, because v1 has no equivalent — this is new coverage, not reused.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

DOB_CODE = "DOB_MISSING"
POLICY_CODE = "POLICY"
STALE_PAIR_CODE = "STALE_PAIR"
NO_ANSWER_CODE = "NO_ANSWER"
UNSUPPORTED_CODE = "UNSUPPORTED_WIDGET"


@dataclass
class Answer:
    value: str                 # for radio/checkbox/select/chips: the exact option text to pick
    source: str                 # "policy" | "llm" | "config" | "rules"
    parts: Optional[dict] = None  # date_split only: {"day": "06", "month": "06", "year": "2001"}
    values: Optional[List[str]] = None  # checkbox only: every option to tick (value = first of them)


@dataclass
class Discard:
    code: str
    detail: str = ""


def _dob_parts(config):
    dob = str((config.get("personal_info", {}) or {}).get("date_of_birth", "")).strip()
    if not dob:
        return None
    for sep in ("/", "-", "."):
        if sep in dob:
            bits = [b.strip() for b in dob.split(sep) if b.strip()]
            break
    else:
        return None
    if len(bits) != 3:
        return None
    day, month, year = bits  # config is documented as DD/MM/YYYY
    if len(year) == 2:
        year = ("20" if int(year) < 50 else "19") + year
    return {"day": day.zfill(2), "month": month.zfill(2), "year": year}


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]


def _match_date_option(options, role, parts):
    want = parts[role]
    for o in options:
        t = (o.get("text") or "").strip()
        if role == "month":
            if t.lower().startswith(_MONTHS[int(want) - 1][:3]):
                return t
            if t.lstrip("0") == want.lstrip("0"):
                return t
        elif t.lstrip("0") == want.lstrip("0") or t == want:
            return t
    return None


def _is_dob_question(q):
    ql = (q or "").lower()
    return "date of birth" in ql or " dob" in f" {ql}" or ql.startswith("dob")


def decide(bot, widget, hooks, config, loc_variants):
    kind = widget.get("kind")
    q = widget.get("q", "")

    if kind == "unknown":
        return Discard(UNSUPPORTED_CODE, f"no handler for this control: {q[:80]}")

    if kind == "date_split":
        parts_needed = [p.get("role") for p in widget.get("parts", [])]
        dob = _dob_parts(config)
        if not dob or not all(r in dob for r in parts_needed if r):
            return Discard(DOB_CODE, "personal_info.date_of_birth missing or unparseable in config")
        picked = {}
        for p in widget.get("parts", []):
            role = p.get("role")
            if not role:
                continue
            if p.get("options"):
                m = _match_date_option(p["options"], role, dob)
                if not m:
                    return Discard(DOB_CODE, f"no matching {role} option for {dob[role]}")
                picked[role] = m
            else:
                picked[role] = dob[role]
        return Answer(value="/".join(picked.get(r, "") for r in ("day", "month", "year")),
                      source="config", parts=picked)

    if kind in ("date", "date_text"):
        dob = _dob_parts(config)
        if not dob:
            return Discard(DOB_CODE, "personal_info.date_of_birth missing or unparseable in config")
        value = f"{dob['year']}-{dob['month']}-{dob['day']}" if kind == "date" \
            else f"{dob['day']}/{dob['month']}/{dob['year']}"
        return Answer(value=value, source="config")

    if kind in ("radio", "checkbox", "select", "chips"):
        options = [o.get("text", "") for o in widget.get("options", []) if o.get("text")]
        if not options:
            return Discard(NO_ANSWER_CODE, "no options parsed")
        if hooks.q_opts_mismatch(q, options):
            return Discard(STALE_PAIR_CODE, f"question/options look mismatched: {options[:4]}")
        if kind == "checkbox":
            # Multi-select. Personal facts come from config first (canary 2026-09-15: a single
            # LLM pick answered "What are the languages you know?" with only 'Kannada').
            lower = {o.strip().lower(): o for o in options}
            if "language" in q.lower():
                langs = [str(x).strip().lower() for x in
                         ((config.get("personal_info", {}) or {}).get("languages") or []) if str(x).strip()]
                picks = [lower[l] for l in langs if l in lower]
                if picks:
                    return Answer(value=picks[0], source="config", values=picks)
            raw = hooks.llm_answer(f"{q} (Select ALL options that apply. Options: {' | '.join(options)}. "
                                   f"Reply with the exact option texts separated by ' | '.)", options=None, config=config)
            picks = []
            for part in re.split(r"\s*[|;,]\s*", raw or ""):
                o = lower.get(part.strip().strip('"\'').lower())
                if o and o not in picks:
                    picks.append(o)
            if picks:
                return Answer(value=picks[0], source="llm", values=picks)
        if _is_dob_question(q):
            dob = _dob_parts(config)
            if dob:
                m = _match_date_option(widget.get("options", []), "year", dob) if any(
                    (o.get("text") or "").strip().isdigit() and len(o.get("text", "").strip()) == 4
                    for o in widget.get("options", [])) else None
                if m:
                    return Answer(value=m, source="config")
        decision, payload = hooks.classify_radio(q, options, loc_variants)
        if decision == "select" and payload in options:
            return Answer(value=payload, source="policy")
        if decision == "discard":
            return Discard(POLICY_CODE, str(payload))
        pick = hooks.llm_answer(q, options=options, config=config)
        if pick and pick in options:
            return Answer(value=pick, source="llm")
        return Discard(NO_ANSWER_CODE, "no rule or LLM answer matched an option")

    if kind in ("text", "textarea", "composer"):
        try:
            ans = hooks.text_answer(bot, q)
        except Exception as e:
            return Discard(NO_ANSWER_CODE, f"text_answer raised: {e}")
        if ans:
            # 2026-09-16: hooks.text_answer (_unattended_text_answer) stamps
            # bot._last_text_answer_source before returning so a fabrication-risk LLM answer
            # logs as src=llm, not src=rules -- previously every free-text answer, including
            # LLM output, was logged identically and indistinguishable in the watcher.
            src = getattr(bot, "_last_text_answer_source", None) or "rules"
            return Answer(value=str(ans), source=src)
        return Discard(NO_ANSWER_CODE, "no rule, QA-dictionary or LLM answer")

    return Discard(UNSUPPORTED_CODE, f"unhandled widget kind '{kind}'")
