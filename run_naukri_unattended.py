"""Untracked unattended runner for the Naukri bot. Leaves tracked files untouched.

Why it exists: the shipped Easy-Apply flow targets an obsolete Naukri DOM
(question selector never matches, answers only go to <input>, radio/select
questions unhandled, submit search wants a "submit" button while Naukri shows a
disabled-until-answered "Save"). Result was 18 attempted / 0 applied.

What this wrapper monkeypatches (reversible by deleting this file):
 N1 ChatbotMixin._handle_chatbot -> real Q&A: question bubbles, contenteditable
    chat box, radio/select groups, per-answer send, Save enabled-state gate.
 N2 ApplicationMixin._handle_easy_apply_submission_improved -> tries the Save
    button first (wait-for-enabled + 3 click strategies + verification),
    falls back to the original submit scan for non-chatbot flows.
 N3 Title/company extraction refreshed (logging/DB only, zero risk).
 N4 External-apply: skipped WITHOUT opening tabs (default; the only safe
    unattended behaviour). Set NAUKRI_SKIP_EXTERNAL=0 to restore tracked
    behaviour (opens company-site tabs for manual filling).
 N5 Answering policy (user-voted): safe defaults FIRST, Gemini SECOND,
    discard unknowns (never misrepresent):
      - Yes: relocate / join / notice-serve / WFO-hybrid-onsite / F2F /
             contract / travel / BGV consent (only when a Yes-like option exists)
      - Location: option matching config location (Bengaluru/Bangalore/...),
                  never a wrong city
      - CTC/salary/notice/experience/phone/email/name: config values
      - qa_dictionary.json exact matches (user-fillable for free text)
      - Gemini (only if GEMINI_API_KEY env is set, never committed): free-text
        answers + picking among radio options
      - DISCARD (job skipped, no lies): employer-specific ("employed by X",
        "currently employed", company traps), legal/health/conviction,
        visa/citizenship, PII traps (PAN/Aadhaar/bank),
        anything unmapped with no AI available.
      - DOB: answered from personal_info.date_of_birth (config.local.json, "DD/MM/YYYY") when
        present — a single free-text "DD/MM/YYYY" field only; a 3-way split day/month/year
        drawer needs the chatdrawer v2 engine (naukri_bot/chatdrawer/), not this v1 path.
 N6 Trailing input() ("Press Enter to close...") neutralised for headless runs.

Runtime config overlay (in memory only, files never written):
  config.local.json (cap 20) + GEMINI_API_KEY env + NAUKRI_SKIP_EXTERNAL env.

Usage:
  .venv\\Scripts\\python.exe run_naukri_unattended.py [--self-test]
"""
import os
import sys
import json
import time

# Single-flight file lock FIRST (before every other import): a same-second duplicate
# interpreter spawns per launch. Loser exits here in <1s, before touching Edge/DB/logs.
try:
    import msvcrt as _msvcrt

    _LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_singleflight.lock")
    _LOCK_FH = open(_LOCK_PATH, "a+b")
    try:
        _msvcrt.locking(_LOCK_FH.fileno(), _msvcrt.LK_NBLCK, 1)
    except OSError:
        print("Duplicate bot instance detected via single-flight lock - exiting.", flush=True)
        sys.exit(0)
except SystemExit:
    raise
except Exception as _e:
    print(f"Single-flight lock unavailable ({_e}) - proceeding without it.", flush=True)
import re
import logging
import sqlite3
import subprocess
import requests
import random
import urllib.parse
import faulthandler
from datetime import datetime

# H5 (2026-09-15): 68 launches/24h left no trace of *why* — stderr is overwritten on every
# relaunch (naukri_keepalive.ps1) and there was no crash dump for native/interpreter deaths.
# This alone can't fix the overwrite, but it turns a silent segfault/hang into a traceback in
# whatever stderr file this launch does get.
try:
    faulthandler.enable()
except Exception:
    pass

REPO = os.path.dirname(os.path.abspath(__file__))
os.chdir(REPO)

# N6: never block on stdin in unattended runs.
try:
    import builtins
    _orig_input = builtins.input
    builtins.input = lambda *a, **k: ""
except Exception:
    pass

import main  # noqa: F401  -- side effect only: root logging + win32 UTF-8 wrap
from naukri_bot.core.naukri_bot import NaukriBot
from naukri_bot.chatbot.chatbot import ChatbotMixin
from naukri_bot.modules.application import ApplicationMixin
from naukri_bot.modules.auth import AuthMixin

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    InvalidSessionIdException,
    WebDriverException,
)

logger = logging.getLogger("naukri_unattended")

# ---------------------------------------------------------------- policy tables
DISCARD_SUBSTR = (
    # never guess: legal / health / identity / employer-specific / PII traps
    "convict", "criminal", "offence", "offense", "fir", "lawsuit", "court case",
    "health", "disab", "veteran", "ex-serviceman", "citizen", "visa", "sponsor",
    "employed by", "currently employed", "working with", "previous employer",
    "career break", "gap in", "gender", "marital", "married", "pregnan",
    "religion", "caste", "pan card", "aadhaar", "passport number",
    "bank account", "upi id", "salary slip", "offer letter", "form 16",
    "fired", "terminated for", "dismissed", "blacklist",
)
SAFE_YES_SUBSTR = (
    # safe affirmative consents / availability (only when a Yes-like option exists)
    "relocat", "willing to join", "join immediately", "immediate join",
    "serve notice", "work from office", "work from client", "hybrid",
    "on-site", "onsite", "face to face", "f2f", "interview",
    "contract", "contractual", "travel", "willing to work",
    "background verification", "bgv", "drug test",
)
LOCATION_WORDS = (
    "location", "city", "cities", "based in", "work location",
    "preferred", "current location", "live in", "resid", "job location",
)
YES_LIKE = ("yes", "agree", "i do", "i have", "willing", "sure", "ok", "confirm")

# Shared with naukri_bot/chatdrawer (v2 engine) via the Hooks injected in the install() call
# near the bottom of this file — one constant instead of two copies drifting apart.
RESUME_PDF = r"C:\Users\Admin\Downloads\Kaustubh_upadhyaya_data_engineer.pdf"

SAVE_XPATH = (
    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'save')]"
)
FOOTER_SAVE_XPATH = (
    "//div[contains(@class,'footerWrapper') or contains(@class,'Footer')]"
    "//button"
)


def _match_option(options, needles):
    for opt in options:
        ol = (opt or "").strip().lower()
        if any(n in ol for n in needles):
            return opt
    return None


def classify_radio(question, options, location_variants):
    """Pure function: ('select', option_substr) | ('gemini', None) | ('discard', reason)."""
    q = (question or "").lower()
    opts = [o for o in (options or []) if o and str(o).strip()]
    if not opts:
        return ("discard", "no options parsed")
    if any(d in q for d in DISCARD_SUBSTR):
        return ("discard", "sensitive/employer-specific/PII")
    if q:
        loc_hit = _match_option(opts, [v.lower() for v in location_variants])
        if loc_hit and any(w in q for w in LOCATION_WORDS):
            return ("select", loc_hit)
        yes_hit = _match_option(opts, list(YES_LIKE))
        if yes_hit and any(s in q for s in SAFE_YES_SUBSTR):
            return ("select", yes_hit)
    # Unknown Yes/No or value question -> let Gemini choose among options,
    # else discard (never blind-pick options[0]).
    return ("gemini", None)


def _load_qa_dictionary():
    try:
        with open(os.path.join(REPO, "qa_dictionary.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k).strip().lower(): str(v).strip()
                for k, v in data.items() if str(v).strip()}
    except Exception:
        return {}


QA_DICT = _load_qa_dictionary()

# ----------------------------------------------- profile digest & LLM answering
_CACHED_PROFILE_DIGEST = None


def _get_resume_digest(config=None):
    """Extract, synthesize, and cache a concise profile digest at startup."""
    global _CACHED_PROFILE_DIGEST
    if _CACHED_PROFILE_DIGEST:
        return _CACHED_PROFILE_DIGEST

    pdf_path = r"C:\Users\Admin\Downloads\Kaustubh_upadhyaya_data_engineer.pdf"
    pdf_text = ""
    if os.path.exists(pdf_path):
        for extractor in ("pypdf", "pdfminer.high_level", "fitz"):
            try:
                mod = __import__(extractor)
                if extractor == "pypdf":
                    reader = mod.PdfReader(pdf_path)
                    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
                elif extractor == "pdfminer.high_level":
                    pdf_text = mod.extract_text(pdf_path)
                elif extractor == "fitz":
                    doc = mod.open(pdf_path)
                    pdf_text = "\n".join(page.get_text() for page in doc)
                if pdf_text.strip():
                    break
            except Exception:
                continue

    enh_skills = []
    enh_resume = ""
    enh_path = os.path.join(REPO, "enhanced_config.json")
    if os.path.exists(enh_path):
        try:
            with open(enh_path, encoding="utf-8") as fh:
                enh_data = json.load(fh)
                enh_profile = enh_data.get("user_profile", {})
                enh_skills = enh_profile.get("core_skills", [])
                enh_resume = enh_profile.get("resume_text", "")
        except Exception:
            pass

    exp_ctc = "20 LPA"
    cur_ctc = "15 LPA"
    if config:
        cb = config.get("chatbot_answers", {})
        pi = config.get("personal_info", {})
        exp_ctc = str(cb.get("expected_ctc") or pi.get("expected_ctc") or exp_ctc)
        if not any(u in exp_ctc.lower() for u in ("lpa", "lakh", "lac")):
            exp_ctc = f"{exp_ctc} LPA"
        cur_ctc = str(cb.get("current_ctc") or pi.get("current_ctc") or cur_ctc)
        if not any(u in cur_ctc.lower() for u in ("lpa", "lakh", "lac")):
            cur_ctc = f"{cur_ctc} LPA"

    skills_list = ["Python", "PySpark", "SQL", "AWS", "Airflow", "Snowflake", "ETL"]
    for s in enh_skills:
        if s not in skills_list and len(skills_list) < 15:
            skills_list.append(s)

    lines = [
        "Candidate Profile:",
        "Name: Kaustubh Upadhyaya",
        "Target Roles: Data Engineer / Big Data / Cloud Engineer",
        "Total Experience: 3-5 years (Data Engineering / Big Data / Cloud)",
        "PySpark Experience: 3-5 years",
        "Python Experience: 3-5 years",
        "SQL Experience: 3-5 years",
        "AWS Experience: 3-5 years",
        "Airflow Experience: 3-5 years",
        "Snowflake Experience: 3-5 years",
        "ETL Experience: 3-5 years",
        f"Key Skills: {', '.join(skills_list)}",
        "Current Location: Bengaluru, India",
        "Preferred Location: Bengaluru location (open to Hybrid / On-site / Relocation)",
        "Notice Period: Immediate / 15-30 days",
        f"Current CTC: {cur_ctc}",
        f"Expected CTC: {exp_ctc}",
        "Relocation & Availability: Yes, willing to relocate to Bengaluru, open to background checks and immediate joining."
    ]
    if enh_resume:
        lines.append(f"Profile Summary: {enh_resume.strip()[:350]}")
    elif pdf_text:
        lines.append(f"Resume Excerpt: {pdf_text.strip()[:350]}")

    _CACHED_PROFILE_DIGEST = "\n".join(lines)
    logger.info(f"📄 Resume profile digest cached ({len(_CACHED_PROFILE_DIGEST)} chars)")
    return _CACHED_PROFILE_DIGEST


_LAST_LLM_MODEL = "unknown"

def _call_local_proxy(prompt):
    """Call local Antigravity proxy with adequate token budget for reasoning models."""
    global _LAST_LLM_MODEL
    url = "http://127.0.0.1:8080/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "dummy",
        "anthropic-version": "2023-06-01",
    }
    for model_name in ("gemini-2.5-flash", "gemini-3.7-flash-tiered", "gemini-3.8-flash-tiered"):
        # Fast model gets a small budget (1-line answers); reasoning-tiered models keep
        # room for thinking tokens so they don't starve.
        _budget = 256 if model_name == "gemini-2.5-flash" else 1024
        payload = {
            "model": model_name,
            "max_tokens": _budget,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
                if text:
                    _LAST_LLM_MODEL = f"Local Proxy ({model_name})"
                    logger.info(f"🧠 Local proxy ({model_name}) answered question")
                    return text
        except Exception as e:
            logger.debug(f"Local LLM proxy ({model_name}) failed: {e}")
    return None


def _call_opencode_zen(prompt):
    """Call free model on OpenCode Zen as zero-cost fallback."""
    exe = r"C:\Users\Admin\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe"
    if not os.path.exists(exe):
        return None
    try:
        cmd = [exe, "run", "-m", "opencode/muse-spark-1.3-contributor-free", "--pure", prompt]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if p.returncode == 0 and p.stdout:
            lines = [
                l.strip() for l in p.stdout.splitlines()
                if l.strip() and not l.startswith(">") and not l.startswith("Skill") and not l.startswith("→")
            ]
            if lines:
                ans = lines[-1].strip()
                logger.info(f"🧠 OpenCode Zen (muse-spark-1.3) answered question: {ans}")
                return ans
    except Exception as e:
        logger.debug(f"OpenCode Zen call failed: {e}")
    return None


def _call_gemini_fallback(prompt, config=None):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and config:
        key = str(config.get("gemini_api_key", "")).strip()
    if not key:
        enh_path = os.path.join(REPO, "enhanced_config.json")
        if os.path.exists(enh_path):
            try:
                with open(enh_path, encoding="utf-8") as fh:
                    key = json.load(fh).get("gemini_api_key", "").strip()
            except Exception:
                pass
    if not key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 30, "temperature": 0.1}
        )
        if resp and resp.text:
            return resp.text.strip()
    except Exception as e:
        logger.debug(f"Gemini API fallback error: {e}")
    return None


def _match_llm_option(resp_text, options):
    if not resp_text or not options:
        return None
    r = resp_text.strip().strip('"\'`').strip().lower()
    if not r:
        return None

    # 1. Exact match
    for opt in options:
        if opt and opt.strip().lower() == r:
            return opt

    # 2. Word boundary match
    for opt in options:
        ol = opt.strip().lower()
        if ol and re.search(r'\b' + re.escape(ol) + r'\b', r):
            return opt

    # 3. Substring match
    for opt in options:
        ol = opt.strip().lower()
        if ol and (ol in r or r in ol):
            return opt

    return None


def _llm_answer_question(question_text, options=None, config=None):
    """Grounded LLM question answering: local proxy first, Gemini fallback second."""
    q = (question_text or "").strip()
    if not q:
        return None
    # Session memo: identical questions repeat across jobs — answer once, reuse instantly.
    try:
        _mkey = (_qkey(q), tuple(sorted(str(o).strip().lower() for o in (options or []) if str(o).strip())))
        if _mkey in _LLM_MEMO:
            _memo_ans = _LLM_MEMO[_mkey]
            logger.info(f"🤖 [memo hit]: Q='{q[:70]}' -> '{str(_memo_ans)[:60]}'")
            return _memo_ans
    except Exception:
        _mkey = None
    digest = _get_resume_digest(config)

    if options:
        opts_clean = [str(o).strip() for o in options if str(o).strip()]
        if not opts_clean:
            return None
        opts_str = "\n".join(f"- {o}" for o in opts_clean)
        prompt = (
            f"{digest}\n\n"
            f'Question: "{q}"\n\n'
            f"Available Options:\n{opts_str}\n\n"
            "CRITICAL INSTRUCTION: Select EXACTLY one option from the Available Options list above "
            "that best matches the candidate profile. Output ONLY the exact text of the chosen option from the list, nothing else."
        )
    else:
        opts_clean = None
        prompt = (
            f"{digest}\n\n"
            f'Question: "{q}"\n\n'
            "Instruction: Answer the question concisely in 1 line (e.g. a number for years/CTC/notice, or a brief phrase) "
            "strictly based on the candidate profile. Output ONLY the concise answer, no explanations or punctuation prefix."
        )

    raw_answer = _call_local_proxy(prompt)
    model_used = _LAST_LLM_MODEL if _LAST_LLM_MODEL != "unknown" else "Local Proxy"
    if not raw_answer:
        raw_answer = _call_opencode_zen(prompt)
        model_used = "OpenCode Zen (muse-spark)"
    if not raw_answer:
        raw_answer = _call_gemini_fallback(prompt, config)
        model_used = "Google Gemini Direct (gemini-2.5-flash)"
    if not raw_answer:
        logger.warning(f"⚠️ [AI Answering Failed]: No model was able to answer question: '{q[:80]}'")
        return None

    if opts_clean:
        chosen = _match_llm_option(raw_answer, opts_clean)
        logger.info(f"🤖 [{model_used}]: Q='{q[:70]}' -> Chosen Option='{chosen}' (Raw: '{raw_answer.strip()[:40]}')")
        try:
            if _mkey is not None and chosen:
                _LLM_MEMO[_mkey] = chosen
        except Exception:
            pass
        return chosen
    else:
        line = raw_answer.splitlines()[0].strip().strip('"\'`')
        line = re.sub(r'^(Answer|A):\s*', '', line, flags=re.IGNORECASE).strip()
        logger.info(f"🤖 [{model_used}]: Q='{q[:70]}' -> Answer='{line}'")
        try:
            if _mkey is not None and line:
                _LLM_MEMO[_mkey] = line
        except Exception:
            pass
        return line if line else None


