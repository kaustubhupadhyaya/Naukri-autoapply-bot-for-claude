"""12-Hour Telemetry & Performance Monitor for Naukri Autoapplier.

Polls telemetry events, summarizes question formats, model handling, and speed metrics.
Maintains a live report at naukri_telemetry_summary.md.
"""
import os
import sys
import time
import json
from datetime import datetime
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
TELEMETRY_FILE = os.path.join(REPO, "naukri_telemetry_12h.jsonl")
SUMMARY_FILE = os.path.join(REPO, "naukri_telemetry_summary.md")
BOT_LOG = os.path.join(REPO, "naukri_bot.log")


def parse_telemetry():
    if not os.path.exists(TELEMETRY_FILE):
        return []
    records = []
    try:
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return records


def generate_summary(records, elapsed_seconds, max_seconds):
    total = len(records)
    fmt_counter = Counter(r.get("format") for r in records)
    success_counter = Counter(f"{r.get('format')}:{'success' if r.get('success') else 'fail'}" for r in records)
    
    questions = []
    for r in records:
        q = r.get("question")
        if q and q not in ("application_rejected", "drawer_save", "chatbot_drawer"):
            questions.append({
                "time": r.get("timestamp"),
                "format": r.get("format"),
                "question": q,
                "answer": r.get("answer"),
                "success": r.get("success")
            })

    # Count applications and rejections
    rejections = [r for r in records if r.get("format") == "rejection"]
    saves = [r for r in records if r.get("format") == "save_submission"]
    
    hours_run = round(elapsed_seconds / 3600, 2)
    hours_rem = max(0, round((max_seconds - elapsed_seconds) / 3600, 2))

    lines = [
        "# Naukri Autoapplier — 12-Hour Telemetry & Performance Summary",
        f"\n**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Monitoring Duration:** {hours_run} hours elapsed / {hours_rem} hours remaining (Target: 12h)\n",
        "## 1. Questions & Formats Encountered",
        f"- **Total Interaction Events:** {total}",
        f"- **Text Inputs (`text_input`):** {fmt_counter.get('text_input', 0)}",
        f"- **Quick-Reply Chips (`quick_reply_chip`):** {fmt_counter.get('quick_reply_chip', 0)}",
        f"- **Radio Buttons (`radio_button`):** {fmt_counter.get('radio_button', 0)}",
        f"- **Dropdown Selects (`dropdown_select`):** {fmt_counter.get('dropdown_select', 0)}",
        f"- **Save Submissions (`save_submission`):** {len(saves)}",
        f"- **Rejections Caught (`rejection`):** {len(rejections)}\n",
        "## 2. Model & Applier Handling Breakdown",
        "| Format | Successful Actions | Failed / Discarded | Notes |",
        "|---|---|---|---|",
        f"| Text Input | {success_counter.get('text_input:success', 0)} | {success_counter.get('text_input:fail', 0)} | Handled via Local Proxy / OpenCode Zen |",
        f"| Quick-Reply Chip | {success_counter.get('quick_reply_chip:success', 0)} | {success_counter.get('quick_reply_chip:fail', 0)} | Native instant bubble commit |",
        f"| Radio Button | {success_counter.get('radio_button:success', 0)} | {success_counter.get('radio_button:fail', 0)} | Safe defaults + LLM selection |",
        f"| Dropdown Select | {success_counter.get('dropdown_select:success', 0)} | {success_counter.get('dropdown_select:fail', 0)} | Native Select & custom dropdowns |",
        f"| Form Submission | {success_counter.get('save_submission:success', 0)} | {len(rejections)} | Verified against incomplete banner |\n",
        "## 3. Recent Questions Log (Last 15)"
    ]

    if not questions:
        lines.append("\n*No question events recorded yet in this monitoring cycle.*")
    else:
        lines.append("\n| Timestamp | Format | Question | Answer Given | Status |")
        lines.append("|---|---|---|---|---|")
        for q in questions[-15:]:
            st = "✅" if q["success"] else "❌"
            q_clean = q["question"].replace("|", "\\|")[:80]
            ans_clean = str(q["answer"]).replace("|", "\\|")[:50]
            lines.append(f"| {q['time']} | `{q['format']}` | {q_clean} | {ans_clean} | {st} |")

    return "\n".join(lines) + "\n"


def run_monitor(duration_hours=12, interval_seconds=30):
    max_seconds = duration_hours * 3600
    start_time = time.time()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Started 12-Hour Naukri Telemetry Monitor.")
    print(f"Writing live summary to: {SUMMARY_FILE}")

    while True:
        elapsed = time.time() - start_time
        if elapsed >= max_seconds:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitoring cycle of {duration_hours}h complete.")
            break

        records = parse_telemetry()
        summary_md = generate_summary(records, elapsed, max_seconds)
        try:
            with open(SUMMARY_FILE, "w", encoding="utf-8") as sf:
                sf.write(summary_md)
        except Exception as e:
            pass

        time.sleep(interval_seconds)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        rec = parse_telemetry()
        print(generate_summary(rec, 0, 12 * 3600))
    else:
        dur = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
        run_monitor(duration_hours=dur)
