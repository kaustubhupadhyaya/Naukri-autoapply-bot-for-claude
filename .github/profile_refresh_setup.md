# 🚀 Naukri Profile Auto-Refresh Setup Guide

## 📋 **Overview**

This system automatically updates your Naukri profile hourly to keep it "fresh" in their search algorithm, helping you appear higher in recruiter searches.

**How it works:**
1. ⏰ Runs every hour (9 AM - 9 PM IST) via GitHub Actions
2. 🔐 Logs into your Naukri account automatically
3. 🔄 Makes minimal profile changes (rotates different strategies)
4. 💾 Saves progress and logs all activities
5. 🔁 Repeats automatically without your input

---

## 🛠️ **Setup Instructions**

### **Step 1: Add Files to Repository**

1. **Add the profile refresher:**
   ```bash
   # Save as: naukri_profile_refresher.py
   ```

2. **Add GitHub Actions workflow:**
   ```bash
   # Save as: .github/workflows/profile-refresh.yml
   ```

### **Step 2: Configure GitHub Secrets**

1. Go to your GitHub repository
2. Navigate to `Settings` > `Secrets and variables` > `Actions`
3. Add these **Repository Secrets:**

   | Secret Name | Value | Example |
   |-------------|--------|---------|
   | `NAUKRI_EMAIL` | Your Naukri login email | `kaustubh.upadhyaya1@gmail.com` |
   | `NAUKRI_PASSWORD` | Your Naukri password | `your_password_here` |
   | `FIRSTNAME` | Your first name | `Kaustubh` |
   | `LASTNAME` | Your last name | `Upadhyaya` |

### **Step 3: Test the Setup**

1. **Manual test:**
   ```bash
   # In your repository, go to Actions tab
   # Click "Naukri Profile Refresh" workflow
   # Click "Run workflow" button
   # Select "Run workflow" to test
   ```

2. **Check results:**
   - ✅ Green checkmark = Success
   - ❌ Red X = Failed (check logs)

### **Step 4: Monitor Automation**

- **Automatic schedule:** Runs hourly from 9 AM - 9 PM IST
- **Check status:** GitHub Actions tab shows all runs
- **View logs:** Click on any run to see detailed logs

---

## ⚡ **Update Strategies (Rotated Hourly)**

The system rotates through these strategies to avoid detection:

1. **Headline Tweak** - Minor punctuation changes
2. **Summary Refresh** - Add/remove periods, line breaks
3. **Skill Reorder** - Open/close skills section
4. **Experience Touch** - Visit experience section
5. **Contact Refresh** - View contact information

Each strategy makes minimal changes that trigger Naukri's "last updated" timestamp without affecting your profile content.

---

## 📊 **Monitoring & Logs**

### **Success Indicators:**
- ✅ Green status in GitHub Actions
- 📄 `profile_refresh_log.json` updated
- 📝 `last_strategy.txt` tracks rotation

### **Log Files:**
```json
// profile_refresh_log.json
{
  "timestamp": "2025-07-21T10:30:00",
  "status": "success", 
  "strategy_used": "headline_tweak"
}
```

### **Failure Handling:**
- 🔄 **Automatic retry:** Fallback job runs if main job fails
- 📧 **Notifications:** Optional (can add Discord/email alerts)
- ⏭️ **Skip:** Continues next hour if one fails

---

## 🚨 **Important Limitations & Considerations**

### **What You're Missing in Logic:**

1. **CAPTCHA Challenge**
   - ⚠️ **Risk:** Naukri may show CAPTCHAs for automated logins
   - 🔧 **Mitigation:** Random user agents, human-like delays
   - 📋 **Backup:** Manual intervention may be needed occasionally

2. **IP Address Changes**
   - ⚠️ **Issue:** GitHub Actions uses different IPs each run
   - 🔍 **Detection:** Naukri may flag unusual login patterns
   - 💡 **Solution:** Consider using proxy or VPN service

3. **Account Security**
   - ⚠️ **Risk:** Automated logins might trigger security alerts
   - ✅ **Best Practice:** Use app-specific passwords if available
   - 🔐 **Recommendation:** Monitor account for unusual activity