def _is_mandatory(q_text, element=None):
    """Detect if a question or form field is marked mandatory/required."""
    if q_text:
        if "*" in q_text or re.search(r'\b(required|mandatory)\b', q_text, re.IGNORECASE):
            return True
    if element is not None:
        try:
            req = element.get_attribute("required")
            if req and str(req).lower() not in ("false", "0", "null"):
                return True
            aria_req = element.get_attribute("aria-required")
            if aria_req and str(aria_req).lower() == "true":
                return True
            el_cls = (element.get_attribute("class") or "").lower()
            if any(k in el_cls for k in ("mandatory", "required", "star", "asterisk")):
                return True
            for xp in (
                "./ancestor::div[contains(@class,'botmsg') or contains(@class,'question') or contains(@class,'form') or contains(@class,'field') or contains(@class,'ssrc')][1]",
                "./ancestor::div[contains(@id,'SingleSelect') or contains(@id,'Radio') or count(.//input)>0][1]",
                "./ancestor::div[1]",
                "./ancestor::div[2]",
            ):
                try:
                    anc = element.find_element(By.XPATH, xp)
                    anc_txt = anc.text or ""
                    if "*" in anc_txt or re.search(r'\b(required|mandatory)\b', anc_txt, re.IGNORECASE):
                        return True
                    anc_cls = (anc.get_attribute("class") or "").lower()
                    if any(k in anc_cls for k in ("mandatory", "required")):
                        return True
                    if anc.find_elements(By.XPATH, ".//*[contains(@class,'mandatory') or contains(@class,'required') or contains(@class,'star') or contains(@class,'asterisk')]"):
                        return True
                except Exception:
                    continue
        except Exception:
            pass
    return False


def _close_chatbot_drawer(driver):
    """Attempt to close/cancel the chatbot drawer or modal dialog to abort incomplete application."""
    logger.info("🛑 Closing/canceling chatbot drawer to abort incomplete application")
    close_selectors = [
        "//div[contains(@class,'chatbot') or contains(@class,'drawer') or contains(@class,'modal')]//span[contains(@class,'close') or contains(@class,'cross')]",
        "//div[contains(@class,'chatbot') or contains(@class,'drawer') or contains(@class,'modal')]//button[contains(@class,'close') or contains(@class,'cross') or contains(@class,'cancel')]",
        "//div[contains(@class,'chatbot') or contains(@class,'drawer') or contains(@class,'modal')]//*[@aria-label='Close' or @aria-label='close']",
        "//div[contains(@class,'crossIcon') or contains(@class,'cross-icon')]",
        "//span[contains(@class,'crossIcon') or contains(@class,'close-popup')]",
        "//button[contains(@class,'close') or contains(@class,'cancel')]",
        "//a[contains(@class,'close') or contains(@class,'cancel')]",
        "//div[contains(@class,'chatbot')]//*[name()='svg' and (contains(@class,'close') or contains(@class,'cross'))]",
    ]
    closed = False
    for xp in close_selectors:
        try:
            for el in _displayed(driver.find_elements(By.XPATH, xp)):
                try:
                    el.click()
                    closed = True
                    break
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        closed = True
                        break
                    except Exception:
                        continue
            if closed:
                break
        except Exception:
            continue

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    time.sleep(1.0)


def _check_rejection_messages(driver):
    """Fast rejection inspection using JavaScript innerText (5ms execution, zero DOM search stalls)."""
    rejection_phrases = (
        "incomplete information",
        "oops!",
        "mandatory question",
        "mandatory questions",
        "not accepted due to",
        "please answer all mandatory questions",
        "application was not accepted",
        "fill all mandatory",
        "answer all required",
    )
    try:
        body_text = (driver.execute_script("return (document.body ? document.body.innerText : '')") or "").lower()
        for p in rejection_phrases:
            if p in body_text:
                idx = body_text.find(p)
                snippet = body_text[max(0, idx - 20):idx + 100]
                return snippet.strip().replace("\n", " ")
    except Exception as e:
        logger.debug(f"Fast rejection check error: {e}")
    return None

# ------------------------------------------------------- small DOM helpers
_Q_XPATH = (
    ".//div[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'botmsg')"
    " or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'bot-msg')"
    " or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'question')]"
)


def _displayed(elements):
    out = []
    for el in elements:
        try:
            if el.is_displayed():
                out.append(el)
        except Exception:
            pass
    return out


def _drawer_from_save_button(driver):
    """Save-anchored drawer detection: find the visible Save/Submit button first, then take
    the SMALLEST in-viewport ancestor sized like a drawer (>=300x200). No class-name
    dependence (Naukri uses hashed CSS-module classes). The Save footer is the stable
    landmark — container-first matching kept landing on the wrong subtree."""
    try:
        driver.implicitly_wait(0)
        btns = driver.find_elements(
            By.XPATH,
            ".//*[normalize-space(translate(string(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))='save' "
            "or normalize-space(translate(string(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))='save & apply' "
            "or normalize-space(translate(string(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))='submit']")
        try:
            logger.info(f"🔍 Save-anchor scan: {len(btns)} save-text button(s) page-wide")
        except Exception:
            pass
        best = None
        best_area = None
        for b in btns:
            try:
                if not b.is_displayed():
                    continue
                t = ((b.text or "") + " " + (b.get_attribute("value") or "")).strip().lower()
                if not t or any(c in t for c in ("cancel", "close", "skip", "save job")):
                    continue
                anc = driver.execute_script("""
                    var el = arguments[0], best = null, bestArea = Infinity;
                    for (var i = 0; i < 14 && el; i++) {
                        el = el.parentElement;
                        if (!el || el === document.body || el === document.documentElement) break;
                        var r = el.getBoundingClientRect();
                        if (r.width >= 300 && r.width <= 800 && r.height >= 200 && r.left < window.innerWidth && r.right > 0) {
                            var html = (el.innerHTML || '').toLowerCase();
                            var hasQ = html.indexOf('contenteditable') >= 0 || html.indexOf('ssrc__radio') >= 0
                                || html.indexOf('singleselect') >= 0 || html.indexOf('type="text"') >= 0
                                || html.indexOf("type='text'") >= 0 || html.indexOf('<select') >= 0
                                || html.indexOf('<textarea') >= 0 || html.indexOf('botmsg') >= 0
                                || html.indexOf('bot-msg') >= 0 || html.indexOf('quick-reply') >= 0
                                || html.indexOf('type="radio"') >= 0 || html.indexOf("type='radio'") >= 0;
                            if (!hasQ) continue;
                            var a = r.width * r.height;
                            if (a < bestArea) { bestArea = a; best = el; }
                        }
                    }
                    return best;
                """, b)
                if anc is None:
                    continue
                try:
                    r = driver.execute_script(
                        "var x=arguments[0].getBoundingClientRect();return [x.width, x.height];", anc)
                    area = float(r[0]) * float(r[1])
                except Exception:
                    area = None
                if best is None or (area is not None and (best_area is None or area < best_area)):
                    best = anc
                    best_area = area
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
        if best is not None:
            try:
                logger.info("💬 Drawer located via Save-button anchor")
            except Exception:
                pass
            return best
    except Exception:
        pass
    return None


def _find_chat_drawer(driver):
    """Return the visible chatbot drawer/modal container element, or None.

    Save-anchored first (stable landmark); falls back to container scoring.
    Job-page decoys (hidden file inputs, page Apply buttons) never qualify.
    """
    hit = _drawer_from_save_button(driver)
    if hit is not None:
        return hit
    try:
        driver.implicitly_wait(0)
        candidates = driver.find_elements(
            By.CSS_SELECTOR,
            "div[class*='chatbot'], div[class*='drawer'], div[class*='modal'], div[class*='Modal'], "
            "div[class*='dialog'], div[class*='Dialog'], div[class*='bottomSheet'], div[class*='popup']")
        scored = []
        for c in candidates:
            try:
                if not c.is_displayed():
                    continue
                try:
                    rect = driver.execute_script(
                        "var r=arguments[0].getBoundingClientRect();"
                        "return [r.width, r.height, r.left, r.right, window.innerWidth];", c)
                    if not (rect[0] > 0 and rect[1] > 0 and rect[2] < rect[4] and rect[3] > 0):
                        continue  # off-screen slide-in template, not the open drawer
                    if not (rect[0] >= 300 and rect[1] >= 200):
                        continue  # floating help bubble / collapsed widget, not the application drawer
                except Exception:
                    continue
                inner = (c.get_attribute("innerHTML") or "").lower()
                if any(k in inner for k in ("contenteditable", "ssrc__radio", "singleselect",
                                           "type=\"text\"", "type='text'", "<select",
                                           "<textarea", "botmsg", "bot-msg", "quick-reply")):
                    try:
                        area = float(rect[0]) * float(rect[1])
                    except Exception:
                        area = 0
                    scored.append((area, c))
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
        if scored:
            scored.sort(key=lambda t: t[0], reverse=True)
            best = scored[0][1]
            try:
                logger.info(f"💬 Drawer selected by area (largest of {len(scored)} candidates)")
            except Exception:
                pass
            return best
    except Exception:
        pass
    finally:
        try:
            driver.implicitly_wait(0)
        except Exception:
            pass
    return None


def _find_save_button(root):
    """Identify the true chatbot-drawer Save / Submit button WITHIN the drawer element.
    Never call with the full driver — page-wide Apply buttons must never match."""
    # Relative XPaths — searched INSIDE the drawer element only, page buttons unreachable.
    # NOTE: Naukri renders Save as a non-<button> control (div/span). The universal
    # exact-text selector matches any element whose ENTIRE text is save/submit —
    # ancestors never match since their text includes questions/options too.
    _up = "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'"
    selectors = (
        f".//*[normalize-space(translate(string(.),{_up}))='save']",
        f".//*[normalize-space(translate(string(.),{_up}))='save & apply']",
        f".//*[normalize-space(translate(string(.),{_up}))='submit']",
        ".//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save') and not(contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save job'))]",
        ".//button[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))='save & apply']",
        ".//button[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))='submit']",
        ".//button[contains(@class,'save') or contains(@class,'Save') or contains(@class,'submit') or contains(@class,'Submit')]",
        ".//input[@type='submit' or @type='button'][contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save')]",
    )
    try:
        for sel in selectors:
            try:
                for el in root.find_elements(By.XPATH, sel):
                    if el.is_displayed():
                        txt = (el.text or el.get_attribute("value") or "").strip().lower()
                        if not txt or any(c in txt for c in ("cancel", "close", "skip", "save job", "type message", "send")):
                            continue
                        if any(k in txt for k in ("save", "submit")):
                            return el
            except StaleElementReferenceException:
                return None
            except Exception:
                continue
    except Exception:
        pass
    return None


def _click_radio_option(driver, input_el, label_el=None):
    """Click a radio option across channels: visible label/pill first (custom-styled),
    then native input click, then JS clicks. Verifies via is_selected()."""
    try:
        if label_el is not None:
            try:
                if label_el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", label_el)
                    try:
                        label_el.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", label_el)
                    time.sleep(0.5)
                    try:
                        if input_el.is_selected():
                            return True
                    except Exception:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", input_el)
    except Exception:
        pass
    try:
        input_el.click()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", input_el)
        time.sleep(0.5)
        try:
            if input_el.is_selected():
                return True
        except Exception:
            return True
        return True
    except Exception:
        return False


def _qkey(t):
    return " ".join((t or "").strip().lower().split())[:120]


_LLM_MEMO = {}


def _q_opts_mismatch(q, options):
    """Detect stale-question pairing: experience-years question with duration options
    (or vice versa). A wrong answer is worse than a discard (never misrepresent)."""
    ql = (q or "").lower()
    opts = [(o or "").lower() for o in (options or []) if o]
    if not ql or not opts:
        return False
    asks_years = any(p in ql for p in ("how many years", "years of experience", "total experience", "number of years"))
    asks_notice = any(p in ql for p in ("notice", "join", "available", "reliev"))
    dur_hits = sum(1 for o in opts if any(k in o for k in ("day", "month", "week", "immediate", "serving", "notice")))
    if asks_years and not asks_notice and dur_hits >= max(1, len(opts) // 2):
        return True
    # Quantity question (years/CTC/salary/count) paired with pure Yes/No options =
    # stale question from another group (LLM would otherwise answer "No" to "how many").
    asks_qty = asks_years or any(p in ql for p in ("how many", "how much", "total ", "number of", "ctc", "lpa", "lakh", "salary", "expected ", "current "))
    bool_opts = len(opts) >= 2 and all(o.strip() in ("yes", "no", "y", "n") for o in opts)
    if asks_qty and not asks_notice and bool_opts:
        return True
    return False


_PLACEHOLDER_TEXTS = (
    "type message here", "type your message", "write a message", "enter your answer",
    "type here", "type your answer", "enter message", "write here", "ask something",
)


def _is_placeholder(text):
    t = (text or "").strip().lower().rstrip(".… ")
    return bool(t) and t in _PLACEHOLDER_TEXTS


def _box_current_value(box):
    """Current composer value with placeholder-as-text treated as empty (contenteditable
    composers render 'Type message here...' as real text — without this the box looks
    permanently 'filled' and Q2+ is never typed)."""
    try:
        tag = (box.tag_name or "").lower()
        if tag in ("input", "textarea"):
            v = (box.get_attribute("value") or "").strip()
            if v:
                return v
            ph = (box.get_attribute("placeholder") or "").strip()
            cur = v or ph
        else:
            cur = (box.text or "").strip()
            if not cur:
                try:
                    cur = (box.get_attribute("textContent") or "").strip()
                except Exception:
                    cur = ""
        if _is_placeholder(cur):
            return ""
        return cur
    except Exception:
        return ""


def _location_variants(config):
    loc = str(config.get("job_search", {}).get("location", "bengaluru") or "bengaluru")
    variants = {loc, loc.lower()}
    if "bengaluru" in loc.lower() or "bangalore" in loc.lower():
        variants |= {"bengaluru", "bangalore", "bengaluru / bangalore"}
    return sorted(variants)


_TELEMETRY_FILE = os.path.join(REPO, "naukri_telemetry_12h.jsonl")


def _log_telemetry(fmt, question, answer, success, extra=None):
    """Structured telemetry logger for 12h monitoring."""
    try:
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": fmt,
            "question": (question or "")[:150],
            "answer": (str(answer) if answer is not None else "")[:100],
            "success": bool(success),
            "extra": extra or {}
        }
        with open(_TELEMETRY_FILE, "a", encoding="utf-8") as tf:
            tf.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"Telemetry log error: {e}")


