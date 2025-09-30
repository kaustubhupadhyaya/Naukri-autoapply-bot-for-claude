## Copilot / AI Agent Instructions for this repository

Purpose
- Help an automated coding agent become productive quickly: explain the big-picture architecture, developer workflows, where secrets/config live, and project-specific patterns the codebase uses.

Quick start snippets (safe, repeatable)
- Install deps: `pip install -r requirements.txt` (use the same Python you will run the scripts with)
- Run the system test (non-destructive): `python test_complete_system.py`
- WebDriver: create `C:\WebDrivers` and place `msedgedriver.exe` there or let `webdriver-manager` auto-download (requires internet/proxy)

High-level architecture (what reads/writes what)
- Naukri_Edge.py — base bot. Responsibilities: load `config.json` (or `enhanced_config.json`), setup Selenium Edge, login, scrape job cards, apply to jobs, handle chatbots, save session reports and record applications in `naukri_jobs.db`.
- enhanced_naukri_bot.py — extends the base bot. Responsibilities: orchestrates AI analysis + application flow, produces `enhanced_naukri_session_*.json` session reports and richer stats.
- intelligent_job_processor.py — encapsulates AI scoring/analysis using Google Generative AI (`google.generativeai`). It reads `enhanced_config.json` for the `gemini_api_key` and `gemini_settings` (model, rate_limit_delay).
- test_complete_system.py — lightweight integration test: verifies imports, config structure, and basic initialization for the above components. Run this first.

Primary data flows
- Config (config.json / enhanced_config.json) -> Bot -> Selenium -> Naukri web pages -> scrape -> IntelligentJobProcessor (optional Gemini calls) -> Decision -> Apply / Skip -> Persistence (sqlite `naukri_jobs.db` + session jsons + `naukri_bot.log`).

Files and conventions worth noting (concrete examples)
- `config.json` / `enhanced_config.json` contains keys used in code:
  - `webdriver.edge_driver_path` (default: `C:\WebDrivers\msedgedriver.exe`)
  - `webdriver.headless` (true/false)
  - `job_search.pages_per_keyword`, `job_search.max_applications_per_session`
  - `bot_behavior.typing_delay`, `min_delay`/`max_delay`
  - `gemini_api_key` and `gemini_settings` used by `intelligent_job_processor.py`.
- Session files naming: `naukri_session_YYYYMMDD_HHMMSS.json` and `enhanced_naukri_session_*.json` are created at runtime.
- Database: `naukri_jobs.db` is created automatically (sqlite) and holds `applied_jobs`.
- Logging: `naukri_bot.log` is configured via logging.FileHandler in `Naukri_Edge.py`.

Project-specific coding patterns to follow
- Defensive selector lists: the bots try multiple CSS/XPath selectors for critical UI elements. When adding or modifying selectors, mirror the same pattern (list of fallbacks). Example in `Naukri_Edge.py` login:
  ```py
  email_selectors = ['#usernameField', "input[placeholder*='Email']", ...]
  for sel in email_selectors: try: find_element(sel) except: continue
  ```
- Human-like interaction helpers: use `smart_delay()` and `human_type()` helpers defined in `Naukri_Edge.py` when simulating typing or pauses.
- Driver setup fallbacks: the code attempts three methods in order: `webdriver-manager` auto-download, manual path from config, then system driver. Keep this order if modifying driver setup.

Developer workflows and commands (project-specific)
- Install and verify packages using the exact Python used to run bots to avoid ModuleNotFoundError: e.g.
  ```powershell
  C:/Users/Admin/AppData/Local/Microsoft/WindowsApps/python3.11.exe -m pip install -r requirements.txt
  C:/Users/Admin/AppData/Local/Microsoft/WindowsApps/python3.11.exe -m pip check
  ```
- Test (safe): `python test_complete_system.py`. This checks imports, config structure and basic class initialization.
- Quick bot smoke-run (safe): set `job_search.max_applications_per_session` to `1`, `webdriver.headless` to `true` in `config.json`/`enhanced_config.json`, then run `python Naukri_Edge.py`.
- WebDriver troubleshooting: If `webdriver-manager` can't download, download the exact EdgeDriver matching your Edge version and drop `msedgedriver.exe` into `C:\WebDrivers`.

Integration points and external dependencies
- Google Gemini (via `google.generativeai`) — used by `intelligent_job_processor.py`; requires valid `gemini_api_key` in `enhanced_config.json` and network access. The processor enforces a rate-limit (`min_delay_between_calls`) to reduce quota exhaustion.
- Selenium / webdriver-manager — may auto-download drivers; if network is restricted, supply a local `msedgedriver.exe`.

Security and secrets handling (what the code currently does)
- The repo currently stores credentials and the Gemini API key in `config.json`/`enhanced_config.json` (present in the working tree). Code reads API keys and credentials directly from these JSON files. Agents should NOT commit secrets. Prefer adding a `config.example.json` and use environment variables or `.env` for secrets.

Where agents should look first when making changes
- `Naukri_Edge.py` — core behavior: login, scraping, applying, session save, DB usage.
- `enhanced_naukri_bot.py` — orchestrates AI-driven behavior; changes here must align with `IntelligentJobProcessor` interface.
- `intelligent_job_processor.py` — Gemini prompts, rate limiting and parsing; changing prompt structure or model name goes here.
- `test_complete_system.py` — update to reflect any structural changes so CI/devs can quickly validate.

Small concrete examples an agent can apply immediately
- When adding a new selector, add it to the appropriate fallback list (e.g. `job_card_selector` lists in both bot files).
- To reduce risk while testing: set `job_search.max_applications_per_session` to `1` and `job_search.pages_per_keyword` to `1`.

If anything above is unclear or you want additional examples (for instance, exact Gemini prompt parsing, test fixtures, or a safe CI job), tell me which area to expand and I will iterate.
