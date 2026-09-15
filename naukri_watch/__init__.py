"""Naukri failure watcher: a separate, manually-triggered observer of the auto-apply bot.

It never drives the browser. `live` attaches to the bot's Edge over CDP (read-only) and
tails naukri_bot.log; `postmortem` reads the log + DB only. Both write a run folder under
watch_runs/ with incidents.jsonl, questions.jsonl and report.md.

    watch.cmd                      (live, until Ctrl+C)
    watch.cmd live --minutes 30
    watch.cmd postmortem --since 6h
"""