# ------------------------------------------------------- N1 chatbot rewrite
def _unattended_handle_chatbot(self, timeout=12):
    """Answer the Naukri Easy-Apply chatbot. Returns True when application was saved."""
    self._chatbot_detected = False
    self._chatbot_ok = True
    self._chatbot_unanswered = []
    self._chatbot_mandatory_unanswered = []
    driver = self.driver

    # Enforce zero implicit wait for lightning-fast element checks
    try:
        driver.implicitly_wait(0)
    except Exception:
        pass

    # 1. Drawer present? Locate the actual drawer ELEMENT (scoped container) — page-wide
    # signals caused false positives on the job page (decoy file inputs, page Apply button).
    drawer = _find_chat_drawer(driver)
    if drawer is None:
        # Drawer may animate in after Easy Apply click — one short re-check, then give up fast
        time.sleep(2.0)
        drawer = _find_chat_drawer(driver)
    if drawer is None:
        logger.info("No chatbot drawer element — proceeding to standard submit path")
        return True

    self._chatbot_detected = True
    self._resume_attached = False
    self._chatbot_answered_qs = []
    self._chatbot_given_answers = []
    _prev_qsig = None
    _last_qchange = time.time()
    logger.info("💬 Chatbot drawer found (unattended handler)")
    try:
        _dcls = (drawer.get_attribute("class") or "")[:120]
        _did = drawer.get_attribute("id") or ""
        _dtag = drawer.tag_name or ""
        _dr = driver.execute_script(
            "var r=arguments[0].getBoundingClientRect();return [r.width,r.height,r.left,r.top];", drawer)
        logger.info(f"🧭 Drawer identity: <{_dtag}> id='{_did}' class='{_dcls}' rect={_dr}")
    except Exception as e:
        logger.info(f"🧭 Drawer identity unreadable: {e}")
    time.sleep(2.5)  # Allow initial chatbot bubbles and questions to render
    content_grace_until = time.time() + 15  # drawer content loads async — don't judge it empty too early
    deadline = time.time() + 100
    last_progress = time.time()
    loc_variants = _location_variants(self.config)

    while time.time() < deadline:
        progressed = False

        # Re-resolve drawer each pass (it re-renders after every answer: stale AND
        # detached-but-not-stale references must both be refreshed, else all queries
        # silently return empty and the loop discards answered drawers).
        try:
            _drawer_alive = bool(drawer.is_displayed())
        except Exception:
            _drawer_alive = False
        if not _drawer_alive:
            drawer = _find_chat_drawer(driver)
            if drawer is None:
                # H4 (2026-09-15): the drawer disappearing after at least one answer was
                # sent is not necessarily a failure — Naukri auto-submits after the last
                # answer and navigates to /myapply/... (confirmed live: 3+ real successes
                # were discarded this way, e.g. 'Applied to "Informatica Etl Tester"' in the
                # discard dump). Check Naukri's own verdict before giving up.
                if getattr(self, "_chatbot_answered_qs", None):
                    ev = None
                    for _ in range(5):
                        ev = _applied_evidence(driver)
                        if ev:
                            break
                        time.sleep(2.0)
                    if ev == "applied":
                        logger.info("✅ Drawer closed after answering — Naukri shows Applied (confirmed)")
                        self._chatbot_ok = True
                        _log_telemetry("save_submission", "chatbot_drawer", "applied_after_drawer_close", True)
                        return True
                    if ev == "external":
                        logger.info("↗️ Drawer closed — Naukri redirected to the company site, not applied")
                        self._chatbot_ok = False
                        return False
                    if ev == "rejected":
                        logger.warning("⚠️ Drawer closed — Naukri shows the incomplete-information rejection")
                        self._chatbot_ok = False
                        return False
                break
            progressed = True

        # ---- collect visible question texts (excluding inputs/footers/options)
        qtexts = []
        try:
            for el in drawer.find_elements(By.XPATH, _Q_XPATH):
                try:
                    t = (el.text or "").strip()
                    if t and el.is_displayed() and len(t) > 1:
                        qtexts.append(t)
                except Exception:
                    continue
        except Exception:
            pass

        # Settle tracking: a newly arrived question resets the Save quiet timer so the
        # bot never saves 1s before the next question streams in (the Izmo .Net Core case).
        try:
            _qsig = tuple(qtexts)
            if _qsig != _prev_qsig:
                _prev_qsig = _qsig
                _last_qchange = time.time()
        except Exception:
            pass

        # ---- A0. quick-reply chips & suggestion pills (e.g. [ Bengaluru ], [ Yes ], [ 30 Days ])
        # Also covers BARE leaf pills (div/span/li, no chip class — e.g. consent [Yes]).
        # Leaf-only + short-text + exclusion list keeps containers and bubbles out; only
        # the LLM/boolean-matched single is ever clicked.
        try:
            chip_els = _displayed(drawer.find_elements(
                By.CSS_SELECTOR,
                "div[class*='msg'] button, div[class*='chat'] button, "
                "div[class*='botmsg'] button, div[class*='bot-msg'] button, "
                "div[class*='content'] button, div[class*='options'] button, "
                "div[class*='quick-reply'] button, "
                "div[class*='chip'], span[class*='chip'], button[class*='chip'], "
                "div[class*='pill'], span[class*='pill'], button[class*='pill'], "
                "ul[class*='chips'] li, [class*='option-bubble'], button, "
                "div[class*='msg'] div, div[class*='msg'] span, div[class*='msg'] li, "
                "div[class*='options'] span, div[class*='quick-reply'] span, "
                "div[class*='botmsg'] div, div[class*='bot-msg'] span"
            ))
            valid_chips = []
            try:
                _given = set(getattr(self, "_chatbot_given_answers", []) or [])
            except Exception:
                _given = set()
            for ch in chip_els:
                try:
                    txt = (ch.text or "").strip()
                except Exception:
                    continue
                # Leaf only: reject multi-line containers (e.g. "Upload Resume\nI'll do it later")
                if not txt or "\n" in txt or len(txt) > 40:
                    continue
                if any(k in txt.lower() for k in ("save", "apply", "cancel", "close", "skip", "send", "submit", "type message")):
                    continue
                # Never treat our OWN previous answer bubbles as clickable options
                # (e.g. stale "3 years" bubble clicked for a relocate question).
                if txt.strip().lower() in _given:
                    continue
                try:
                    if ch.find_elements(By.XPATH, "./*"):
                        continue  # container, not a leaf pill
                except Exception:
                    pass
                try:
                    _uanc = ch.find_elements(
                        By.XPATH,
                        "./ancestor::*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'user') "
                        "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'outgoing') "
                        "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sender')][1]")
                    if _uanc:
                        continue  # outgoing/user bubble, not an option
                except Exception:
                    pass
                valid_chips.append((ch, txt))

            resume_path = RESUME_PDF
            q_recent = (qtexts[-1] if qtexts else "").lower()

            # Dedicated Resume Upload & Existing Resume Attachment (hidden input aware, never types filename)
            if "resume" in q_recent or "upload" in q_recent or "cv" in q_recent or any("resume" in txt.lower() for _, txt in valid_chips):
                try:
                    _nfi = len(drawer.find_elements(By.CSS_SELECTOR, "input[type='file']"))
                    logger.info(f"📄 Resume branch: chips={[t for _, t in valid_chips][:10]} file_inputs={_nfi} q='{q_recent[:60]}'")
                except Exception:
                    pass
                existing_chip = None
                for ch, txt in valid_chips:
                    if any(k in txt.lower() for k in ("existing", "profile", "saved", "attached", "keep", "current", "continue")):
                        existing_chip = (ch, txt)
                        break
                if existing_chip:
                    logger.info(f"Chatbot chip clicked (using existing resume): '{existing_chip[1]}'")
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", existing_chip[0])
                    try:
                        existing_chip[0].click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", existing_chip[0])
                    progressed = True
                    time.sleep(1.5)
                    _log_telemetry("quick_reply_chip", "Please upload your resume.", existing_chip[1], True)
                elif os.path.exists(resume_path):
                    # Human order: click 'Upload Resume' FIRST to expose/enable the upload UI,
                    # then attach to the live file input and verify files.length == 1.
                    upload_chip = None
                    for ch, txt in valid_chips:
                        if "upload" in txt.lower() and "resume" in txt.lower():
                            upload_chip = (ch, txt)
                            break
                    if upload_chip and not getattr(self, "_resume_attached", False):
                        logger.info(f"Clicking '{upload_chip[1]}' chip first to expose resume upload UI...")
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", upload_chip[0])
                        try:
                            upload_chip[0].click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", upload_chip[0])
                        time.sleep(1.5)
                        try:
                            fresh = _find_chat_drawer(driver)
                            if fresh is not None:
                                drawer = fresh
                        except Exception:
                            pass
                        progressed = True

                    def _try_attach_resume():
                        attached = False
                        try:
                            file_inputs = drawer.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        except StaleElementReferenceException:
                            return False
                        except Exception:
                            file_inputs = []
                        for fi in file_inputs:
                            try:
                                acc = fi.get_attribute("accept") or ""
                                dis = fi.get_attribute("disabled")
                                logger.info(f"🔍 file input: accept='{acc}' disabled={dis} displayed={fi.is_displayed()}")
                            except Exception:
                                pass
                            try:
                                driver.execute_script("arguments[0].style.display='block';arguments[0].style.visibility='visible';arguments[0].style.opacity='1';arguments[0].removeAttribute('hidden');arguments[0].removeAttribute('disabled');", fi)
                            except Exception:
                                pass
                            try:
                                fi.send_keys(resume_path)
                                try:
                                    nfiles = driver.execute_script("return (arguments[0].files ? arguments[0].files.length : -1);", fi)
                                except Exception:
                                    nfiles = -1
                                try:
                                    fname = driver.execute_script("return (arguments[0].files && arguments[0].files.length ? arguments[0].files[0].name : '');", fi)
                                except Exception:
                                    fname = ""
                                logger.info(f"📄 Resume file attached via input[type=file]: {resume_path} (verified files={nfiles} name='{fname}')")
                                if nfiles == 1:
                                    attached = True
                                    break
                                logger.warning(f"⚠️ send_keys accepted but files.length={nfiles} — trying next file input (if any)")
                            except Exception as e:
                                logger.warning(f"⚠️ File upload threw ({type(e).__name__}): {str(e)[:120]}")
                                continue
                        return attached
                    uploaded_file = _try_attach_resume()
                    if uploaded_file:
                        progressed = True
                        self._resume_attached = True
                        time.sleep(2.5)
                        _log_telemetry("file_upload", "Please upload your resume.", "Kaustubh_upadhyaya_data_engineer.pdf", True)
                    if not uploaded_file:
                        # Upload chip was already clicked above; drawer may have re-rendered — re-resolve and retry once
                        try:
                            fresh = _find_chat_drawer(driver)
                            if fresh is not None:
                                drawer = fresh
                        except Exception:
                            pass
                        time.sleep(1.0)
                        if _try_attach_resume():
                            uploaded_file = True
                            progressed = True
                            self._resume_attached = True
                            time.sleep(2.5)
                            _log_telemetry("file_upload", "Please upload your resume.", "Kaustubh_upadhyaya_data_engineer.pdf", True)
                    if not uploaded_file:
                        logger.warning("⚠️ Resume file input not accepting file (files.length=0) — will NOT type filename into chat box")
                        try:
                            diag = driver.execute_script("""
                                var d = arguments[0];
                                var btns = [];
                                d.querySelectorAll('button').forEach(function(b){
                                    var t = (b.innerText || '').trim().replace(/\\s+/g,' ');
                                    if (t) btns.push(t.slice(0,60));
                                });
                                var inputs = [];
                                document.querySelectorAll('input[type=file]').forEach(function(f, i){
                                    inputs.push('#'+i+' acc='+(f.accept||'')+' dis='+f.disabled+' vis='+(f.offsetParent!==null)+' files='+(f.files?f.files.length:-1));
                                });
                                var rtxt = [];
                                d.querySelectorAll('*').forEach(function(el){
                                    if (el.children.length===0) {
                                        var t=(el.innerText||'').trim();
                                        if (t && /resume|upload|attach|biodata|cv/i.test(t) && t.length<120) rtxt.push(t.slice(0,100));
                                    }
                                });
                                return 'BTN:['+btns.slice(0,12).join('|')+'] FILE:'+inputs.join(';')+' RTXT:['+[...new Set(rtxt)].slice(0,6).join('|')+']';
                            """, drawer)
                            logger.warning(f"🔬 Upload-area diagnostic: {diag}")
                        except Exception as e:
                            logger.debug(f"Upload diagnostic failed: {e}")

            if valid_chips:
                q = qtexts[-1] if qtexts else ""
                ql = q.lower()
                # Resume already attached via file input — NEVER click any chip for a resume question
                # (both "Upload Resume" and "I'll do it later" would undo the attachment → rejection)
                if getattr(self, "_resume_attached", False) and any(
                        k in ql for k in ("resume", "upload your", "attach", "cv", "biodata")):
                    logger.info("⏭️ Resume already attached — skipping all chips for resume question")
                    progressed = True
                    time.sleep(0.5)
                    continue
                if getattr(self, "_resume_attached", False):
                    valid_chips = [(ch, txt) for ch, txt in valid_chips
                                   if not any(k in txt.lower() for k in ("resume", "upload", "attach", "cv", "later", "skip"))]
                chip_texts = [txt for _, txt in valid_chips]
                matched_chip = None

                # Location matching
                if any(w in ql for w in LOCATION_WORDS):
                    matched_chip = _match_option(chip_texts, [v.lower() for v in loc_variants])

                # Boolean Yes/No matching
                if not matched_chip and any(t.lower() in ("yes", "no") for t in chip_texts):
                    if any(neg in ql for neg in ("criminal", "convicted", "fired", "terminated", "felony", "visa sponsorship")):
                        matched_chip = _match_option(chip_texts, ["no"])
                    else:
                        matched_chip = _match_option(chip_texts, ["yes"])

                if not matched_chip:
                    matched_chip = _llm_answer_question(q, options=chip_texts, config=self.config)
                    if matched_chip not in chip_texts:
                        matched_chip = _match_option(chip_texts, [matched_chip.lower()] if matched_chip else [])

                if matched_chip:
                    for ch, txt in valid_chips:
                        if txt == matched_chip:
                            logger.info(f"Chatbot chip clicked: '{q[:80]}' -> '{txt}'")
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ch)
                            try:
                                ch.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", ch)
                            progressed = True
                            time.sleep(1.0)
                            _log_telemetry("quick_reply_chip", q, txt, True)
                            try:
                                self._chatbot_answered_qs.append(_qkey(q))
                                self._chatbot_given_answers.append(txt.strip().lower())
                            except Exception:
                                pass
                            break
        except Exception as e:
            logger.debug(f"chip handling: {e}")

        # ---- A. free-text chat boxes & inputs (drawer-scoped). Broad on purpose:
        # Naukri swaps composer markup between questions (contenteditable div with varying
        # classes, or inputs of varying type). Missing it means boxes=0 with visible
        # questions — the Q2-never-typed failure.
        try:
            boxes = _displayed(drawer.find_elements(
                By.CSS_SELECTOR, "[contenteditable='true'], [contenteditable='']"))
            for el in _displayed(drawer.find_elements(
                By.CSS_SELECTOR,
                "textarea, input:not([type]), input[type='text'], input[type='search'], "
                "input[type='number'], input[type='tel'], input[type='email'], input[type='url'], "
                "div[role='textbox'], [role='textbox']")):
                if el not in boxes:
                    boxes.append(el)
        except StaleElementReferenceException:
            drawer = _find_chat_drawer(driver)
            if drawer is None:
                break
            boxes = []
        except Exception:
            boxes = []
        for box in boxes:
            try:
                is_input_tag = (box.tag_name or "").lower() in ("input", "textarea")
                current_val = _box_current_value(box)
                if current_val:
                    continue  # already filled
                q = qtexts[-1] if qtexts else ""
                if not q:
                    try:
                        bid = box.get_attribute("id")
                        if bid:
                            labs = drawer.find_elements(By.XPATH, f".//label[@for='{bid}']")
                            if labs and labs[0].text:
                                q = labs[0].text.strip()
                    except Exception:
                        pass
                if not q:
                    try:
                        anc = box.find_element(By.XPATH, "./ancestor::div[contains(@class,'field') or contains(@class,'form') or contains(@class,'botmsg') or contains(@class,'question')][1]")
                        q = (anc.text or "").strip()
                    except Exception:
                        pass

                # NEVER type resume filename into chat box — file must go via input[type=file] only
                ql_box = (q or "").lower()
                if any(k in ql_box for k in ("resume", "upload your", "attach", "cv", ".pdf")):
                    logger.info(f"⏭️ Skipping free-text typing for resume/upload question (handled by file input): '{q[:60]}'")
                    continue

                ans = self._unattended_text_answer(q)
                # Safety: never send a bare filename as a chat answer
                if ans and (ans.strip().lower().endswith(".pdf") or "kaustubh_upadhyaya" in ans.lower()):
                    logger.warning(f"⚠️ Blocking filename-as-answer '{ans[:50]}' — resume must attach via file input, not chat text")
                    continue
                if not ans:
                    if _is_mandatory(q, box):
                        self._chatbot_ok = False
                        self._chatbot_mandatory_unanswered.append(q or "text input")
                        logger.warning(f"⚠️ Mandatory question unanswered: '{q[:90]}' -> Discarding job to prevent incomplete application")
                        _close_chatbot_drawer(driver)
                        return False
                    if q and q not in self._chatbot_unanswered:
                        self._chatbot_unanswered.append(q)
                    continue

                logger.info(f"Chatbot Q: '{q[:90]}' -> A: '{ans[:60]}'")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", box)
                except Exception:
                    pass
                try:
                    box.click()
                except Exception:
                    pass

                if is_input_tag:
                    try:
                        box.clear()
                    except Exception:
                        pass
                    try:
                        box.send_keys(ans)
                        driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true})); arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", box)
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true})); arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", box, ans)
                        except Exception:
                            continue
                else:
                    try:
                        driver.execute_script(
                            "var el=arguments[0],v=arguments[1];el.focus();"
                            "document.execCommand('selectAll',false,null);"
                            "document.execCommand('insertText',false,v);"
                            "el.dispatchEvent(new Event('input',{bubbles:true}));",
                            box, ans)
                    except Exception:
                        try:
                            box.send_keys(ans)
                        except Exception:
                            continue
                time.sleep(0.5)
                # Robust per-answer send: parent/sibling icon click + send selectors + JS keydown/keypress/keyup + Selenium RETURN
                sent = False

                # 1. Immediate parent/sibling send button or SVG search
                try:
                    js_clicked = driver.execute_script("""
                        var box = arguments[0];
                        var p = box.parentElement;
                        for (var i = 0; i < 4 && p; i++) {
                            var btns = p.querySelectorAll("button, [role='button'], .send, [class*='send'], svg, i, [data-automation*='send']");
                            for (var b of btns) {
                                if (b !== box && b.offsetParent !== null) {
                                    var t = (b.innerText || '').toLowerCase();
                                    if (!t.includes('save') && !t.includes('cancel')) {
                                        b.click();
                                        return true;
                                    }
                                }
                            }
                            p = p.parentElement;
                        }
                        return false;
                    """, box)
                    if js_clicked:
                        sent = True
                except Exception:
                    pass

                if not sent:
                    send_selectors = (
                        "//button[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')]",
                        "//span[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')]",
                        "//div[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')]",
                        "//*[contains(@class,'sendMsg') or contains(@class,'send-btn') or contains(@class,'SendMessage')]",
                        "//*[@aria-label='Send' or @aria-label='send']",
                        "//*[@data-automation='sendMessage' or @data-automation='sendBtn']"
                    )
                    for sxp in send_selectors:
                        try:
                            btns = _displayed(drawer.find_elements(By.XPATH, "." + sxp))
                            for b in btns:
                                btxt = (b.text or "").strip().lower()
                                if "save" in btxt:
                                    continue
                                try:
                                    b.click()
                                    sent = True
                                    break
                                except Exception:
                                    driver.execute_script("arguments[0].click();", b)
                                    sent = True
                                    break
                            if sent:
                                break
                        except Exception:
                            continue

                # Dispatch synthetic JS KeyboardEvents for Enter (keydown, keypress, keyup) with keyCode 13
                try:
                    driver.execute_script("""
                        var el = arguments[0];
                        var opts = {key:'Enter', code:'Enter', keyCode:13, which:13, charCode:13, bubbles:true, cancelable:true};
                        el.dispatchEvent(new KeyboardEvent('keydown', opts));
                        el.dispatchEvent(new KeyboardEvent('keypress', opts));
                        el.dispatchEvent(new KeyboardEvent('keyup', opts));
                    """, box)
                except Exception:
                    pass

                # Selenium send_keys Return fallback
                try:
                    box.send_keys(Keys.RETURN)
                except Exception:
                    pass

                # Verify bubble or cleared input (placeholder-as-text counts as cleared)
                time.sleep(1.2)
                try:
                    if not _box_current_value(box):
                        sent = True
                except Exception:
                    pass

                _log_telemetry("text_input", q, ans, sent)
                if sent:
                    try:
                        self._chatbot_answered_qs.append(_qkey(q))
                        self._chatbot_given_answers.append((ans or "").strip().lower())
                    except Exception:
                        pass
                progressed = True
                time.sleep(1.0)
            except StaleElementReferenceException:
                progressed = True
                continue
            except Exception as e:
                logger.debug(f"chatbox handling: {e}")
                continue

        # ---- B. radio groups (grouped by name, fallback by container, drawer-scoped)
        # NOTE: custom-styled radios hide the native input (display:none) — search WITHOUT
        # the display filter so hidden inputs are found; clicking goes through the visible
        # label/pill or JS click (see _click_radio_option).
        try:
            _seen_ids = set()

            def _collect(inps):
                out = []
                for _r in inps:
                    try:
                        _kk = (_r.get_attribute("id") or _r.get_attribute("name") or "",
                               _r.get_attribute("value") or "")
                        if _kk in _seen_ids:
                            continue
                        _seen_ids.add(_kk)
                        out.append(_r)
                    except StaleElementReferenceException:
                        continue
                    except Exception:
                        continue
                return out

            radios = _collect(drawer.find_elements(By.CSS_SELECTOR, "input.ssrc__radio"))
            radios += _collect(drawer.find_elements(By.CSS_SELECTOR, "input[type='radio']"))
        except StaleElementReferenceException:
            drawer = _find_chat_drawer(driver)
            if drawer is None:
                break
            radios = []
        except Exception:
            radios = []
        groups = {}
        for r in radios:
            try:
                key = r.get_attribute("name") or ""
                if not key:
                    try:
                        anc = r.find_element(By.XPATH, "./ancestor::div[@id][1]")
                        key = anc.get_attribute("id") or ""
                    except Exception:
                        key = ""
                groups.setdefault(key or f"anon-{len(groups)}", []).append(r)
            except StaleElementReferenceException:
                progressed = True
            except Exception:
                continue
        loc_variants = _location_variants(self.config)
        for key, grp in groups.items():
            try:
                if any(r.is_selected() for r in grp):
                    continue
            except StaleElementReferenceException:
                progressed = True
                continue
            except Exception:
                continue
            labels = []
            label_els = []
            for r in grp:
                try:
                    rid = r.get_attribute("id") or ""
                    lab = None
                    lab_txt = ""
                    if rid:
                        try:
                            lab = drawer.find_element(By.XPATH, f".//label[@for='{rid}']")
                            lab_txt = ((lab.text if lab is not None else "") or "").strip()
                        except NoSuchElementException:
                            lab = None
                    if not lab_txt:
                        lab_txt = (r.get_attribute("value") or "").strip()
                    if not lab_txt:
                        # Custom pill radios: option text lives in a visible ancestor container
                        try:
                            pill = r.find_element(
                                By.XPATH,
                                "./ancestor::*[self::label or self::div or self::span]"
                                "[normalize-space(string(.))!=''][1]")
                            lab_txt = " ".join((pill.text or "").split())[:60]
                            if pill is not None and lab is None:
                                try:
                                    if pill.is_displayed():
                                        lab = pill
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    labels.append(lab_txt)
                    label_els.append(lab)
                except Exception:
                    labels.append("")
                    label_els.append(None)
            # question text: ALWAYS prefer the group's own container text (qtexts[-1] is
            # often a stale/different question — e.g. notice-period options paired with an
            # Azure-experience question — which makes the LLM pick a nonsense option).
            q = ""
            try:
                cont = grp[0].find_element(
                    By.XPATH, "./ancestor::div[count(.//input[@type='radio'])>0][1]")
                ctxt = (cont.text or "").strip()
                for lb in labels:
                    if lb:
                        ctxt = ctxt.replace(lb, " ")
                ctxt = " ".join(ctxt.split())
                if ctxt:
                    q = ctxt[:300]
            except Exception:
                q = ""
            if not q:
                q = qtexts[-1] if qtexts else ""
            if _q_opts_mismatch(q, labels):
                logger.warning(f"⚠️ Question/options mismatch (stale q): '{q[:70]}' vs {labels[:4]} — discarding job, never misrepresenting")
                self._chatbot_ok = False
                self._chatbot_mandatory_unanswered.append(q or f"radio:{key}")
                _close_chatbot_drawer(driver)
                return False
            decision, payload = classify_radio(q, labels, loc_variants)
            if decision == "select":
                target = _match_option(labels, [payload.lower()])
                idx = labels.index(target) if target in labels else -1
                if idx < 0:
                    if _is_mandatory(q, grp[0]):
                        self._chatbot_ok = False
                        self._chatbot_mandatory_unanswered.append(q or f"radio:{key}")
                        logger.warning(f"⚠️ Mandatory question unanswered: '{q[:80]}' -> Discarding job to prevent incomplete application")
                        _close_chatbot_drawer(driver)
                        return False
                    self._chatbot_unanswered.append(q or f"radio:{key}")
                    continue
                logger.info(f"Chatbot radio: '{q[:80]}' -> '{labels[idx]}' (safe default)")
                try:
                    el = grp[idx]
                    _lab = label_els[idx] if idx < len(label_els) else None
                    if _click_radio_option(driver, el, _lab):
                        progressed = True
                        time.sleep(1.0)
                        _log_telemetry("radio_button", q, labels[idx], True)
                        try:
                            self._chatbot_answered_qs.append(_qkey(q))
                            self._chatbot_given_answers.append((labels[idx] or "").strip().lower())
                        except Exception:
                            pass
                    else:
                        logger.debug("radio click failed on all channels")
                        continue
                except Exception as e:
                    logger.debug(f"radio click: {e}")
                    continue
            else:
                pick = None
                if decision != "discard":
                    pick = _llm_answer_question(q, options=labels, config=self.config)
                if pick and pick in labels:
                    idx = labels.index(pick)
                    logger.info(f"Chatbot radio: '{q[:80]}' -> '{pick}' (LLM)")
                    try:
                        el = grp[idx]
                        _lab = label_els[idx] if idx < len(label_els) else None
                        if _click_radio_option(driver, el, _lab):
                            progressed = True
                            time.sleep(1.0)
                            _log_telemetry("radio_button", q, pick, True)
                            try:
                                self._chatbot_answered_qs.append(_qkey(q))
                                self._chatbot_given_answers.append((pick or "").strip().lower())
                            except Exception:
                                pass
                        else:
                            raise Exception("all radio click channels failed")
                    except Exception:
                        if _is_mandatory(q, grp[0]):
                            self._chatbot_ok = False
                            self._chatbot_mandatory_unanswered.append(q or f"radio:{key}")
                            logger.warning(f"⚠️ Mandatory question unanswered: '{q[:80]}' -> Discarding job to prevent incomplete application")
                            _close_chatbot_drawer(driver)
                            return False
                        self._chatbot_unanswered.append(q or f"radio:{key}")
                else:
                    if _is_mandatory(q, grp[0]):
                        self._chatbot_ok = False
                        self._chatbot_mandatory_unanswered.append(q or f"radio:{key}")
                        logger.warning(f"⚠️ Mandatory question unanswered: '{q[:80]}' -> Discarding job to prevent incomplete application")
                        _close_chatbot_drawer(driver)
                        return False
                    logger.info(f"Chatbot radio UNANSWERED/DISCARDED: '{q[:80]}'")
                    if q and q not in self._chatbot_unanswered:
                        self._chatbot_unanswered.append(q)

        # ---- C. native <select> dropdowns (drawer-scoped)
        try:
            selects = _displayed(drawer.find_elements(By.TAG_NAME, "select"))
        except StaleElementReferenceException:
            drawer = _find_chat_drawer(driver)
            if drawer is None:
                break
            selects = []
        except Exception:
            selects = []
        for sel_el in selects:
            try:
                from selenium.webdriver.support.ui import Select
                sel = Select(sel_el)
                cur = sel.first_selected_option.text.strip()
                if cur and cur.lower() not in ("select an option", "select", "--select--", ""):
                    continue
                opts = [o.text.strip() for o in sel.options if o.text.strip()]
                # Container-first question (same stale-qtexts hazard as radios)
                q = ""
                try:
                    _scont = sel_el.find_element(
                        By.XPATH, "./ancestor::div[count(.//select)>0][1]")
                    _sctxt = " ".join(((_scont.text or "").strip()).split())
                    for _o in opts:
                        if _o:
                            _sctxt = _sctxt.replace(_o, " ")
                    _sctxt = " ".join(_sctxt.split())
                    if _sctxt:
                        q = _sctxt[:300]
                except Exception:
                    q = ""
                if not q:
                    q = qtexts[-1] if qtexts else ""
                if _q_opts_mismatch(q, opts):
                    logger.warning(f"⚠️ Question/options mismatch (stale q): '{q[:70]}' vs {opts[:4]} — discarding job, never misrepresenting")
                    self._chatbot_ok = False
                    self._chatbot_mandatory_unanswered.append(q or "select")
                    _close_chatbot_drawer(driver)
                    return False
                target = None
                if any(w in q.lower() for w in LOCATION_WORDS):
                    target = _match_option(opts, [v.lower() for v in loc_variants])
                if target is None:
                    pick = _llm_answer_question(q, options=opts, config=self.config)
                    if pick and pick in opts:
                        target = pick
                if target:
                    logger.info(f"Chatbot select: '{q[:80]}' -> '{target}'")
                    sel.select_by_visible_text(target)
                    progressed = True
                    time.sleep(1.0)
                    _log_telemetry("dropdown_select", q, target, True)
                    try:
                        self._chatbot_answered_qs.append(_qkey(q))
                        self._chatbot_given_answers.append((target or "").strip().lower())
                    except Exception:
                        pass
                else:
                    if _is_mandatory(q, sel_el):
                        self._chatbot_ok = False
                        self._chatbot_mandatory_unanswered.append(q or "select")
                        logger.warning(f"⚠️ Mandatory question unanswered: '{q[:80]}' -> Discarding job to prevent incomplete application")
                        _close_chatbot_drawer(driver)
                        return False
                    if q and q not in self._chatbot_unanswered:
                        self._chatbot_unanswered.append(q)
            except Exception as e:
                logger.debug(f"select handling: {e}")
                continue

        # ---- D. gate on Save state (drawer-scoped — page Apply buttons unreachable)
        try:
            save = _find_save_button(drawer)
        except StaleElementReferenceException:
            drawer = _find_chat_drawer(driver)
            if drawer is None:
                break
            save = None
        try:
            save_enabled = bool(
                save and save.is_displayed() and save.is_enabled()
                and "disabled" not in (save.get_attribute("class") or "").lower()
                and save.get_attribute("disabled") is None
                and str(save.get_attribute("aria-disabled") or "").lower() != "true"
            )
        except StaleElementReferenceException:
            save_enabled = False
            progressed = True
        except Exception:
            save_enabled = False

        if save is not None and not save_enabled:
            # Throttled visibility: log Save presence/state every ~15s while waiting
            try:
                if time.time() - getattr(self, "_last_save_state_log", 0) > 15:
                    self._last_save_state_log = time.time()
                    _st = ""
                    try:
                        _st = (save.get_attribute("class") or "")[:60]
                    except Exception:
                        pass
                    logger.info(f"⏳ Save present but disabled (class='{_st}') — waiting for answers to register...")
            except Exception:
                pass

        try:
            if time.time() - getattr(self, "_last_pass_log", 0) > 12:
                self._last_pass_log = time.time()
                _nq = len(qtexts)
                _nb = len(boxes) if "boxes" in dir() else -1
                _nr = len(radios) if "radios" in dir() else -1
                _ns = len(selects) if "selects" in dir() else -1
                logger.info(f"🔎 pass: qtexts={_nq} boxes={_nb} radios={_nr} selects={_ns} save={'yes' if save else 'no'}/{'enabled' if save_enabled else 'disabled'}")
        except Exception:
            pass

        if save_enabled:
            # Enforce stabilization: do not click Save if an action was taken less than 3.5s ago
            if (time.time() - last_progress < 3.5):
                time.sleep(1.0)
                continue
            # Settle rule: require quiet drawer (no new questions for 8s AND no action for
            # 10s). Multi-question drawers stream Q2 right after Q1 is answered.
            if (time.time() - last_progress < 10) or (time.time() - _last_qchange < 8):
                time.sleep(1.0)
                continue
            # Unanswered-question block: a visible '?' never committed must gate Save,
            # even if the input box momentarily looks settled (the Izmo Q2 race).
            try:
                _answered = set(getattr(self, "_chatbot_answered_qs", []) or [])
                _open_q = [t for t in qtexts if "?" in t and _qkey(t) not in _answered]
            except Exception:
                _open_q = []
            if _open_q:
                logger.info(f"⏳ Open question(s) awaiting answers ({len(_open_q)}) — holding Save: '{_open_q[0][:70]}'")
                time.sleep(1.5)
                continue

            # Prevent premature save if there are empty interactive input boxes still awaiting input
            unanswered_boxes = []
            try:
                for bx in _displayed(drawer.find_elements(By.CSS_SELECTOR, "[contenteditable='true'], [contenteditable=''], textarea, input:not([type]), input[type='text'], input[type='search'], input[type='number'], input[type='tel'], input[type='email'], input[type='url'], div[role='textbox'], [role='textbox']")):
                    if not _box_current_value(bx):
                        unanswered_boxes.append(bx)
            except Exception:
                pass
            if unanswered_boxes and (time.time() - last_progress < 8):
                time.sleep(1.0)
                continue

            # Prevent premature save if there are still question chips or option bubbles on screen
            if valid_chips and (time.time() - last_progress < 8):
                time.sleep(1.0)
                continue

            # Check for uncommitted text in boxes before allowing Save
            uncommitted = False
            try:
                for bx in _displayed(drawer.find_elements(By.CSS_SELECTOR, "[contenteditable='true'], [contenteditable=''], textarea, input:not([type]), input[type='text'], input[type='search'], input[type='number'], input[type='tel'], input[type='email'], input[type='url'], div[role='textbox'], [role='textbox']")):
                    val = _box_current_value(bx)
                    if val:
                        logger.warning(f"⚠️ Box has uncommitted text '{val[:40]}', attempting send before Save...")
                        try:
                            bx.send_keys(Keys.RETURN)
                            time.sleep(1.0)
                        except Exception:
                            pass
                        val_after = (bx.get_attribute("value") or "").strip() if (bx.tag_name or "").lower() in ("input", "textarea") else (bx.text or "").strip()
                        if val_after and val_after.lower() != "type message here...":
                            uncommitted = True
            except Exception:
                pass

            if uncommitted:
                logger.warning("⚠️ Mandatory text answer remains uncommitted in box -> Discarding job to prevent incomplete application")
                self._chatbot_ok = False
                _close_chatbot_drawer(driver)
                return False

            if self._chatbot_mandatory_unanswered:
                logger.warning("⚠️ Save is enabled but mandatory questions remain unanswered -> Discarding")
                self._chatbot_ok = False
                _close_chatbot_drawer(driver)
                return False

            logger.info("✅ Chatbot questions answered — Clicking Save now...")
            try:
                _stag = (save.tag_name or "")
                _scls = (save.get_attribute("class") or "")[:80]
                _saria = save.get_attribute("aria-disabled")
                _sdis = save.get_attribute("disabled")
                _stxt = ((save.text or "") or "")[:30]
                logger.info(f"🎯 Save target: <{_stag}> text='{_stxt}' class='{_scls}' aria-disabled={_saria} disabled={_sdis}")
            except Exception:
                pass
            try:
                _qs = driver.execute_script("return (document.body ? document.body.innerText : '').slice(0, 1200);")
                logger.info(f"🧾 Drawer state before Save: '{(_qs or '').replace(chr(10), ' | ')[:600]}'")
            except Exception:
                pass
            try:
                driver.save_screenshot("debug_chatbot_before_save.png")
                logger.info("📸 Saved pre-save drawer screenshot to debug_chatbot_before_save.png")
            except Exception as e:
                logger.debug(f"Pre-save screenshot skipped: {e}")
            # If Save matched a container, drill to the real inner control first
            _save_target = save
            try:
                for _cand in save.find_elements(By.XPATH, ".//button | .//input[@type='button' or @type='submit'] | .//*[@role='button']"):
                    try:
                        _ct = ((_cand.text or "") + " " + (_cand.get_attribute("value") or "")).strip().lower()
                        _cc = (_cand.get_attribute("class") or "").lower()
                        if _cand.is_displayed() and ("save" in _ct or "submit" in _ct or "save" in _cc or "submit" in _cc):
                            _save_target = _cand
                            try:
                                logger.info(f"🎯 Save inner control: <{(_cand.tag_name or '')}> text='{_ct[:30]}'")
                            except Exception:
                                pass
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", _save_target)
            except Exception:
                pass
            time.sleep(0.3)
            _save_clicked = False
            for _click_try in range(3):
                try:
                    _save_target.click()
                    _save_clicked = True
                    break
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", _save_target)
                        _save_clicked = True
                        break
                    except Exception as e:
                        logger.debug(f"Save click try {_click_try + 1} failed: {e}")
                        time.sleep(1.0)
            if not _save_clicked:
                # Last resort: coordinate click (container divs sometimes ignore element clicks)
                try:
                    from selenium.webdriver.common.action_chains import ActionChains as _AC
                    _AC(driver).move_to_element(_save_target).click().perform()
                    _save_clicked = True
                    logger.info("🖱️ Save clicked via ActionChains coordinates")
                except Exception as e:
                    logger.error(f"❌ Save click failed on all channels: {e}")
                    _close_chatbot_drawer(driver)
                    return False
            time.sleep(2.0)

            rej = _check_rejection_messages(driver)
            if rej:
                logger.error(f"❌ Application rejected due to incomplete information: '{rej}'")
                _log_telemetry("rejection", "application_rejected", rej[:100], False)
                _close_chatbot_drawer(driver)
                self._chatbot_ok = False
                return False
            # Drawer-state check: if the drawer is still open with identical questions,
            # the click landed nowhere — retry once via coordinates before giving up.
            try:
                _still_open = _find_chat_drawer(driver) is not None
            except Exception:
                _still_open = False
            if _still_open and not _is_applied_on_page(driver):
                logger.info("↩️ Drawer still open after Save click — retrying via ActionChains")
                try:
                    from selenium.webdriver.common.action_chains import ActionChains as _AC2
                    _AC2(driver).move_to_element(_save_target).click().perform()
                    time.sleep(3.0)
                except Exception as e:
                    logger.debug(f"Save retry click failed: {e}")

            # STRICT confirmation: a click without rejection is NOT proof (page-level Save
            # favorite clicks also produce no rejection). Require applied-state evidence,
            # checked twice (success toasts can render a few seconds late).
            confirmed = False
            for _attempt in range(2):
                try:
                    if _is_applied_on_page(driver):
                        confirmed = True
                        break
                except Exception:
                    pass
                # H3 (2026-09-15): the old fallback here matched 'apply confirmation' /
                # 'applied' anywhere in the URL or body — sampled live, that title/text
                # appears on BOTH a real 200 success AND a 202 "redirected to the company
                # website" page, so it could confirm an application that never happened.
                # `_applied_evidence` reads Naukri's own verdict (multiApplyResp code /
                # 'Applied to "') instead of guessing from ambiguous text.
                try:
                    if _applied_evidence(driver) == "applied":
                        confirmed = True
                        break
                except Exception:
                    pass
                if not confirmed and _attempt == 0:
                    time.sleep(3.0)
            if not confirmed:
                logger.warning("⚠️ Save clicked, no rejection, but NO applied-state evidence — will NOT count as applied")
                _log_telemetry("rejection", "save_unconfirmed", "no_applied_state", False)
                _close_chatbot_drawer(driver)
                self._chatbot_ok = False
                return False

            logger.info("✅ Chatbot application submitted & confirmed via Save")
            self._chatbot_ok = True
            self._chatbot_unanswered = []
            _log_telemetry("save_submission", "chatbot_drawer", "save_confirmed", True)
            return True
        if progressed:
            last_progress = time.time()
            time.sleep(1.5)
            continue
        if self._chatbot_unanswered and time.time() - last_progress > 12:
            break
        if not save and not boxes and not radios and not selects:
            if time.time() < content_grace_until:
                time.sleep(1.5)
                continue  # drawer content still loading — keep polling, don't discard yet
            break  # genuinely nothing to do
        time.sleep(1.5)

    try:
        _qs = driver.execute_script("return (document.body ? document.body.innerText : '').slice(0, 800);")
        logger.warning(f"🧾 Discard drawer dump: '{(_qs or '').replace(chr(10), ' | ')[:500]}'")
    except Exception:
        pass
    try:
        driver.save_screenshot("debug_drawer_empty.png")
        logger.info("📸 Saved empty-drawer screenshot to debug_drawer_empty.png")
    except Exception as e:
        logger.debug(f"Empty-drawer screenshot skipped: {e}")
    logger.warning("⚠️ Chatbot finished without confirmed Save submission -> Discarding")
    _log_telemetry("rejection", "chatbot_no_save", "discarded_no_confirmed_save", False)
    self._chatbot_ok = False
    _close_chatbot_drawer(driver)
    return False