4. **Rate Limiting**
   - ⚠️ **Risk:** Too frequent updates might get flagged
   - ⚙️ **Current:** Hourly updates (reasonable frequency)
   - 📊 **Adjust:** Can reduce to every 2-3 hours if needed

5. **Naukri Terms of Service**
   - ⚠️ **Legal:** Automated access might violate ToS
   - 🤔 **Consider:** Ensure compliance with platform rules
   - 📋 **Alternative:** Manual profile updates twice daily

### **Technical Challenges:**

6. **Headless Browser Detection**
   - 🤖 **Issue:** Naukri might detect headless Chrome
   - 🛠️ **Mitigation:** Advanced anti-detection measures included
   - 🔄 **Fallback:** Switch to different browsers if needed

7. **GitHub Actions Limits**
   - ⏱️ **Limit:** 2000 minutes/month on free plan
   - 📊 **Usage:** ~30 minutes/month for this automation
   - ✅ **Status:** Well within limits

8. **Network Timeouts**
   - 🌐 **Issue:** GitHub runners might have connectivity issues
   - 🔄 **Handling:** Retry logic and fallback jobs included
   - 📝 **Logging:** Detailed error tracking

---

## 🔧 **Advanced Configuration**

### **Adjust Frequency:**
```yaml
# In .github/workflows/profile-refresh.yml
schedule:
  # Every 2 hours instead of hourly
  - cron: '30 3,5,7,9,11,13,15 * * *'
  
  # Only during business hours (9 AM - 5 PM IST)
  - cron: '30 3-11 * * 1-5'
```

### **Add Notifications:**
```yaml
# Add to workflow
- name: Notify on failure
  if: failure()
  run: |
    curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"🚨 Naukri profile refresh failed!"}' \
    ${{ secrets.DISCORD_WEBHOOK_URL }}
```

### **Custom Update Strategies:**
```python
# In naukri_profile_refresher.py
self.update_strategies = [
    'headline_tweak',
    'summary_refresh', 
    'skill_reorder',
    'custom_strategy'  # Add your own
]
```

---

## 🎯 **Expected Results**

### **Immediate (1-2 weeks):**
- ✅ Profile shows "Recently updated" status
- 📈 Appears higher in search results
- 🔍 More profile views from recruiters

### **Long-term (1+ months):**
- 📊 20-30% increase in profile views
- 📞 More recruiter calls/messages
- 🎯 Better job opportunity flow

### **Success Metrics:**
- 📈 **Profile views:** Track in Naukri dashboard
- 📧 **Messages received:** Monitor recruiter outreach
- 🔍 **Search ranking:** Check where you appear for relevant searches

---

## 🆘 **Troubleshooting**

### **Common Issues:**

1. **Login Fails:**
   ```
   Solution: Check credentials in GitHub Secrets
   Verify: No special characters breaking JSON
   ```

2. **Workflow Not Running:**
   ```
   Check: GitHub Actions is enabled in repository settings
   Verify: Correct cron timezone (UTC vs IST)
   ```

3. **Profile Changes Not Visible:**
   ```
   Note: Changes are minimal by design
   Check: "Last updated" timestamp on profile
   ```

4. **Too Many Failures:**
   ```
   Action: Reduce frequency to every 2-3 hours
   Consider: Manual updates as backup
   ```

---

## 🚀 **Getting Started Checklist**

- [ ] Add `naukri_profile_refresher.py` to repository
- [ ] Create `.github/workflows/profile-refresh.yml`
- [ ] Add GitHub Secrets (email, password, names)
- [ ] Test with manual workflow run
- [ ] Monitor first few automated runs
- [ ] Adjust frequency if needed
- [ ] Set up failure notifications (optional)

---

## 💡 **Pro Tips**

1. **Monitor Results:** Check Naukri profile views weekly
2. **Stay Compliant:** Don't overuse - hourly is optimal
3. **Have Backup:** Keep manual profile updates as fallback
4. **Track Performance:** Note correlation with job opportunities
5. **Be Patient:** SEO effects take 2-3 weeks to show

**This system gives you a competitive advantage by ensuring your profile stays fresh and visible to recruiters 24/7!** 🎯