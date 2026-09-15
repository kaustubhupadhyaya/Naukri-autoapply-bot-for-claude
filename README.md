# Naukri-automatic-job-apply-bot
Automation that applies to jobs on Naukri.com easily for fatster job hunting and it uses Selenium package for browser automation.

## When in doubt: `watch.cmd`

A separate, read-only failure watcher. It never clicks or navigates. `live` attaches to the running bot's
own Edge over CDP and tails `naukri_bot.log`. `postmortem` needs only the log.

```
watch.cmd                          live, until Ctrl+C
watch.cmd live --minutes 30
watch.cmd postmortem --since 6h    no browser needed
```

Each run writes `watch_runs/<time>_<mode>/`:
- `report.md`: outcomes as the bot believed them vs Naukri's verdict, incidents by class, where the time went.
- `incidents.jsonl`: every finding, with its evidence.
- `questions.jsonl`: every chat-window question and its control type.
- `network.jsonl`: Naukri apply/chatbot requests.
- `samples/`: drawer HTML for each new question format.

Naukri's verdict is the only proof of an application. After applying, the page URL carries
`multiApplyResp={"<jobId>": code}`: **200** applied, **202** redirected to the company site (not applied),
**406** "Oops! … incomplete information".

The chat window is handled by `naukri_bot/chatdrawer/` (v2). Turn it on with `"chat_engine": "v2"` under
`bot_behavior` in `config.local.json`; v1 is used otherwise. `personal_info.date_of_birth` ("DD/MM/YYYY")
and `personal_info.languages` (a list) answer the questions those fields cover.

Why the earlier fixes failed: `docs/STRUCTURAL_FAULTS.md`.

## Steps to run the Mozilla file

- Open/Download Mozilla browser
- Open a new tab and type about:profiles
- Create a new profile and launch the new profile
- Login into Naukri.com into the new profile.
- goto about:profiles and Copy the path of the Root Directory
- Open Naukri-auto-apply-bot python file and paste the path in profiles variable
- Add your Firstname, Lastname, keywords(Job roles) and location(optional)
- Run the Naukri-autoapply bot by python Naukri-Mozilla.py
- Please note this script was built in selenium version 3

## Steps to run the Edge file
- Download Edge driver and include its filepath in the naukri-Edge file
- Add your Firstname, Lastname, keywords(Job roles) and location(optional)
- Run the Naukri-autoapply bot by python Naukri-Edge.py
- Please note this script was built in selenium version 4



- Last run: 2025-09-29T19:35:10.210758 UTC
- Jobs discovered: 90
- Applied (easy apply): 0
- Skipped (external): 11


- Last run: 2025-09-30T19:28:12.764881 UTC
- Jobs discovered: 128
- Applied (easy apply): 0
- Skipped (external): 58