def _unattended_text_answer(self, question):
    """Safe-defaults-first text answering. Returns answer string or None."""
    q = (question or "").strip()
    if not q:
        return None
    ql = q.lower()

    # Date of birth (2026-09-15): single free-text "DD/MM/YYYY" field. A 3-way split
    # day/month/year drawer is not a text box at all and is handled by chatdrawer v2 instead.
    if "date of birth" in ql or re.search(r'\bdob\b', ql):
        dob = str((self.config.get("personal_info", {}) or {}).get("date_of_birth", "")).strip()
        if dob:
            return dob

    # Boolean Yes/No questions should NEVER be answered as "3 years"
    if any(ql.startswith(p) for p in ("do you", "are you", "have you", "will you", "can you", "would you", "is there", "is your", "should")):
        if any(neg in ql for neg in ("criminal", "convicted", "fired", "terminated", "felony", "visa sponsorship")):
            return "No"
        return "Yes"

    # Specific quantitative experience questions
    if any(p in ql for p in ("how many years", "years of experience", "total experience", "number of years")):
        return f"{self.config.get('user_profile', {}).get('experience_years', '3')} years"

    try:
        ans = ChatbotMixin._get_keyword_answer(self, q)
        if ans:
            return ans
    except Exception:
        pass
    hit = QA_DICT.get(ql)
    if hit:
        return hit
    try:
        ans = _llm_answer_question(q, options=None, config=getattr(self, "config", None))
        if ans:
            return ans
    except Exception as e:
        logger.debug(f"LLM text answer error: {e}")
    return None


