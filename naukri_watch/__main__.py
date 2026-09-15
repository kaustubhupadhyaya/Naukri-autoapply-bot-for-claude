"""CLI: python -m naukri_watch [live|postmortem] ...  (see watch.cmd)"""
import argparse
import os
import re
import sys
import time

from . import live, postmortem

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _duration(s):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd]?)", s.strip().lower())
    if not m:
        raise argparse.ArgumentTypeError("use e.g. 90m, 6h, 2d")
    return float(m.group(1)) * {"": 3600, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="naukri_watch", description="Separate failure watcher for the Naukri bot.")
    sub = ap.add_subparsers(dest="mode")
    lv = sub.add_parser("live", help="attach to the running bot (read-only) and record failures as they happen")
    lv.add_argument("--minutes", type=float, default=None, help="stop after N minutes (default: until Ctrl+C)")
    lv.add_argument("--poll", type=float, default=1.0, help="page probe interval in seconds")
    pm = sub.add_parser("postmortem", help="classify past attempts from naukri_bot.log only")
    pm.add_argument("--since", type=_duration, default=_duration("6h"), help="window, e.g. 90m, 6h, 2d")
    pm.add_argument("--echo", action="store_true", help="print every incident")
    args = ap.parse_args(argv)
    mode = args.mode or "live"

    run_dir = os.path.join(REPO, "watch_runs", time.strftime("%Y%m%d_%H%M%S") + "_" + mode)
    os.makedirs(run_dir, exist_ok=True)
    if mode == "postmortem":
        tracker, path = postmortem.run(run_dir, args.since, echo=args.echo)
    else:
        tracker, path = live.run(run_dir, minutes=getattr(args, "minutes", None), poll_s=getattr(args, "poll", 1.0))
    high = sum(1 for i in tracker.incidents if i["severity"] == "high")
    print(f"\n{len(tracker.attempts)} attempts, {len(tracker.incidents)} incidents ({high} high). Report: {path}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
