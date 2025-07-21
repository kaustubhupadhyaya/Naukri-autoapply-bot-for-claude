# 🚀 Naukri Auto-Apply Bot - Complete Setup Guide

## 📋 **Quick Start (3 Steps)**

### **Step 1: Install Dependencies**
```bash
# Install Python packages
pip install -r requirements.txt
```

### **Step 2: Download Edge WebDriver**
```bash
# Create WebDrivers directory
mkdir C:\WebDrivers

# Download EdgeDriver from Microsoft and place at:
# C:\WebDrivers\msedgedriver.exe
```

### **Step 3: Run the Bot**
```bash
# Test base bot first
python Naukri_Edge.py

# Or run AI-enhanced bot
python enhanced_naukri_bot.py
```

---

## 📁 **File Structure**

```
naukri-bot/
├── Naukri_Edge.py              # Base bot (FIXED LOGIN)
├── enhanced_naukri_bot.py      # AI-enhanced bot 
├── intelligent_job_processor.py # AI processor
├── config.json                 # Base bot config
├── enhanced_config.json        # Enhanced bot config
├── requirements.txt            # Dependencies
├── test_complete_system.py     # System test
└── logs/
    ├── naukri_bot.log         # Detailed logs
    └── session_*.json         # Session reports
```

---

## ⚙️ **Detailed Setup Instructions**

### **1. Environment Setup**

```bash
# Check Python version (requires 3.8+)
python --version

# Create virtual environment (recommended)
python -m venv naukri_env
naukri_env\Scripts\activate  # Windows
# source naukri_env/bin/activate  # macOS/Linux

# Install requirements
pip install -r requirements.txt
```

### **2. WebDriver Setup**

**Option A: Automatic (Recommended)**
- The bot will auto-download EdgeDriver when first run
- Requires internet connection

**Option B: Manual**
```bash
# 1. Create directory
mkdir C:\WebDrivers

# 2. Download from Microsoft:
# https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/

# 3. Extract msedgedriver.exe to C:\WebDrivers\msedgedriver.exe
```

### **3. Configuration**

**For Base Bot (Naukri_Edge.py):**
- Edit `config.json` with your credentials
- Set job search keywords and location

**For Enhanced Bot (enhanced_naukri_bot.py):**  
- Edit `enhanced_config.json`
- Add your Gemini API key (free from Google AI Studio)
- Configure AI analysis settings

### **4. API Setup (Enhanced Bot Only)**

```bash
# 1. Get free Gemini API key from:
# https://aistudio.google.com/app/apikey

# 2. Add to enhanced_config.json:
"gemini_api_key": "YOUR_API_KEY_HERE"
```

---

## 🧪 **Testing & Validation**

### **System Test**
```bash
# Run comprehensive system test
python test_complete_system.py

# Should output:
# ✅ SYSTEM READY - All tests passed!
```

### **Base Bot Test**
```bash
# Test login and basic functionality
python Naukri_Edge.py

# Expected: Browser opens, logs in, finds jobs
```

### **Enhanced Bot Test**
```bash
# Test AI-powered job analysis
python enhanced_naukri_bot.py

# Expected: AI analysis + smart applications
```

---

## 🔧 **Common Issues & Solutions**

### **Login Issues**
```
❌ Problem: Login fails or hangs
✅ Solution: 
- Verify credentials in config files
- Check Naukri isn't blocking automated logins
- Try clearing browser cache
- Use VPN if IP is blocked
```

### **WebDriver Issues**
```  
❌ Problem: "Could not reach host" or driver errors
✅ Solution:
- Download EdgeDriver manually to C:\WebDrivers\
- Update Edge browser to latest version
- Check Windows PATH includes Edge installation
```

### **AI API Issues**
```
❌ Problem: "429 quota exceeded" or API errors  
✅ Solution:
- Verify Gemini API key is valid
- Check API quotas in Google Cloud Console
- Reduce applications per session (max 10-15)
- Increase rate limiting delay
```