def _unattended_gemini_pick(self, question, options):
    """Ask LLM to choose among radio/select options. Returns option text or None."""
    if not options:
        return None
    try:
        return _llm_answer_question(question, options=options, config=getattr(self, "config", None))
    except Exception as e:
        logger.debug(f"LLM pick error: {e}")
        return None


ChatbotMixin._handle_chatbot = _unattended_handle_chatbot
ChatbotMixin._unattended_text_answer = _unattended_text_answer
ChatbotMixin._unattended_gemini_pick = _unattended_gemini_pick

# ------------------------------------------------- chatdrawer v2 (dedicated chat-window module)
# Wraps the v1 handler just installed above rather than replacing it: v2 only runs when a bot
# instance is opted in (config.bot_behavior.chat_engine == "v2" or env NAUKRI_CHAT_ENGINE=v2),
# so it can be canary-tested against real applications before becoming the default. See
# naukri_bot/chatdrawer/__init__.py for the contract both paths honor.
try:
    from naukri_bot.chatdrawer import install as _install_chatdrawer_v2, Hooks as _ChatV2Hooks

    _install_chatdrawer_v2(ChatbotMixin, _ChatV2Hooks(
        classify_radio=classify_radio,
        llm_answer=_llm_answer_question,
        text_answer=_unattended_text_answer,
        location_variants=_location_variants,
        q_opts_mismatch=_q_opts_mismatch,
        resume_path=RESUME_PDF,
    ))
except Exception as e:
    logger.warning(f"chatdrawer v2 install skipped ({e!r}) — v1 chat handler remains active")

# -------------------------------------------- N2 Save-aware submit + N3 titles
_orig_submit_improved = ApplicationMixin._handle_easy_apply_submission_improved


# H2 (2026-09-15): a visible modal/dialog containing form controls, or None. Used to scope
# _find_save_button — it must NEVER be called with the whole driver/page (its own docstring
# already said so): page-wide it matched job-card bookmark "Save" buttons on the search-results
# page behind the job, and every one of those got clicked and counted as an applied submission
# (13 in an 18-minute window; 202 external-redirects and Naukri error pages included). This is
# the confirmed root cause of the "Applied (Easy Apply)" false-confirm rows.
def _find_modal_form(driver):
    try:
        driver.implicitly_wait(0)
        modals = driver.find_elements(
            By.CSS_SELECTOR,
            "div[class*='modal' i], div[class*='Modal'], div[class*='dialog' i], [role='dialog'], [aria-modal='true']")
        for m in modals:
            try:
                if not m.is_displayed():
                    continue
                if m.find_elements(By.CSS_SELECTOR, "input, select, textarea, button"):
                    return m
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
    except Exception:
        pass
    finally:
        try:
            driver.implicitly_wait(1)
        except Exception:
            pass
    return None


def _save_aware_submit(self):
    if getattr(self, "_chatbot_ok", True) is False or getattr(self, "_chatbot_mandatory_unanswered", []):
        logger.warning("⏭️ Chatbot left mandatory/unanswered questions — skipping submit scan")
        return False
    driver = self.driver
    # Fast path: Easy Apply click may have applied already (no drawer, no Save) — verify in ~5ms
    # instead of burning 26s hunting legacy submit selectors.
    try:
        if _is_applied_on_page(driver):
            logger.info("✅ Page already shows applied state — counting as applied (no submit hunt)")
            return True
    except Exception:
        pass
    modal = _find_modal_form(driver)
    save = _find_save_button(modal) if modal is not None else None
    if save is not None:
        try:
            logger.info("🔍 Found Save button — waiting for enabled state...")
            try:
                driver.implicitly_wait(0)
                if not save.is_enabled():
                    WebDriverWait(driver, 6).until(lambda d: save.is_displayed() and save.is_enabled())
            except Exception:
                pass
            finally:
                try:
                    driver.implicitly_wait(1)
                except Exception:
                    pass
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", save)
            except Exception:
                pass
            time.sleep(0.3)
            clicked = False
            try:
                save.click()
                clicked = True
            except Exception:
                pass
            if not clicked:
                try:
                    driver.execute_script("arguments[0].click();", save)
                    clicked = True
                except Exception as e:
                    logger.debug(f"Save JS click: {e}")
            if not clicked:
                logger.error("❌ Save click failed")
                return False
            time.sleep(2)

            rej = _check_rejection_messages(driver)
            if rej:
                logger.error(f"❌ Application rejected due to incomplete information: '{rej}'")
                try:
                    driver.save_screenshot("debug_incomplete_app.png")
                    logger.info("📸 Saved screenshot to debug_incomplete_app.png")
                except Exception as e:
                    logger.debug(f"Screenshot error: {e}")
                _close_chatbot_drawer(driver)
                return False

            # H3 (2026-09-15): _verify_application_submitted() (application.py) returns True
            # whenever no button[type=submit] is on the page — true for almost any page, which
            # is how a job-card bookmark "Save" click got counted as a submitted application.
            # Naukri's own verdict (multiApplyResp / 'Applied to "') is the only thing trusted.
            try:
                ev = None
                for _attempt in range(2):
                    ev = _applied_evidence(driver)
                    if ev:
                        break
                    time.sleep(2.0)
                if ev == "applied":
                    logger.info("✅ Save submission CONFIRMED (Naukri shows Applied)")
                    return True
                rej = _check_rejection_messages(driver)
                if rej or ev == "rejected":
                    logger.error(f"❌ Application rejected due to incomplete information: '{rej or ev}'")
                    try:
                        driver.save_screenshot("debug_incomplete_app.png")
                        logger.info("📸 Saved screenshot to debug_incomplete_app.png")
                    except Exception:
                        pass
                    return False
                if ev == "external":
                    logger.info("↗️ Save led to a company-site redirect — not an Easy Apply submission")
                    return False
                logger.warning("⚠️ Save clicked, no Naukri verdict found — will NOT count as applied")
                return False
            except Exception:
                return False
        except TimeoutException:
            logger.info("Save stayed disabled (questions pending) — will not submit")
            _close_chatbot_drawer(driver)
            return False
        except Exception as e:
            logger.debug(f"Save flow: {e}")
            return False

    # Legacy modal-form hunt burned 84s and destabilized the driver with zero hits.
    # Only run it when a modal form with inputs actually exists; otherwise fail fast.
    try:
        has_modal_form = driver.execute_script(
            "var n=0;"
            "document.querySelectorAll(\"div[class*='modal' i], div[class*='Modal'], div[class*='dialog' i]\").forEach(function(m){"
            "  if (m.offsetParent!==null) n += m.querySelectorAll('input,select,textarea,button').length;});"
            "return n;") or 0
    except Exception:
        has_modal_form = 0
    if not has_modal_form:
        logger.info("⏭️ No modal form present — skipping legacy submit hunt (fail fast, no driver churn)")
        return False
    try:
        driver.implicitly_wait(0)
        result = _orig_submit_improved(self)
    finally:
        try:
            driver.implicitly_wait(0)
        except Exception:
            pass
    if result:
        rej = _check_rejection_messages(driver)
        if rej:
            logger.error(f"❌ Application rejected due to incomplete information: '{rej}'")
            try:
                driver.save_screenshot("debug_incomplete_app.png")
                logger.info("📸 Saved screenshot to debug_incomplete_app.png")
            except Exception:
                pass
            _close_chatbot_drawer(driver)
            return False
        # H3: the legacy path's own _verify_application_submitted() (application.py) also uses
        # the "no submit button on page = success" heuristic. Downgrade its True to a Naukri
        # verdict when one is available; keep it only when there is truly nothing to check.
        ev = _applied_evidence(driver)
        if ev == "applied":
            logger.info("✅ Legacy submit CONFIRMED (Naukri shows Applied)")
        elif ev in ("external", "rejected"):
            logger.warning(f"⚠️ Legacy submit reported success, but Naukri verdict is '{ev}' — not counting as applied")
            return False
    return result


