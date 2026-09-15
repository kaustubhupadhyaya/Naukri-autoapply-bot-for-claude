# Naukri Autoapplier — 12-Hour Telemetry & Performance Summary

**Last Updated:** 2026-09-15 04:44:39  
**Monitoring Duration:** 6.41 hours elapsed / 5.59 hours remaining (Target: 12h)

## 1. Questions & Formats Encountered
- **Total Interaction Events:** 138
- **Text Inputs (`text_input`):** 57
- **Quick-Reply Chips (`quick_reply_chip`):** 32
- **Radio Buttons (`radio_button`):** 15
- **Dropdown Selects (`dropdown_select`):** 0
- **Save Submissions (`save_submission`):** 2
- **Rejections Caught (`rejection`):** 32

## 2. Model & Applier Handling Breakdown
| Format | Successful Actions | Failed / Discarded | Notes |
|---|---|---|---|
| Text Input | 57 | 0 | Handled via Local Proxy / OpenCode Zen |
| Quick-Reply Chip | 32 | 0 | Native instant bubble commit |
| Radio Button | 15 | 0 | Safe defaults + LLM selection |
| Dropdown Select | 0 | 0 | Native Select & custom dropdowns |
| Form Submission | 2 | 32 | Verified against incomplete banner |

## 3. Recent Questions Log (Last 15)

| Timestamp | Format | Question | Answer Given | Status |
|---|---|---|---|---|
| 2026-09-15 03:04:56 | `text_input` | How many years of experience do you have in .Net Core? | 3 years | ✅ |
| 2026-09-15 03:05:02 | `text_input` | How many years of experience do you have in Asp.Net Core? | 3 years | ✅ |
| 2026-09-15 03:05:08 | `text_input` | How many years of experience do you have in React.Js? | 3 years | ✅ |
| 2026-09-15 03:05:17 | `text_input` | This role demans someone who are still hands on, When was was the last time you  | I actively code daily in my current Data Engineer  | ✅ |
| 2026-09-15 03:05:25 | `rejection` | save_unconfirmed | no_applied_state | ❌ |
| 2026-09-15 03:06:45 | `quick_reply_chip` | I confirm that I have reviewed all job-related information and hereby provide my | Consent | ✅ |
| 2026-09-15 03:06:57 | `rejection` | chatbot_no_save | discarded_no_confirmed_save | ❌ |
| 2026-09-15 03:11:42 | `text_input` | State your total team handling experience (in years) and the team size managed ( | 3 years | ✅ |
| 2026-09-15 03:11:48 | `text_input` | Are you currently residing in Bengaluru or willing to relocate to Bengaluru? | Yes | ✅ |
| 2026-09-15 03:11:51 | `rejection` | chatbot_no_save | discarded_no_confirmed_save | ❌ |
| 2026-09-15 03:13:07 | `quick_reply_chip` | I confirm that I have reviewed all job-related information and hereby provide my | Consent | ✅ |
| 2026-09-15 03:13:18 | `rejection` | chatbot_no_save | discarded_no_confirmed_save | ❌ |
| 2026-09-15 03:24:24 | `text_input` | How many years of experience do you have in Ms Sql Development? | 3 years | ✅ |
| 2026-09-15 03:24:33 | `text_input` | How many years of experience do you have in US Healthcare Domain? | 3 years | ✅ |
| 2026-09-15 03:25:00 | `rejection` | save_unconfirmed | no_applied_state | ❌ |
