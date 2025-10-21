# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Setup and Testing
```powershell
# Install dependencies (use same Python version as runtime)
pip install -r requirements.txt

# Run system verification test (non-destructive, always run first)
python test_complete_system.py

# Run base bot (legacy)
python Naukri_Edge.py

# Run enhanced AI-powered bot
python enhanced_naukri_bot.py

# Run modular bot (new architecture)
python main.py
```

### WebDriver Setup
```powershell
# Download EdgeDriver manually if webdriver-manager fails
# Place msedgedriver.exe in C:\WebDrivers\
# Or let webdriver-manager auto-download (requires internet)
```

### Safe Testing Commands
```powershell
# Test with minimal risk (set in config.json/enhanced_config.json):
# - "max_applications_per_session": 1
# - "pages_per_keyword": 1  
# - "headless": true
```

## Architecture Overview

This is a Naukri.com job application automation bot with three architectural layers:

### Core Components
- **Base Bot** (`Naukri_Edge.py`): Selenium-based automation with adaptive selector caching
- **Enhanced Bot** (`enhanced_naukri_bot.py`): Adds Google Gemini AI job scoring/analysis
- **Modular Bot** (`naukri_bot/`): Clean modular architecture separating concerns

### Data Flow
```
Config → Bot → Selenium → Naukri.com → Scrape → 
AI Analysis (optional) → Apply/Skip → SQLite DB + Session JSONs + Logs
```

### Key Files
- **Configuration**: `config.json` / `enhanced_config.json`
- **Database**: `naukri_jobs.db` (auto-created SQLite)
- **Logging**: `naukri_bot.log` (rotating, 10MB max)
- **Session Reports**: `naukri_session_YYYYMMDD_HHMMSS.json` / `enhanced_naukri_session_*.json`

## Modular Architecture (`naukri_bot/`)

```
naukri_bot/
├── core/                  # Core orchestration
│   ├── naukri_bot.py     # Main bot controller
│   └── webdriver_manager.py # Browser management
├── modules/              # Feature modules
│   ├── auth.py          # Login handling
│   ├── job_search.py    # Job discovery
│   └── application.py   # Application submission
├── chatbot/             # AI chatbot handling
│   ├── chatbot_handler.py
│   ├── question_detector.py
│   ├── answer_provider.py
│   └── qa_dictionary.py
└── utils/               # Shared utilities
    ├── config_manager.py
    ├── database.py
    └── session_manager.py
```

## AI Integration

### Google Gemini Integration
- **Processor**: `intelligent_job_processor.py`
- **Model**: `gemini-1.5-flash`
- **Rate Limiting**: 15-second delays (free tier: 15 RPM)
- **Fallback Scoring**: Local scoring when API fails
- **Configuration**: `gemini_api_key` and `gemini_settings` in `enhanced_config.json`

### Job Scoring Logic
- **Score Range**: 0-100 based on skill match, role relevance, company fit
- **Application Threshold**: 70+ score jobs get applied to
- **Cache**: Avoids re-processing identical jobs

## Configuration Patterns

### Defensive Selector Strategy
The bots use fallback selector lists for critical UI elements:
```python
email_selectors = ['#usernameField', "input[placeholder*='Email']", ...]
for sel in email_selectors: 
    try: find_element(sel) 
    except: continue
```

### Human-like Interaction
- **Delays**: `smart_delay()` with randomization
- **Typing**: `human_type()` with character-by-character delays
- **Behavior**: `bot_behavior` config controls timing patterns

### Driver Setup Fallback Order
1. `webdriver-manager` auto-download
2. Manual path from `webdriver.edge_driver_path` 
3. System driver

## Development Patterns

### Adding New Selectors
Add to appropriate fallback lists in both `Naukri_Edge.py` and `enhanced_naukri_bot.py`:
```python
job_card_selectors = [
    '.jobTuple',
    '[data-job-id]',
    '.job-card'  # Add new selector here
]
```

### Testing with Minimal Risk
Always set these config values for testing:
- `max_applications_per_session: 1`
- `pages_per_keyword: 1`
- `headless: true`

### Session Recovery
All bots implement adaptive selector caching and session recovery for handling Naukri.com UI changes.

## Integration Points

### External Dependencies
- **Selenium**: WebDriver automation (Edge browser required)
- **Google Generative AI**: Job analysis (requires API key)
- **webdriver-manager**: Auto-downloads EdgeDriver if network available

### Database Schema
- **SQLite**: `applied_jobs` table tracks application history
- **Session Files**: JSON format with application details and statistics

## Configuration Security

**Current State**: Credentials and API keys stored in config JSON files (in working tree)
**Recommendation**: Use environment variables or `.env` files for secrets, create `config.example.json` template

## Troubleshooting Entry Points

### For Bot Logic Changes
1. `Naukri_Edge.py` - Core behavior, login, scraping, application flow
2. `enhanced_naukri_bot.py` - AI integration orchestration
3. `intelligent_job_processor.py` - Gemini prompts and rate limiting

### For Architecture Changes  
1. `naukri_bot/core/naukri_bot.py` - Main orchestration
2. `test_complete_system.py` - Update tests to reflect changes

### For Chatbot/QA Features
1. `naukri_bot/chatbot/` - Question detection and answer automation
2. `tools/` - Analysis and debugging utilities

Always run `test_complete_system.py` after structural changes to validate system integrity.