### **No Jobs Found**
```
❌ Problem: Bot finds 0 jobs
✅ Solution:
- Update job search keywords in config
- Increase pages_per_keyword (try 3-5)  
- Check location spelling ("bengaluru" not "bangalore")
- Verify Naukri search URL format
```

---

## 🎯 **Usage Modes**

### **Mode 1: Base Bot (Simple)**
```bash
python Naukri_Edge.py

# Features:
- ✅ Login automation
- ✅ Job scraping  
- ✅ Basic keyword filtering
- ✅ Auto-apply to jobs
- ✅ Session reporting
```

### **Mode 2: Enhanced Bot (AI-Powered)**
```bash
python enhanced_naukri_bot.py

# Features:  
- ✅ All base bot features
- ✅ AI job analysis (Gemini)
- ✅ Smart job scoring (0-100)
- ✅ Experience level matching
- ✅ Company quality assessment
- ✅ Intelligent application targeting
```

---

## 📊 **Configuration Reference**

### **Key Settings**
```json
{
  "job_search": {
    "max_applications_per_session": 15,  // Reduce for testing
    "min_job_score": 60,                 // AI score threshold
    "pages_per_keyword": 2               // Pages to scrape
  },
  "bot_behavior": {
    "min_delay": 3,                      // Delay between actions
    "max_delay": 7,                      // Random delay range
    "typing_delay": 0.15                 // Human-like typing
  },
  "gemini_settings": {
    "rate_limit_delay": 15               // Seconds between API calls
  }
}
```

### **Recommended Settings for Different Goals**

**Testing/Development:**
```json
{
  "max_applications_per_session": 5,
  "pages_per_keyword": 1,
  "rate_limit_delay": 20
}
```

**Production/Daily Use:**
```json  
{
  "max_applications_per_session": 20,
  "pages_per_keyword": 3,
  "rate_limit_delay": 15
}
```

---

## 📈 **Success Metrics**

### **Base Bot Success:**
- ✅ Logs in successfully
- ✅ Finds 10+ relevant jobs
- ✅ Applies to 80%+ of found jobs
- ✅ Zero crashes during session

### **Enhanced Bot Success:**
- ✅ AI analysis success rate >80%
- ✅ Average job scores >65/100  
- ✅ Application relevance >90%
- ✅ Interview callback rate increases

---

## 🚨 **Safety & Ethics**

### **Rate Limiting**
- Built-in delays prevent IP blocking
- Respects Naukri's terms of service
- Smart retry logic for failures

### **Privacy**
- Credentials stored locally only
- No data sent to external services (except Gemini API)
- Job data cached temporarily for efficiency

### **Responsible Usage**
- Only applies to relevant positions
- Respects daily application limits  
- Maintains human-like behavior patterns
- Includes fallback mechanisms

---

## 🆘 **Troubleshooting**

### **Getting Help**
1. **Check Logs:** `naukri_bot.log` contains detailed error info
2. **Run Tests:** `python test_complete_system.py` diagnoses issues
3. **Start Simple:** Test base bot before enhanced features
4. **Monitor Console:** Watch real-time output for errors

### **Emergency Reset**
```bash
# Clear all cached data and start fresh
rm naukri_jobs.db
rm *.log  
rm session_*.json

# Restart with clean slate
python test_complete_system.py
```

---

## 🎉 **Ready to Go!**

Your complete Naukri automation system is now set up with:

- ✅ **Fixed login issues** - Updated selectors and retry logic
- ✅ **Complete files** - No snippets, everything included  
- ✅ **AI integration** - Smart job matching and scoring
- ✅ **Error handling** - Robust failure recovery
- ✅ **Testing framework** - Verify everything works
- ✅ **Detailed logging** - Monitor all activities

**Next Steps:**
1. Run `python test_complete_system.py` to verify setup
2. Start with `python Naukri_Edge.py` for basic functionality  
3. Graduate to `python enhanced_naukri_bot.py` for AI features
4. Monitor logs and adjust settings as needed

**Good luck with your job search! 🚀**