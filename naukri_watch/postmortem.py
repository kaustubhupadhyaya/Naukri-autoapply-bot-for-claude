"""Postmortem mode: classify past attempts from naukri_bot.log alone (no browser needed)."""
import os
import time

from . import logtail, report
from .analysis import Tracker

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO, "naukri_bot.log")


def run(run_dir, since_s, echo=False):
    start = time.time() - since_s
    events = logtail.read_since(LOG_PATH, start)
    tracker = Tracker(run_dir, "postmortem", echo=echo)
    for ev in events:
        tracker.on_log(ev)
    end = events[-1].ts if events else time.time()
    tracker.finish(end)
    path = report.write(tracker, os.path.join(run_dir, "report.md"), start, end,
                        f"postmortem of the last {since_s / 3600:.1f}h")
    return tracker, path