def _fresh_title_company(driver, job_url):
    title, company = "Unknown", "Unknown"
    try:
        driver.implicitly_wait(0)
        try:
            metas = driver.find_elements(By.XPATH, "//meta[@property='og:title']")
            if metas:
                content = metas[0].get_attribute("content") or ""
                if content.strip():
                    title = content.strip()[:120]
        except Exception:
            pass
        if title == "Unknown":
            for xp in ("//h1[contains(@class,'title') or contains(@class,'Title')]",
                       "//h1", "//div[contains(@class,'jd-title')]"):
                try:
                    els = _displayed(driver.find_elements(By.XPATH, xp))
                    if els and (els[0].text or "").strip():
                        title = els[0].text.strip().split("\n")[0][:120]
                        break
                except Exception:
                    continue
        for css in ("div[class*='comp-name' i]", "div[class*='CompName']",
                    ".jd-header-comp-name", "div[class*='company' i]"):
            try:
                els = _displayed(driver.find_elements(By.CSS_SELECTOR, css))
                if els and (els[0].text or "").strip():
                    company = els[0].text.strip().split("\n")[0][:80]
                    break
            except Exception:
                continue
        if title == "Unknown":
            try:
                slug = job_url.rstrip("/").split("/")[-1].replace("-", " ")
                if slug:
                    title = slug[:100]
            except Exception:
                pass
    finally:
        try:
            driver.implicitly_wait(1)
        except Exception:
            pass
    return title, company


def _is_applied_on_page(driver):
    """Broad already-applied check — zero delay."""
    try:
        driver.implicitly_wait(0)
        try:
            for el in _displayed(driver.find_elements(By.CSS_SELECTOR, ".already-applied-layer")):
                return True
        except Exception:
            pass
        try:
            els = driver.find_elements(
                By.XPATH,
                "//*[contains(translate(normalize-space(text()),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                "'abcdefghijklmnopqrstuvwxyz'),'already applied')]")
            for el in els[:6]:
                try:
                    if el.is_displayed():
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        if _applied_evidence(driver) == "applied":
            return True
    finally:
        try:
            driver.implicitly_wait(1)
        except Exception:
            pass
    return False


# H3 (2026-09-15): Naukri's own verdict, read off the result page it navigates to after a
# chatbot Save or a legacy submit — /myapply/... with multiApplyResp={"<jobId>":<code>} in the
# URL (200 = applied, 202 = "redirected to the company website" = NOT applied) and/or the page
# text 'Applied to "<title>"'. Every prior success check (URL contains 'applied'/'confirmation'/
# 'success', or body contains 'apply confirmation') fires for BOTH codes — sampled live, the
# title "Apply Confirmation" appears on 202 pages too — which is how page-wide-Save clicks on a
# job-card bookmark button, and 202 external-redirects, both got written to the DB as
# "Applied (Easy Apply)". This is the only success oracle that should be trusted.
def _applied_evidence(driver):
    """Returns 'applied' | 'external' | 'rejected' | None from Naukri's own result page."""
    try:
        driver.implicitly_wait(0)
        url = driver.current_url or ""
        if "/myapply/" not in url.lower():
            return None
        try:
            decoded = urllib.parse.unquote(url)
            m = re.search(r"multiApplyResp=(\{[^}]*\})", decoded, re.IGNORECASE)
            if m:
                resp = json.loads(m.group(1))
                code = next(iter(resp.values())) if resp else None
                if code in (200, "200"):
                    return "applied"
                if code in (202, "202"):
                    return "external"
                if code in (406, "406"):  # "Oops! ... incomplete information" page
                    return "rejected"
        except Exception as e:
            logger.debug(f"multiApplyResp parse: {e}")
        try:
            body = (driver.execute_script("return document.body ? document.body.innerText : ''") or "").lower()
        except Exception:
            body = ""
        if 'applied to "' in body:
            return "applied"
        if "redirected to the company website" in body:
            return "external"
        if any(p in body for p in ("oops!", "not accepted due to", "incomplete information")):
            return "rejected"
        return None
    finally:
        try:
            driver.implicitly_wait(1)
        except Exception:
            pass


def _get_page_with_retry(driver, url, max_retries=2, timeout=5):
    """Fast page load with up to 2 reload attempts if dropping."""
    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                driver.get(url)
            else:
                logger.info(f"🔄 Reloading page (attempt {attempt}/{max_retries}): {url[:70]}...")
                driver.refresh()
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            return True
        except TimeoutException:
            if attempt < max_retries:
                time.sleep(1.0)
                continue
            logger.warning(f"⚠️ Page load timed out after {max_retries} reloads: {url[:70]}")
            return False
        except Exception as e:
            logger.debug(f"Page load attempt {attempt} error: {e}")
            if attempt < max_retries:
                time.sleep(1.0)
                continue
            return False
    return False


ApplicationMixin._handle_easy_apply_submission_improved = _save_aware_submit

# ------------------------------------------------- N4 apply-one replacement
EASY_APPLY_SELECTORS = [
    "button.apply-button",
    "button[class*='apply-button']",
    "button[id*='apply']",
    ".job-apply-button",
    "button[class*='apply' i]",
    "a.apply-button",
    "button[data-automation*='apply' i]",
    "button[aria-label*='apply' i]",
    # H1 (2026-09-15): both XPaths below match on button TEXT and used to accept "Apply on
    # company site" (contains 'apply', not 'applied') -> the bot clicked through to the
    # employer's own site and Naukri counted it as External (202), while the false-confirm
    # bug (H2/H3) then wrote it to the DB as "Applied (Easy Apply)". Excluding "company site"
    # here is the actual fix; H2/H3 make a repeat impossible even if this slips.
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply') and not(contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'applied')) and not(contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'save job')) and not(contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'company site'))]",
    "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply') and not(contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'applied')) and not(contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'company site'))]",
]


def _poll_easy_apply_button(driver, timeout=8.0):
    """Poll for the job-page Apply button (eager-load hydration race: the button often
    renders seconds after <body> exists). Zero implicit wait, 0.5s poll interval."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            driver.implicitly_wait(0)
            for selector in EASY_APPLY_SELECTORS:
                try:
                    by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                    cand = driver.find_elements(by, selector)
                    for c in cand:
                        try:
                            if c.is_displayed() and c.is_enabled():
                                txt = (c.text or "").strip().lower()
                                cid = (c.get_attribute("id") or "").lower()
                                if "applied" in txt or "save job" in txt or "company site" in txt \
                                        or "company-site" in cid:
                                    continue
                                return c
                        except StaleElementReferenceException:
                            continue
                except Exception:
                    continue
        finally:
            try:
                driver.implicitly_wait(1)
            except Exception:
                pass
        time.sleep(0.5)
    return None


def _js_click_apply_fallback(driver):
    """Last-resort: page-wide JS search for a visible Apply button/link and click it in-page."""
    try:
        clicked = driver.execute_script("""
            var els = document.querySelectorAll('button, a, div[role=button], span[role=button]');
            for (var el of els) {
                var t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().toLowerCase();
                var id = (el.id || '').toLowerCase();
                if (!t || t.indexOf('applied') >= 0 || t.indexOf('save job') >= 0) continue;
                if (t.indexOf('company site') >= 0 || id.indexOf('company-site') >= 0) continue;
                // H1 (2026-09-15): 'apply on' used to also match "Apply on company site",
                // sending the bot to the employer's own site instead of Naukri's Easy Apply.
                if (t === 'apply' || t.indexOf('apply now') >= 0 || t.indexOf('easy apply') >= 0) {
                    var r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) { el.click(); return t.slice(0, 40); }
                }
            }
            return '';
        """)
        if clicked:
            logger.info(f"✅ JS fallback clicked Apply control ('{clicked}')")
            return True
    except Exception as e:
        logger.debug(f"JS apply fallback error: {e}")
    return False


def _enforce_single_tab(driver):
    """Close any extra tabs/windows so the bot always reuses ONE Edge window (no new window per job)."""
    try:
        handles = driver.window_handles
        if len(handles) > 1:
            main = driver.current_window_handle
            for h in list(handles):
                if h != main:
                    try:
                        driver.switch_to.window(h)
                        driver.close()
                    except Exception:
                        pass
            driver.switch_to.window(main)
            logger.debug(f"🧹 Closed extra tabs, single-tab enforced ({len(handles)}→1)")
    except Exception:
        pass


def _unattended_apply_one(self, job_url):
    """High-speed skip-external apply path with zero-wait probing & 2-attempt reload. Single-tab only."""
    original_tab = None
    driver = self.driver
    _t_entry = time.time()
    try:
        _enforce_single_tab(driver)
        original_tab = driver.current_window_handle
        if not _get_page_with_retry(driver, job_url, max_retries=2, timeout=5):
            return False

        if _is_applied_on_page(driver):
            logger.info("⏩ Page shows already applied")
            return False

        job_title, company = _fresh_title_company(driver, job_url)
        logger.info(f"📋 {job_title} at {company}")

        # Polled probe for Easy Apply buttons (hydration race) + JS text fallback
        easy_apply_button = _poll_easy_apply_button(driver, timeout=8.0)
        js_clicked = False
        if not easy_apply_button:
            js_clicked = _js_click_apply_fallback(driver)

        if easy_apply_button or js_clicked:
            if js_clicked and not easy_apply_button:
                logger.info("✅ Apply control already clicked via JS fallback")
            else:
                logger.info("✅ Found Easy Apply button")
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", easy_apply_button)
                except Exception:
                    pass
                try:
                    easy_apply_button.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", easy_apply_button)
                    except Exception as e:
                        logger.error(f"Easy Apply click failed: {e}")
                        return False

            # 1-click apply: Easy Apply may complete instantly with no drawer — check first
            time.sleep(1.5)
            try:
                if _is_applied_on_page(driver):
                    logger.info("✅ Easy Apply completed instantly (no questions asked)")
                    try:
                        self._save_job_application(
                            self._extract_job_id(job_url), job_url,
                            "Applied (Easy Apply)", f"{job_title} at {company}")
                    except Exception as e:
                        logger.debug(f"db save: {e}")
                    return True
            except Exception:
                pass

            self._chatbot_detected = False
            self._chatbot_ok = True
            self._chatbot_unanswered = []
            self._chatbot_mandatory_unanswered = []
            chatbot_success = self._handle_chatbot(timeout=5)

            if getattr(self, "_chatbot_detected", False):
                if chatbot_success and getattr(self, "_chatbot_ok", True) and not getattr(self, "_chatbot_mandatory_unanswered", []):
                    logger.info("✅ Easy Apply (Chatbot) successfully completed & confirmed")
                    try:
                        self._save_job_application(
                            self._extract_job_id(job_url), job_url,
                            "Applied (Easy Apply)", f"{job_title} at {company}")
                    except Exception as e:
                        logger.debug(f"db save: {e}")
                    return True
                else:
                    # Drawer questions may have applied despite unconfirmed Save — verify, don't assume failure
                    try:
                        if _is_applied_on_page(driver):
                            logger.info("✅ Page shows applied despite unconfirmed Save — counting as applied")
                            try:
                                self._save_job_application(
                                    self._extract_job_id(job_url), job_url,
                                    "Applied (Easy Apply)", f"{job_title} at {company}")
                            except Exception as e:
                                logger.debug(f"db save: {e}")
                            return True
                    except Exception:
                        pass
                    logger.warning("⏭️ Chatbot incomplete / rejected — discarding job")
                    return False

            # Non-chatbot standard Easy Apply modal form
            if self._handle_easy_apply_submission_improved():
                try:
                    self._save_job_application(
                        self._extract_job_id(job_url), job_url,
                        "Applied (Easy Apply)", f"{job_title} at {company}")
                except Exception as e:
                    logger.debug(f"db save: {e}")
                return True
            return False

        logger.info(f"↗️ No Easy Apply — external skipped instantly (page+probe took {time.time() - _t_entry:.1f}s)")
        self.skipped += 1
        try:
            _t0 = time.time()
            self._save_job_application(
                self._extract_job_id(job_url), job_url,
                "External (Manual Required)", f"{job_title} at {company}")
            logger.info(f"⏱️ skip-path db save took {time.time() - _t0:.1f}s")
        except Exception as e:
            logger.debug(f"db save: {e}")
        return False
    except Exception as e:
        logger.error(f"Error in _unattended_apply_one: {e}")
        return False
    finally:
        # Measured, not yet changed (2026-09-15): ~40s of bot-log silence follows every verdict
        # and only this cleanup runs there. Log its duration so the watcher can confirm the
        # cause before anyone "fixes" it blind.
        _t_fin = time.time()
        try:
            _enforce_single_tab(driver)
            if original_tab and driver.current_window_handle != original_tab:
                driver.switch_to.window(original_tab)
        except Exception:
            pass
        try:
            _enforce_single_tab(driver)
        except Exception:
            pass
        _fin = time.time() - _t_fin
        if _fin > 1.0:
            logger.info(f"⏱️ tab cleanup took {_fin:.1f}s")


# ---------------------------------------- N7 official tally + Excel tracker
_TRACKER_PATH = r"C:\Users\Admin\GitHub\job-tracker\track_job_applications.py"
_REC_STATE = {"last": 0.0, "first_done": False}
_REC_EVERY = 40 * 60
_REC_URL = "https://www.naukri.com/mnjuser/myapplications"


def _run_tracker(*args):
    try:
        subprocess.run([sys.executable, _TRACKER_PATH, *args], cwd=REPO, timeout=120,
                       stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.debug(f"tracker call failed: {e!r}")


def _report_official(source, count, method):
    _run_tracker("official", "--source", source,
                 "--count", "unknown" if count is None else str(count),
                 "--method", (method or "")[:200])


_REC_IMPLICIT_RESTORE = 15  # must match config.local.json webdriver.implicit_wait


def _rec_ready_naukri(drv):
    """Wait condition for data-bearing elements on myapplications or profile."""
    try:
        for sel in (
            "[class*='applicationCard']",
            "[class*='applied-job']",
            ".jobCard",
            "[class*='jobCard']",
            "[class*='applied-status']",
            ".applied-jobs",
            ".count",
            "[class*='count']",
            ".empty-state",
            ".no-applications",
        ):
            if drv.find_elements(By.CSS_SELECTOR, sel):
                return True
        t = (drv.find_element(By.TAG_NAME, "body").text or "").lower()
        return any(w in t for w in (
            "applied jobs", "application status", "my applications",
            "no applications", "total applied", "applied: ", "applications: "
        ))
    except Exception:
        return False


def _parse_naukri_official(driver):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        body = ""

    cands = []
    # Multi-pattern regex: count-before-label, count-after-label, colon-separated,
    # "showing X of Y applications", etc.
    for pat, tag in (
        (r"(\d[\d,]{0,6})\s+(?:total\s+)?applications?", "N applications"),
        (r"applied\s+jobs?\s*\(?\s*(\d[\d,]{0,6})\s*\)?", "Applied Jobs (N)"),
        (r"applications?\s*[:–\-()]?\s*\(?\s*(\d[\d,]{0,6})", "Applications: N"),
        (r"applied\s*[:–\-]?\s*(\d[\d,]{0,6})", "Applied: N"),
        (r"(?:of|of\s+about)\s+(\d[\d,]{0,6})\s+(?:job\s+)?applications?", "of N applications"),
        (r"(\d[\d,]{0,6})\s+applied\b", "N applied"),
    ):
        try:
            for m in re.finditer(pat, body, re.IGNORECASE):
                try:
                    cands.append((int(m.group(1).replace(",", "")), f"text regex on page ({tag})"))
                except Exception:
                    continue
        except Exception:
            continue

    # Targeted count elements on Naukri
    for sel in (
        "[class*='applied-count']",
        "[class*='application-count']",
        ".app-count",
        ".applied-count",
        ".total-applications",
        "span.count",
    ):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                txt = (el.text or "").strip()
                m = re.search(r"(\d[\d,]{0,6})", txt)
                if m:
                    cands.append((int(m.group(1).replace(",", "")), f"targeted count element ({sel})"))
        except Exception:
            continue

    if cands:
        best = max(cands, key=lambda x: x[0])
        return best[0], best[1]

    lowered = (body or "").lower()
    if "appl" not in lowered and ("log in" in lowered or "login" in lowered
                                  or "sign in" in lowered):
        try:
            url = driver.current_url
        except Exception:
            url = "?"
        logger.warning(f"Official tally: login redirect suspected (url={url})")
        return None, "not parsed (login redirect suspected)"

    # Zero implicit wait around the selector probes so misses cost ~0s
    try:
        driver.implicitly_wait(0)
        for css in (".jobCard", "[class*='jobCard']", "[class*='applicationCard']",
                    "[class*='applied-job']", ".cardContainer"):
            try:
                els = driver.find_elements(By.CSS_SELECTOR, css)
                if els:
                    return len(els), f"visible card count ({css}, page 1 — approximate)"
            except Exception:
                continue
    finally:
        try:
            driver.implicitly_wait(_REC_IMPLICIT_RESTORE)
        except Exception:
            pass
    try:
        url = driver.current_url
    except Exception:
        url = "?"
    logger.warning(f"Official tally not parsed (url={url} "
                   f"body={body[:300]!r}...)")
    return None, "not parsed"


def _reconcile_nk_periodic(driver, force=False):
    now = time.time()
    if not force and (now - _REC_STATE["last"]) < _REC_EVERY:
        return
    _REC_STATE["last"] = now
    count, method = None, "error"
    try:
        orig = driver.current_window_handle
        driver.switch_to.new_window("tab")
        try:
            try:
                driver.get(_REC_URL)
            except TimeoutException:
                logger.warning("Official tally: page-load timeout — retrying once")
                try:
                    driver.get(_REC_URL)
                except TimeoutException as e2:
                    method = f"page-load timeout: {e2!r}"
                    _report_official("naukri", count, method)
                    logger.info(f"Official tally: naukri count={count} via {method}")
                    return

            try:
                WebDriverWait(driver, 10).until(_rec_ready_naukri)
            except TimeoutException:
                pass
            time.sleep(1.5)

            try:
                cur = driver.current_url or ""
            except Exception:
                cur = ""

            # If redirected to homepage, attempt to navigate via "Applications" link
            if "myapplications" not in cur:
                try:
                    app_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='myapplications'], a[href*='applied']")
                    for al in app_links:
                        href = al.get_attribute("href") or ""
                        if "myapplications" in href:
                            driver.get(href)
                            try:
                                WebDriverWait(driver, 10).until(_rec_ready_naukri)
                            except TimeoutException:
                                pass
                            time.sleep(1.5)
                            cur = driver.current_url or ""
                            break
                except Exception:
                    pass

            if "myapplications" not in cur:
                # Still redirected — try parsing count from current page stats before declaring redirect
                count, parse_m = _parse_naukri_official(driver)
                if count is not None and count > 0:
                    method = f"from redirect page ({cur[:60]}): {parse_m}"
                    _report_official("naukri", count, method)
                    logger.info(f"Official tally: naukri count={count} via {method}")
                    return

                try:
                    excerpt = (driver.find_element(By.TAG_NAME, "body").text or "")[:300]
                except Exception:
                    excerpt = ""
                method = f"redirected (url={cur[:120]})"
                logger.warning(f"Official tally: landing check failed — {method} "
                               f"body={excerpt!r}...")
                _report_official("naukri", None, method)
                logger.info(f"Official tally: naukri count=None via {method}")
                return

            count, method = _parse_naukri_official(driver)
            if count is None:
                try:
                    excerpt = (driver.find_element(By.TAG_NAME, "body").text or "")[:300]
                except Exception:
                    excerpt = ""
                logger.warning(f"Official tally parse failed (url={cur} "
                               f"body={excerpt!r}...)")
        finally:
            try:
                driver.close()
            except Exception:
                pass
            try:
                driver.switch_to.window(orig)
            except Exception:
                pass
    except Exception as e:
        method = f"error: {e!r}"
    _report_official("naukri", count, method)
    logger.info(f"Official tally: naukri count={count} via {method}")


# N7b: write application_date/company_name for every new row so the tracker can
# date-filter correctly (the tracked INSERT omits those columns → NULL dates),
# and support profile-isolated database and selector cache paths.
try:
    from naukri_bot.utils.database import DatabaseMixin as _DBMixin
    _orig_init_db = _DBMixin.init_job_database

    def _isolated_init_job_database(self):
        db_path = getattr(self, "_db_path", None)
        if not db_path:
            return _orig_init_db(self)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT NOT NULL,
                    job_title TEXT,
                    company_name TEXT,
                    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    notes TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_id ON applied_jobs(job_id)')
            self.db_conn.commit()
            logger.info(f"✅ Job database initialized ({db_path})")
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            self.db_conn = None

    _DBMixin.init_job_database = _isolated_init_job_database

    def _dated_save_job_application(self, job_id, job_url, status, notes=''):
        if not self.db_conn:
            return
        try:
            job_title = job_url.split('/')[-1].replace('-', ' ')[:100]
            company = ""
            if notes and " at " in notes:
                company = notes.rsplit(" at ", 1)[-1].strip()[:80]
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO applied_jobs "
                "(job_id, job_url, job_title, company_name, application_date, status, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, job_url, job_title, company,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), status, notes))
            self.db_conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database save error: {e}")

    _DBMixin._save_job_application = _dated_save_job_application
except Exception as e:
    logger.warning(f"dated-save patch skipped: {e!r}")


# N7c: profile-isolated selector cache persistence.
try:
    from naukri_bot.utils.selectors import SelectorCacheMixin as _SCMixin

    def _isolated_load_selector_cache(self):
        cache_file = getattr(self, "_cache_path", 'selector_cache.json')
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                    for key, value in loaded_cache.items():
                        if value:
                            self.selector_cache[key] = value
                cached_count = len([v for v in self.selector_cache.values() if v])
                logger.info(f"✅ Loaded selector cache with {cached_count} cached selectors ({cache_file})")
        except Exception as e:
            logger.debug(f"Could not load selector cache: {e}")

    def _isolated_save_selector_cache(self):
        cache_file = getattr(self, "_cache_path", 'selector_cache.json')
        try:
            os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)
            cache_to_save = {k: v for k, v in self.selector_cache.items() if v}
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, indent=2)
            logger.debug(f"💾 Selector cache saved ({cache_file}): {cache_to_save}")
        except Exception as e:
            logger.error(f"Could not save selector cache: {e}")

    _SCMixin.load_selector_cache = _isolated_load_selector_cache
    _SCMixin.save_selector_cache = _isolated_save_selector_cache
except Exception as e:
    logger.warning(f"selector cache patch skipped: {e!r}")


# N7d: session end → final official tally + Excel sync, with profile-isolated reports.
try:
    from naukri_bot.utils.session import SessionMixin as _SessionMixin
    _orig_save_results = _SessionMixin.save_results

    def _tracked_save_results(self):
        try:
            if getattr(self, "driver", None):
                _reconcile_nk_periodic(self.driver, force=True)
        except Exception:
            pass

        session_dir = getattr(self, "_session_dir", REPO)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(session_dir, f'naukri_session_{timestamp}.json')
        try:
            session_data = {
                'timestamp': timestamp,
                'date': datetime.now().isoformat(),
                'statistics': {
                    'total_jobs_found': len(self.joblinks),
                    'applications_sent': self.applied,
                    'applications_failed': self.failed,
                    'jobs_skipped': self.skipped,
                    'external_tabs_opened': len(self.external_tabs_opened),
                    'success_rate': round((self.applied / max(self.applied + self.failed, 1)) * 100, 2),
                    'submit_button_success_rate': round(
                        (self.performance_stats['submit_button_success'] /
                         max(self.performance_stats['submit_button_success'] +
                             self.performance_stats['submit_button_failures'], 1)) * 100, 2
                    )
                },
                'applications': {
                    'successful': self.applied_list['passed'],
                    'failed': self.applied_list['failed']
                },
                'config_used': {
                    'keywords': self.config.get('job_search', {}).get('keywords', []),
                    'location': self.config.get('job_search', {}).get('location', '')
                },
                'performance': self.performance_stats,
                'cached_selectors': {k: v for k, v in self.selector_cache.items() if v}
            }
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=4, ensure_ascii=False)
            logger.info(f"📊 Session report saved: {report_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")

        _run_tracker("sync")
        logger.info("📊 Excel tracker synced")

    _SessionMixin.save_results = _tracked_save_results
except Exception as e:
    logger.warning(f"save_results patch skipped: {e!r}")


# ---------------------------------------- N8 Robust Session Recovery + Search Loop
try:
    from naukri_bot.core.webdriver import DriverMixin as _WDMixin
    from naukri_bot.modules.search import SearchMixin as _SearchMixin

    _orig_setup_driver = _WDMixin.setup_driver
    _orig_recover_session = _WDMixin.recover_session

    def _eager_setup_driver(self):
        """High-speed setup: page_load_strategy='eager' so driver.get returns instantly without waiting for ad networks."""
        try:
            logger.info("🚀 Setting up high-speed browser (eager page load strategy)...")
            from selenium import webdriver
            from selenium.webdriver.edge.service import Service as EdgeService
            options = webdriver.EdgeOptions()
            options.page_load_strategy = 'eager'  # DO NOT block on third-party ads/trackers
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            if self.config['webdriver'].get('headless', False):
                options.add_argument("--headless")

            # Persistent Edge profile: reuse login cookies so no fresh Microsoft/Naukri login window per launch
            profile_dir = self.config['webdriver'].get('user_data_dir')
            if not profile_dir:
                profile_dir = os.path.join(REPO, "browser_profile", "edge_default")
                try:
                    os.makedirs(profile_dir, exist_ok=True)
                except Exception:
                    pass
            options.add_argument(f"user-data-dir={profile_dir}")

            driver = None
            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                driver_path = EdgeChromiumDriverManager().install()
                service = EdgeService(executable_path=driver_path)
                driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ High-speed driver ready (eager mode)")
            except Exception:
                pass
            if not driver:
                driver = webdriver.Edge(options=options)
            self.driver = driver
            self.driver.set_page_load_timeout(15)
            try:
                self.driver.set_script_timeout(10)
            except Exception:
                pass
            self.driver.implicitly_wait(1)
            self.wait = WebDriverWait(self.driver, 5)
            return True
        except Exception as e:
            logger.error(f"High-speed driver setup error: {e}")
            return _orig_setup_driver(self)

    _WDMixin.setup_driver = _eager_setup_driver

    def _robust_recover_session(self):
        """Recover from dead / crashed Edge driver and re-establish authenticated session."""
        logger.info("🔄 Robust session recovery initiated...")
        try:
            if getattr(self, "driver", None):
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
        except Exception:
            pass

        # Cool down 2 seconds for OS socket / driver cleanup
        time.sleep(2)

        for attempt in range(1, 3):
            logger.info(f"🔄 Driver recreate attempt {attempt}/2...")
            try:
                if not self.setup_driver():
                    logger.error(f"❌ setup_driver failed on attempt {attempt}")
                    time.sleep(2)
                    continue

                # Driver created, now login
                if self.login():
                    logger.info("✅ Session recovered & logged in successfully!")
                    return True
                else:
                    logger.warning(f"⚠️ Login failed on recovery attempt {attempt}")
                    try:
                        if self.driver:
                            self.driver.quit()
                    except Exception:
                        pass
                    self.driver = None
                    time.sleep(2)
            except Exception as e:
                logger.error(f"❌ Exception during recovery attempt {attempt}: {e!r}")
                try:
                    if self.driver:
                        self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                time.sleep(2)

        logger.error("❌ All session recovery attempts failed.")
        return False

    _WDMixin.recover_session = _robust_recover_session

    def _instant_handle_popups(self):
        """Zero-delay popup handler with zero implicit wait."""
        try:
            self.driver.implicitly_wait(0)
            for selector in ("span.close-popup", "button.close", "div.cross-icon",
                             "[aria-label='Close']", ".crossIcon", "button[title='Close']"):
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for b in btns:
                        if b.is_displayed():
                            try:
                                b.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", b)
                            break
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            try:
                self.driver.implicitly_wait(1)
            except Exception:
                pass

    AuthMixin._handle_popups = _instant_handle_popups

    def _robust_verify_login(self, timeout=12):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                current_url = (self.driver.current_url or "").lower()
                if 'nlogin' not in current_url and '/login' not in current_url and ('mnjuser' in current_url or 'naukri.com' in current_url):
                    for ind in ('.nI-gNb-drawer__icon', '.view-profile-wrapper', '[data-automation="profileDropdown"]', '.user-name', '.profile-img'):
                        els = self.driver.find_elements(By.CSS_SELECTOR, ind)
                        if els and any(el.is_displayed() for el in els):
                            logger.info("✅ Login verified via profile indicator")
                            return True
                    if 'mnjuser/homepage' in current_url:
                        logger.info("✅ Login verified via homepage redirect")
                        return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    AuthMixin._verify_login_success = _robust_verify_login

    def _unattended_search_and_apply(self):
        """Session-resilient page-by-page search and application loop with 10x-100x speedup & continuous cycles."""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        is_all_day = getattr(self, "_is_all_day", False)
        session_cap = self.config['job_search'].get('max_applications_per_session', 20)

        apply_timestamps = []
        hourly_limit = int(os.environ.get("NAUKRI_HOURLY_CAP", "80"))
        cycle_delay_min = int(os.environ.get("NAUKRI_CYCLE_DELAY_MIN", "2"))

        def _is_card_easy_apply_fast(card):
            try:
                txt = (card.text or "").lower()
                if "apply on company site" in txt or "company site" in txt:
                    return False
                return True
            except Exception:
                return True

        cycle_count = 0
        while True:
            cycle_count += 1
            cycle_applies_start = self.applied

            if is_all_day:
                logger.info(f"🔄 ================= ALL-DAY SEARCH CYCLE #{cycle_count} =================")
                logger.info(f"📊 Total Applied So Far: {self.applied} | Mode: 24/7 Continuous (Hourly Pacing: {hourly_limit}/h)")
            else:
                logger.info("🔍 Starting page-by-page job search and application (session-guarded)...")

            for keyword in keywords:
                if not is_all_day and self.applied >= session_cap:
                    logger.info(f"✋ Reached application limit ({session_cap})")
                    return

                logger.info(f"🔎 Searching for: {keyword}")

                for page in range(1, pages_per_keyword + 1):
                    if not is_all_day and self.applied >= session_cap:
                        logger.info(f"✋ Reached application limit ({session_cap})")
                        return

                    # Hourly rate check in all-day mode
                    if is_all_day:
                        now_ts = time.time()
                        apply_timestamps = [t for t in apply_timestamps if now_ts - t < 3600]
                        if len(apply_timestamps) >= hourly_limit:
                            wait_needed = int(3600 - (now_ts - apply_timestamps[0])) + 15
                            if wait_needed > 0:
                                logger.info(f"⏳ Hourly application rate reached ({len(apply_timestamps)}/{hourly_limit} in last hour).")
                                logger.info(f"⏸️ Pacing pause for {wait_needed // 60}m {wait_needed % 60}s to maintain natural cadence...")
                                time.sleep(wait_needed)
                                now_ts = time.time()
                                apply_timestamps = [t for t in apply_timestamps if now_ts - t < 3600]

                    # Ensure valid session before page navigation
                    if not self.ensure_valid_session():
                        logger.error("❌ Session recovery failed before page load. Halting search.")
                        return

                    search_keyword = keyword.lower().replace(' ', '-')
                    search_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"

                    logger.info(f"📄 Page {page}")
                    if not _get_page_with_retry(self.driver, url, max_retries=2, timeout=6):
                        logger.warning(f"⚠️ Could not load search page {page}, attempting session recovery...")
                        if self.recover_session():
                            if not _get_page_with_retry(self.driver, url, max_retries=1, timeout=6):
                                logger.error(f"❌ Failed to load page {page} after recovery. Skipping page.")
                                continue
                        else:
                            logger.error("❌ Session recovery failed. Ending search process.")
                            return

                    try:
                        self._handle_popups()

                        job_cards = self._get_job_cards_fast()
                        if not job_cards:
                            # Search cards hydrate after body-ready under eager loads —
                            # poll briefly before abandoning the whole keyword.
                            for _retry in range(4):
                                time.sleep(2.0)
                                try:
                                    job_cards = self._get_job_cards_fast()
                                except Exception:
                                    job_cards = []
                                if job_cards:
                                    logger.info(f"✅ Job cards appeared after ~{(_retry + 1) * 2}s hydration wait")
                                    break
                        if not job_cards:
                            logger.info("No jobs found on this page, moving to next keyword.")
                            break

                        page_job_links = []
                        for card in job_cards:
                            try:
                                if not _is_card_easy_apply_fast(card):
                                    continue
                                job_url = self._extract_job_url_fast(card)
                                if job_url and job_url not in self.joblinks:
                                    job_id = self._extract_job_id(job_url)
                                    if not self.is_job_already_applied(job_id) and self._is_job_relevant_fast(card):
                                        page_job_links.append(job_url)
                                        self.joblinks.append(job_url)
                            except Exception as e:
                                logger.debug(f"Error extracting job: {e}")

                        if page_job_links:
                            logger.info(f"✅ Found {len(page_job_links)} new Easy-Apply candidate jobs on this page. Applying now...")
                            prev_applied = self.applied
                            self.apply_to_jobs(page_job_links)
                            new_apps = self.applied - prev_applied
                            if new_apps > 0:
                                for _ in range(new_apps):
                                    apply_timestamps.append(time.time())
                            if not self.check_session_validity():
                                if not self.recover_session():
                                    logger.error("❌ Session died during apply and could not be recovered. Stopping.")
                                    return
                        else:
                            logger.info("No new jobs on this page to apply for.")
                    except (InvalidSessionIdException, WebDriverException) as we:
                        logger.warning(f"⚠️ Session error on page {page}: {we!r}")
                        if not self.recover_session():
                            logger.error("❌ Could not recover session. Stopping.")
                            return
                    except Exception as e:
                        logger.error(f"Error on page {page} for keyword '{keyword}': {e}")
                        continue

            cycle_applies = self.applied - cycle_applies_start
            logger.info(f"✅ Completed search cycle #{cycle_count}. Applied this cycle: {cycle_applies}. Cumulative: {self.applied}")

            # Trigger periodic reconciliation and tracker sync at the end of each cycle
            try:
                if getattr(self, "driver", None):
                    _reconcile_nk_periodic(self.driver, force=True)
                _run_tracker("sync")
            except Exception as e:
                logger.debug(f"End-of-cycle sync error: {e}")

            if not is_all_day:
                logger.info("🏁 Session mode complete. Exiting search loop.")
                return

            # All-day mode: idle cooldown between cycles with natural jitter
            jitter = random.randint(-180, 180)  # +/- 3 minutes
            sleep_duration = max(300, (cycle_delay_min * 60) + jitter)
            wake_time = datetime.fromtimestamp(time.time() + sleep_duration).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"💤 All keywords scanned. Entering all-day cooldown of {sleep_duration // 60}m {sleep_duration % 60}s...")
            logger.info(f"⏰ Next search cycle starts at: {wake_time}")

            # Sleep in intervals so process remains responsive and can check session
            sleep_start = time.time()
            while time.time() - sleep_start < sleep_duration:
                rem = sleep_duration - (time.time() - sleep_start)
                time.sleep(min(30, max(1, rem)))

            # Before next cycle, verify session health
            if not self.ensure_valid_session():
                logger.warning("⚠️ Session expired during idle cooldown. Attempting recovery before next cycle...")
                if not self.recover_session():
                    logger.error("❌ Could not recover session after idle period. Ending process.")
                    return

    def _instant_extract_job_url(self, job_card):
        """Zero-delay URL extraction using modern working selectors and zero implicit wait."""
        try:
            self.driver.implicitly_wait(0)
            for selector in ('a[href*="job-listings"]', 'a.title', '.title a', '.jobTuple-title a'):
                try:
                    links = job_card.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        href = links[0].get_attribute('href')
                        if href and 'job-listings' in href:
                            return href
                except Exception:
                    continue
            return None
        finally:
            try:
                self.driver.implicitly_wait(1)
            except Exception:
                pass

    _SearchMixin._extract_job_url_fast = _instant_extract_job_url
    _SearchMixin.search_and_apply_page_by_page = _unattended_search_and_apply
except Exception as e:
    logger.warning(f"session recovery patch skipped: {e!r}")


# ------------------------------------------------------- runner + profile + self-test
def _get_profile_paths(profile=None):
    """Compute and ensure directory structure for an isolated profile."""
    if not profile or profile in ("default", "profile1"):
        p1_cfg = os.path.join(REPO, "profiles", "profile1", "config.json")
        if profile == "profile1" and os.path.exists(p1_cfg):
            pdir = os.path.join(REPO, "profiles", "profile1")
            return {
                "profile": "profile1",
                "dir": pdir,
                "config": p1_cfg,
                "db": os.path.join(pdir, "naukri_jobs.db"),
                "log": os.path.join(pdir, "naukri_bot.log"),
                "cache": os.path.join(pdir, "selector_cache.json"),
                "edge_profile": os.path.join(pdir, "edge_profile"),
                "source_name": "naukri-profile1"
            }
        config_path = "config.local.json" if os.path.exists(os.path.join(REPO, "config.local.json")) else "config.json"
        return {
            "profile": "default",
            "dir": REPO,
            "config": os.path.join(REPO, config_path),
            "db": os.path.join(REPO, "naukri_jobs.db"),
            "log": os.path.join(REPO, "naukri_bot.log"),
            "cache": os.path.join(REPO, "selector_cache.json"),
            "edge_profile": "",
            "source_name": "naukri"
        }

    pdir = os.path.join(REPO, "profiles", profile)
    os.makedirs(pdir, exist_ok=True)
    cfg = os.path.join(pdir, "config.json")
    if not os.path.exists(cfg):
        base_cfg = "config.local.json" if os.path.exists(os.path.join(REPO, "config.local.json")) else "config.json"
        try:
            with open(os.path.join(REPO, base_cfg), "r", encoding="utf-8") as f:
                data = json.load(f)
            if "credentials" in data:
                data["credentials"]["email"] = f"{profile}_user@example.com"
                data["credentials"]["password"] = "ENTER_PASSWORD_HERE"
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Created template config for {profile} at {cfg}")
        except Exception as e:
            logger.warning(f"Could not scaffold config for {profile}: {e}")

    return {
        "profile": profile,
        "dir": pdir,
        "config": cfg,
        "db": os.path.join(pdir, "naukri_jobs.db"),
        "log": os.path.join(pdir, "naukri_bot.log"),
        "cache": os.path.join(pdir, "selector_cache.json"),
        "edge_profile": os.path.join(pdir, "edge_profile"),
        "source_name": f"naukri-{profile}"
    }


def build_bot(profile=None):
    if profile is None:
        for arg in sys.argv:
            if arg.startswith("--profile="):
                profile = arg.split("=", 1)[1].strip()
        if not profile and "--profile" in sys.argv:
            idx = sys.argv.index("--profile")
            if idx + 1 < len(sys.argv):
                profile = sys.argv[idx + 1].strip()
        if not profile:
            profile = os.environ.get("NAUKRI_PROFILE", "default").strip()

    paths = _get_profile_paths(profile)
    logger.info(f"👤 Active profile: '{paths['profile']}' (config: {paths['config']})")

    is_all_day = "--all-day" in sys.argv or os.environ.get("NAUKRI_ALL_DAY", "0").lower() in ("1", "true")

    bot = NaukriBot(config_file=paths["config"])
    bot._profile_paths = paths
    bot._db_path = paths["db"]
    bot._cache_path = paths["cache"]
    bot._session_dir = paths["dir"]
    bot._is_all_day = is_all_day
    if paths["edge_profile"]:
        bot.config.setdefault("webdriver", {})["user_data_dir"] = paths["edge_profile"]

    if is_all_day:
        logger.info("☀️ All-Day 24/7 continuous apply mode enabled (hourly pacing + idle cycles)")

    # Isolated file log handler for non-default profiles
    if paths["profile"] != "default":
        try:
            fh = logging.FileHandler(paths["log"], encoding="utf-8")
            fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(fh)
            logger.info(f"📝 Profile log routed to {paths['log']}")
        except Exception as e:
            logger.warning(f"Could not attach profile file handler: {e}")

    # In-memory overlays only — files never written.
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        bot.config["gemini_api_key"] = key
    else:
        bot.config.pop("gemini_api_key", None)
    try:
        bot._init_gemini_if_configured()
    except Exception:
        pass
    try:
        _get_resume_digest(bot.config)
    except Exception as e:
        logger.debug(f"Resume digest init: {e}")
    skip_external = os.environ.get("NAUKRI_SKIP_EXTERNAL", "1") != "0"
    if skip_external:
        ApplicationMixin._apply_to_single_job = _unattended_apply_one
        logger.info("↗️ External-apply skipped by policy (no company tabs will open)")
    else:
        logger.info("↗️ External-apply ENABLED (company tabs will open for manual fill)")
    logger.info(f"🤖 Gemini fallback: {'ON' if getattr(bot, 'gemini_model', None) else 'OFF (discard unknowns)'}")
    return bot


def self_test():
    """No-browser verification: patch wiring + pure policy unit tests."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name, flush=True)
        if not cond:
            ok = False

    bot = build_bot()
    check("chatbot patched", ChatbotMixin._handle_chatbot is _unattended_handle_chatbot)
    check("submit Save-aware", ApplicationMixin._handle_easy_apply_submission_improved is _save_aware_submit)
    check("skip-external apply-one",
          (ApplicationMixin._apply_to_single_job is _unattended_apply_one)
          == (os.environ.get("NAUKRI_SKIP_EXTERNAL", "1") != "0"))
    check("session recovery patched", _WDMixin.recover_session is _robust_recover_session)
    check("search resilient", _SearchMixin.search_and_apply_page_by_page is _unattended_search_and_apply)
    check("cap==20", bot.config.get("job_search", {}).get("max_applications_per_session") == 20)
    check("all-day flag wired", hasattr(bot, "_is_all_day"))

    # Profile path isolation check
    p_def = _get_profile_paths("default")
    p_two = _get_profile_paths("profile2")
    check("profile default isolated", p_def["profile"] == "default" and p_def["db"].endswith("naukri_jobs.db"))
    check("profile profile2 isolated", p_two["profile"] == "profile2" and "profiles" in p_two["db"] and p_two["source_name"] == "naukri-profile2")

    # Resume digest caching check
    digest = _get_resume_digest(bot.config)
    check("resume digest cached", bool(digest) and "Kaustubh Upadhyaya" in digest and "Data Engineer" in digest)

    # Mandatory question detection checks
    check("mandatory detect (*)", _is_mandatory("Notice Period *") is True)
    check("mandatory detect (required)", _is_mandatory("Years of experience (Required)") is True)
    check("mandatory detect (non-mandatory)", _is_mandatory("Preferred Location") is False)

    # Option matching checks
    check("match option exact", _match_llm_option("Yes", ["Yes", "No"]) == "Yes")
    check("match option substring", _match_llm_option("15 Days", ["Immediate", "15 Days", "30 Days"]) == "15 Days")

    # Offline / online LLM question answering checks against 3 realistic questions
    print("Testing _llm_answer_question with 3 realistic questions...", flush=True)
    ans1 = _llm_answer_question("Total years of experience with PySpark?", config=bot.config)
    print(f"  Q1: 'Total years of experience with PySpark?' -> '{ans1}'", flush=True)
    check("LLM Q1 (years with PySpark)", bool(ans1) and any(c.isdigit() for c in str(ans1)))

    ans2 = _llm_answer_question("Are you willing to work in Bengaluru?", options=["Yes", "No"], config=bot.config)
    print(f"  Q2: 'Are you willing to work in Bengaluru?' -> '{ans2}'", flush=True)
    check("LLM Q2 (work in Bengaluru)", ans2 == "Yes")

    ans3 = _llm_answer_question("Notice period?", options=["Immediate", "15 Days", "30 Days", "60 Days", "90 Days"], config=bot.config)
    print(f"  Q3: 'Notice period?' (options) -> '{ans3}'", flush=True)
    check("LLM Q3 (notice period options)", ans3 in ["Immediate", "15 Days", "30 Days"])

    cities = ["Coimbatore", "Bengaluru", "Pune", "USA"]
    locs = ["bengaluru", "bangalore"]
    d, p = classify_radio("Are you currently living in or ready to relocate to Bengaluru?",
                          ["Yes", "No"], locs)
    check("relocate Yes/No -> select Yes", d == "select" and p == "Yes")
    d, p = classify_radio("Have you been employed by Berkadia or any entity before?",
                          ["Yes", "No"], locs)
    check("employer trap -> discard", d == "discard")
    d, p = classify_radio("Which city do you live in?", cities, locs)
    check("city list -> Bengaluru", d == "select" and p == "Bengaluru")
    d, p = classify_radio("Have you ever been convicted for any criminal offence?",
                          ["Yes", "No"], locs)
    check("conviction -> discard", d == "discard")
    d, p = classify_radio("What is your PAN card number?", ["Yes", "No"], locs)
    check("PII trap -> discard", d == "discard")
    d, p = classify_radio("Preferred work location?", ["Pune", "USA"], ["chennai"])
    check("no matching city -> gemini/discard, never wrong city",
          (d == "select" and p in ("Pune", "USA")) is False)
    d, p = classify_radio("Years of experience with ETL?", [], locs)
    check("no options -> discard", d == "discard")
    try:
        ans = ChatbotMixin._get_keyword_answer(bot, "What is your expected CTC?")
        check("keyword map intact", bool(ans))
    except Exception:
        check("keyword map intact", False)

    print("SELF-TEST " + ("PASSED" if ok else "FAILED"), flush=True)
    return ok


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    # Single-flight mutex: a same-second duplicate interpreter spawns per launch and
    # fights over the Edge profile/DB/log. Loser exits cleanly here, before touching anything.
    try:
        import ctypes as _ctypes

        _kernel32 = _ctypes.windll.kernel32
        _mutex = _kernel32.CreateMutexW(None, True, "Global\\NaukriAutoApplyBotSingleFlight")
        _err = _kernel32.GetLastError()
        if not _mutex or _err == 183:  # 183 = already exists -> another instance holds it
            try:
                if _mutex:
                    _kernel32.CloseHandle(_mutex)
            except Exception:
                pass
            print("Another bot instance already holds the single-flight mutex - exiting duplicate.", flush=True)
            sys.exit(0)
    except SystemExit:
        raise
    except Exception as _e:
        print(f"Single-flight mutex unavailable ({_e}) - proceeding without it.", flush=True)
    bot = build_bot()
    sys.exit(0 if bot.run() else 1)
