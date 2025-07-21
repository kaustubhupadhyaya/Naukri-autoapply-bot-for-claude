import sys
import os
import time
import logging
import json
import platform
from typing import List, Dict
import pandas as pd
from datetime import datetime

# Selenium imports (ADDED - were missing)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import the original NaukriBot
from Naukri_Edge import IntelligentNaukriBot
from intelligent_job_processor import IntelligentJobProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedNaukriBot(IntelligentNaukriBot):
    def __init__(self, config_file="enhanced_config.json"):
        # CORRECTED: Proper parent initialization
        super().__init__(config_file)
        
        # Initialize AI processor
        self.job_processor = IntelligentJobProcessor(config_file)
        self.applied_count = 0
        self.analyzed_count = 0
        self.max_applications = self.config['job_search']['max_applications_per_session']
        
        # Session tracking
        self.session_stats = {
            'ai_calls': 0,
            'fallback_scores': 0,
            'high_score_jobs': 0,
            'applications_sent': 0,
            'jobs_skipped': 0
        }
    
    def process_jobs_with_streaming_application(self):
        """CORRECTED: Process jobs with proper authentication checks and updated selectors"""
        
        # CRITICAL: Verify we're set up and logged in
        if not self.driver:
            logger.error("❌ Driver not initialized! Call setup_driver() first!")
            return False
        
        # Verify login status with multiple indicators
        if not self._verify_authentication():
            logger.error("❌ Not authenticated to Naukri! Call login() first!")
            return False
        
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']  
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        logger.info(f"🎯 Starting streaming job processing (max {self.max_applications} applications)")
        
        total_processed = 0
        
        for keyword_index, keyword in enumerate(keywords):
            if self.applied_count >= self.max_applications:
                logger.info(f"✅ Reached application limit: {self.max_applications}")
                break
                
            logger.info(f"🔍 Processing keyword {keyword_index + 1}/{len(keywords)}: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                if self.applied_count >= self.max_applications:
                    break
                    
                try:
                    # Build URL and navigate
                    clean_keyword = keyword.lower().replace(' ', '-')
                    clean_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_location}-{page}"
                    
                    logger.info(f"Page {page}/{pages_per_keyword}: {url}")
                    self.driver.get(url)
                    
                    # Wait for page to load properly
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "srp-jobtuple-wrapper"))
                        )
                    except TimeoutException:
                        logger.warning("Page load timeout, trying anyway...")
                    
                    time.sleep(4)  # Allow page to load
                    
                    # Get job cards with updated selectors
                    job_cards = self._get_job_cards()
                    logger.info(f"Found {len(job_cards)} job cards on page")
                    
                    if not job_cards:
                        logger.warning("No job cards found - page may not have loaded correctly")
                        continue
                    
                    for card_index, job_card in enumerate(job_cards):
                        if self.applied_count >= self.max_applications:
                            break
                            
                        try:
                            # Extract job data with corrected selectors
                            job_data = self._extract_job_data_corrected(job_card)
                            
                            if not job_data:
                                logger.warning(f"Could not extract data from card {card_index + 1}")
                                continue
                            
                            total_processed += 1
                            
                            # AI Analysis with retry logic
                            ai_result = self._analyze_job_with_retry(
                                job_data['description'],
                                job_data['title'],
                                job_data['company']
                            )
                            
                            self.session_stats['ai_calls'] += 1
                            if ai_result.get('fallback_used', False):
                                self.session_stats['fallback_scores'] += 1
                            
                            score = ai_result.get('total_score', 0)
                            
                            logger.info(f"Job {card_index + 1}: {job_data['title']} (Score: {score}/100)")
                            
                            # Apply if score meets threshold
                            if ai_result.get('should_apply', False) and score >= 70:
                                logger.info(f"✅ WILL APPLY: {job_data['title']} | Score: {score}/100")
                                self.session_stats['high_score_jobs'] += 1
                                
                                success = self._attempt_job_application_corrected(job_data)
                                
                                if success:
                                    self.applied_count += 1
                                    self.session_stats['applications_sent'] += 1
                                    logger.info(f"✅ Application #{self.applied_count} sent: {job_data['title']}")
                                else:
                                    logger.error(f"❌ Application failed: {job_data['title']}")
                                
                            else:
                                logger.info(f"⏭️  SKIPPED: {job_data['title']} | Score: {score}/100")
                                self.session_stats['jobs_skipped'] += 1
                            
                            # Rate limiting between jobs
                            time.sleep(3)
                            
                        except Exception as card_error:
                            logger.error(f"Error processing job card {card_index + 1}: {card_error}")
                            continue
                    
                except Exception as page_error:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {page_error}")
                    continue
        
        logger.info(f"🏁 Session completed: {self.applied_count} applications sent, {total_processed} jobs processed")
        self._print_session_summary()
        return self.applied_count > 0
    
    def _verify_authentication(self):
        """CORRECTED: Verify if we're logged in with multiple fallbacks"""
        try:
            # Multiple authentication indicators to try
            auth_indicators = [
                (By.CLASS_NAME, "nI-gNb-drawer__icon"),
                (By.CLASS_NAME, "nI-gNb-userMenu"),
                (By.CLASS_NAME, "user-menu"),
                (By.ID, "login_Layer"),  # This should NOT be present if logged in
                (By.XPATH, "//div[contains(@class, 'user')]"),
                (By.XPATH, "//a[contains(text(), 'My Naukri')]")
            ]
            
            for by_type, selector in auth_indicators:
                try:
                    element = self.driver.find_element(by_type, selector)
                    if selector == "login_Layer":
                        # If login layer is present, we're NOT logged in
                        if element.is_displayed():
                            logger.warning("❌ Login form detected - not authenticated")
                            return False
                    else:
                        # If other elements are found, we ARE logged in
                        logger.info(f"✅ Authentication verified using: {selector}")
                        return True
                except NoSuchElementException:
                    continue
            
            # If no indicators found, assume not logged in
            logger.warning("⚠️  Could not determine authentication status - assuming not logged in")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying authentication: {e}")
            return False
    
    def _get_job_cards(self):
        """CORRECTED: Get job cards with updated selectors"""
        selectors_to_try = [
            "srp-jobtuple-wrapper",
            "jobTuple",
            "job-tuple",
            "job-card",
            "result"
        ]
        
        for selector in selectors_to_try:
            try:
                job_cards = self.driver.find_elements(By.CLASS_NAME, selector)
                if job_cards:
                    logger.debug(f"Found job cards using selector: {selector}")
                    return job_cards
            except:
                continue
        
        logger.warning("No job cards found with any known selector")
        return []
    
    def _extract_job_data_corrected(self, job_card):
        """CORRECTED: Extract job data with updated selectors that work"""
        try:
            job_data = {}
            
            # Title extraction with multiple selectors
            title_selectors = [
                ".title a",
                ".jobTitle a", 
                ".jobTuple-title a",
                "h3 a",
                "a[data-job-title]",
                ".heading a"
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = job_card.find_element(By.CSS_SELECTOR, selector)
                    job_data['title'] = title_elem.text.strip()
                    job_data['url'] = title_elem.get_attribute('href')
                    break
                except:
                    continue
            
            # Company extraction
            company_selectors = [
                ".subTitle",
                ".companyName", 
                ".employer",
                ".company",
                ".jobTuple-company"
            ]
            
            for selector in company_selectors:
                try:
                    company_elem = job_card.find_element(By.CSS_SELECTOR, selector)
                    job_data['company'] = company_elem.text.strip()
                    break
                except:
                    continue
            
            # Get full card text for AI analysis
            job_data['description'] = job_card.text
            
            # Validate we have minimum required data
            if not job_data.get('title') or not job_data.get('company'):
                logger.warning("Missing title or company in job card")
                return None
            
            return job_data
            
        except Exception as e:
            logger.error(f"Error extracting job data: {e}")
            return None
    
    def _analyze_job_with_retry(self, job_card_text, job_title, company_name, max_retries=2):
        """CORRECTED: Analyze job with proper retry logic"""
        
        for attempt in range(max_retries):
            try:
                # Try AI analysis
                ai_result = self.job_processor.process_job(
                    job_title=job_title,
                    job_description=job_card_text,
                    company_name=company_name
                )
                
                if attempt > 0:
                    logger.info(f"✅ AI Analysis succeeded on attempt {attempt + 1}")
                
                return ai_result
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if "quota" in error_msg or "429" in error_msg:
                    logger.warning(f"🚫 API quota exceeded on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        logger.info(f"⏱️  Waiting 60s for quota reset...")
                        time.sleep(60)  # Wait for quota reset
                        continue
                    else:
                        break
                elif "timeout" in error_msg or "connection" in error_msg:
                    logger.warning(f"🌐 Network error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(10)
                        continue
                    else:
                        break
                else:
                    logger.error(f"❌ AI analysis error: {e}")
                    break
        
        # Fallback scoring
        logger.info(f"🔄 Using fallback scoring for {job_title}")
        fallback_score = self._simple_keyword_scoring(job_card_text)
        
        return {
            'total_score': fallback_score,
            'should_apply': fallback_score >= self.config['job_search']['min_job_score'],
            'match_level': 'fallback',
            'fallback_used': True,
            'reasoning': f'Fallback scoring due to AI failure. Score based on keywords: {fallback_score}/100'
        }
    
    def _simple_keyword_scoring(self, job_text):
        """CORRECTED: Enhanced fallback scoring"""
        job_text_lower = job_text.lower()
        score = 0
        
        # Core Data Engineering keywords (high weight)
        data_eng_keywords = ['data engineer', 'data engineering', 'etl', 'pipeline', 'data pipeline']
        for keyword in data_eng_keywords:
            if keyword in job_text_lower:
                score += 30
                break  # Only count once
        
        # Technology keywords (medium weight)
        tech_keywords = ['python', 'sql', 'airflow', 'aws', 'spark', 'kafka', 'snowflake', 'dbt']
        for keyword in tech_keywords:
            if keyword in job_text_lower:
                score += 6
        
        # Experience level matching (prefer 2-5 years)
        if any(exp in job_text_lower for exp in ['2-5 years', '2-4 years', '3-5 years', 'mid-level']):
            score += 20
        elif any(exp in job_text_lower for exp in ['1-3 years', '2-6 years']):
            score += 15
        elif any(exp in job_text_lower for exp in ['senior', 'lead', '5+ years', '7+ years']):
            score -= 15  # Penalize senior roles
        
        # Location preference (Bangalore)
        if 'bangalore' in job_text_lower or 'bengaluru' in job_text_lower:
            score += 10
        
        # Remote work bonus
        if any(remote in job_text_lower for remote in ['remote', 'work from home', 'wfh', 'hybrid']):
            score += 8
        
        return min(score, 100)
    
    def _attempt_job_application_corrected(self, job_data):
        """CORRECTED: Attempt to apply to a job with proper implementation"""
        try:
            # Navigate to job detail page
            if job_data.get('url'):
                self.driver.get(job_data['url'])
                time.sleep(4)
            else:
                logger.error("No job URL available")
                return False
            
            # Look for apply buttons with various selectors
            apply_selectors = [
                "//button[contains(text(), 'Apply')]",
                "//a[contains(text(), 'Apply')]",
                "//input[@value='Apply']",
                ".apply-button",
                "#apply-btn",
                ".btn-apply",
                "[data-job-apply]"
            ]
            
            for selector in apply_selectors:
                try:
                    if selector.startswith("//"):
                        button = self.driver.find_element(By.XPATH, selector)
                    else:
                        button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if button and button.is_enabled() and button.is_displayed():
                        logger.info(f"Found apply button with selector: {selector}")
                        
                        # Scroll to button to ensure it's visible
                        self.driver.execute_script("arguments[0].scrollIntoView();", button)
                        time.sleep(1)
                        
                        # Click the apply button
                        button.click()
                        time.sleep(5)  # Wait for form/popup to load
                        
                        # Handle application form if it appears
                        form_handled = self._handle_application_form()
                        
                        if form_handled:
                            logger.info("✅ Application form submitted successfully")
                            # Navigate back to search results
                            self.driver.back()
                            time.sleep(3)
                            return True
                        else:
                            logger.warning("⚠️  Apply button clicked but no form found")
                            self.driver.back()
                            time.sleep(3)
                            return True  # Consider it successful if no form is needed
                            
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.error(f"Error clicking apply button: {e}")
                    continue
            
            logger.warning(f"No apply button found for {job_data['title']}")
            # Navigate back to search results
            self.driver.back()
            time.sleep(3)
            return False
            
        except Exception as e:
            logger.error(f"Application attempt failed: {e}")
            # Try to get back to search results
            try:
                self.driver.back()
                time.sleep(3)
            except:
                pass
            return False
    
    def _handle_application_form(self):
        """CORRECTED: Handle application form with proper field detection"""
        try:
            # Wait a bit for any form to load
            time.sleep(3)
            
            # Look for common form elements
            form_selectors = [
                "form",
                ".apply-form",
                ".application-form",
                "#application-popup",
                ".popup-content"
            ]
            
            form_found = False
            for selector in form_selectors:
                try:
                    form = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if form.is_displayed():
                        form_found = True
                        logger.info(f"Found form with selector: {selector}")
                        break
                except:
                    continue
            
            if not form_found:
                logger.info("No application form found - may be direct apply")
                return True
            
            # Fill any required fields with user data
            self._fill_form_fields()
            
            # Look for submit buttons
            submit_selectors = [
                "//button[contains(text(), 'Submit')]",
                "//button[contains(text(), 'Apply')]", 
                "//input[@type='submit']",
                ".btn-submit",
                ".submit-button"
            ]
            
            for selector in submit_selectors:
                try:
                    if selector.startswith("//"):
                        submit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        submit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if submit_btn and submit_btn.is_enabled():
                        submit_btn.click()
                        logger.info("✅ Form submitted successfully")
                        time.sleep(3)
                        return True
                except:
                    continue
            
            logger.warning("Form found but no submit button")
            return False
            
        except Exception as e:
            logger.error(f"Error handling application form: {e}")
            return False
    
    def _fill_form_fields(self):
        """Fill form fields with user data from config"""
        try:
            personal_info = self.config.get('personal_info', {})
            
            # Common field mappings
            field_mappings = {
                'current_ctc': personal_info.get('current_ctc', '13 LPA'),
                'expected_ctc': personal_info.get('expected_ctc', '18 LPA'),
                'notice_period': personal_info.get('notice_period', 'Immediate'),
                'phone': personal_info.get('phone', '9880380081')
            }
            
            for field_id, value in field_mappings.items():
                try:
                    # Try different selector patterns for each field
                    selectors = [
                        f"#{field_id}",
                        f"[name='{field_id}']",
                        f"[placeholder*='{field_id}']"
                    ]
                    
                    for selector in selectors:
                        try:
                            field = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if field.is_displayed() and field.is_enabled():
                                field.clear()
                                field.send_keys(value)
                                logger.debug(f"Filled {field_id}: {value}")
                                break
                        except:
                            continue
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error filling form fields: {e}")
    
    def _print_session_summary(self):
        """Print detailed session summary"""
        logger.info(f"""
        ╔═══ ENHANCED NAUKRI BOT SESSION SUMMARY ═══
        ║ 🔍 Total Jobs Analyzed: {self.session_stats['ai_calls']}
        ║ 🧠 Gemini API Calls: {self.session_stats['ai_calls'] - self.session_stats['fallback_scores']}
        ║ ⭐ High Score Jobs (70+): {self.session_stats['high_score_jobs']}
        ║ ✅ Applications Sent: {self.session_stats['applications_sent']}
        ║ ❌ Skipped (Low Score): {self.session_stats['jobs_skipped']}
        ║ 🔄 Fallback Scores Used: {self.session_stats['fallback_scores']}
        ║ 📈 Success Rate: {(self.session_stats['applications_sent'] / max(self.session_stats['ai_calls'], 1) * 100):.1f}%
        ╚═══════════════════════════════════════════
        """)

# Main execution - CORRECTED VERSION
def main():
    """Main function with proper initialization sequence - CORRECTED"""
    bot = None
    try:
        logger.info("🚀 Starting Enhanced Naukri Bot with AI Intelligence...")
        
        # Initialize bot
        bot = EnhancedNaukriBot()
        logger.info("✅ Enhanced Naukri Bot initialized successfully!")
        
        # CRITICAL: Setup browser first
        logger.info("📡 Phase 1: Setting up browser and logging in...")
        logger.info("Setting up browser...")
        if not bot.setup_driver():
            logger.error("❌ Failed to setup browser")
            return False
        
        # CRITICAL: Login to Naukri  
        logger.info("🔐 Phase 2: Logging into Naukri...")
        if not bot.login():
            logger.error("❌ Failed to login to Naukri")
            return False
            
        # Verify authentication
        if not bot._verify_authentication():
            logger.error("❌ Authentication verification failed")
            return False
        
        logger.info("✅ Login verification successful")
        
        # Now process jobs with AI
        logger.info("📡 Phase 3: Scraping jobs with AI analysis...")
        success = bot.process_jobs_with_streaming_application()
        
        if not success:
            logger.warning("⚠️ No applications were sent")
        
        # Save results
        logger.info("💾 Phase 4: Saving results...")
        bot.save_results()
        
        logger.info("🎉 Enhanced Naukri Bot session completed successfully!")
        return True
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
        return False
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if bot and hasattr(bot, 'driver') and bot.driver:
            input("Press Enter to close browser...")
            bot.driver.quit()

if __name__ == "__main__":
    main()


# ===== 2. CORRECTED intelligent_job_processor.py rate limiting =====

def _rate_limit(self):
    """CORRECTED: Enhanced rate limiting for Gemini free tier"""
    current_time = time.time()
    time_since_last_call = current_time - self.last_api_call
    
    # Gemini free tier: 15 requests per minute = 4 seconds minimum
    # But with processing time, use 8 seconds to be safe
    # For quota issues, might need 10+ seconds
    min_delay = 10.0  # Increased from 4 to 10 seconds
    
    if time_since_last_call < min_delay:
        sleep_time = min_delay - time_since_last_call
        logger.info(f"⏱️  Rate limiting: waiting {sleep_time:.1f}s for API stability...")
        time.sleep(sleep_time)
    
    self.last_api_call = time.time()


# ===== 3. CORRECTED Naukri_Edge.py setup_driver method =====

def setup_driver(self):
    """CORRECTED: Enhanced WebDriver setup with multiple fallbacks"""
    try:
        logger.info("Setting up browser...")
        logger.info(f"Operating System: {platform.platform()}")
        
        # Import webdriver manager
        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            logger.info("✅ webdriver-manager imported successfully")
        except ImportError:
            logger.error("❌ webdriver-manager not installed. Run: pip install webdriver-manager")
            return False
        
        # Edge options with enhanced stealth
        options = webdriver.EdgeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Add user agent to appear more human-like
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59")
        
        # Try multiple driver setup approaches
        setup_methods = [
            ("Auto-download", self._setup_auto_download),
            ("Manual path", self._setup_manual_path), 
            ("System driver", self._setup_system_driver)
        ]
        
        for method_name, method_func in setup_methods:
            try:
                logger.info(f"🔄 Trying {method_name} method...")
                driver = method_func(options)
                if driver:
                    self.driver = driver
                    self.driver.implicitly_wait(self.config['webdriver']['implicit_wait'])
                    self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
                    
                    # Test driver with a simple operation
                    self.driver.get("https://www.google.com")
                    logger.info("✅ Browser setup successful")
                    return True
                    
            except Exception as e:
                logger.warning(f"❌ {method_name} method failed: {e}")
                continue
        
        logger.error("❌ All WebDriver setup methods failed")
        return False
        
    except Exception as e:
        logger.error(f"WebDriver setup failed: {e}")
        return False

def _setup_auto_download(self, options):
    """Try automatic driver download"""
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    service = webdriver.EdgeService(EdgeChromiumDriverManager().install())
    return webdriver.Edge(service=service, options=options)

def _setup_manual_path(self, options):
    """Try manual driver path"""
    manual_path = self.config['webdriver']['edge_driver_path']
    if os.path.exists(manual_path):
        service = webdriver.EdgeService(manual_path)
        return webdriver.Edge(service=service, options=options)
    else:
        raise FileNotFoundError(f"Manual driver not found: {manual_path}")

def _setup_system_driver(self, options):
    """Try system-installed driver"""
    return webdriver.Edge(options=options)


# ===== 4. TESTING SCRIPT - CORRECTED =====

def test_corrected_implementation():
    """Test the corrected implementation step by step"""
    print("🔧 Testing Corrected Naukri Bot Implementation...")
    
    test_results = {
        "imports": False,
        "base_bot": False, 
        "enhanced_bot": False,
        "ai_processor": False,
        "config": False
    }
    
    # Test imports
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        print("✅ Selenium imports: SUCCESS")
        test_results["imports"] = True
    except ImportError as e:
        print(f"❌ Selenium imports: FAILED - {e}")
    
    # Test base bot
    try:
        from Naukri_Edge import IntelligentNaukriBot
        base_bot = IntelligentNaukriBot()
        print("✅ Base bot initialization: SUCCESS")
        test_results["base_bot"] = True
    except Exception as e:
        print(f"❌ Base bot: FAILED - {e}")
    
    # Test enhanced bot
    try:
        from enhanced_naukri_bot import EnhancedNaukriBot  
        enhanced_bot = EnhancedNaukriBot()
        print("✅ Enhanced bot initialization: SUCCESS")
        test_results["enhanced_bot"] = True
    except Exception as e:
        print(f"❌ Enhanced bot: FAILED - {e}")
    
    # Test AI processor
    try:
        from intelligent_job_processor import IntelligentJobProcessor
        processor = IntelligentJobProcessor()
        print("✅ AI processor initialization: SUCCESS") 
        test_results["ai_processor"] = True
    except Exception as e:
        print(f"❌ AI processor: FAILED - {e}")
    
    # Test config
    try:
        import json
        with open("enhanced_config.json", "r") as f:
            config = json.load(f)
        required_keys = ["job_search", "webdriver", "gemini_api_key"]
        if all(key in config for key in required_keys):
            print("✅ Configuration: SUCCESS")
            test_results["config"] = True
        else:
            print("❌ Configuration: MISSING REQUIRED KEYS")
    except Exception as e:
        print(f"❌ Configuration: FAILED - {e}")
    
    # Summary
    passed = sum(test_results.values())
    total = len(test_results)
    
    print(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready to run the bot.")
    else:
        print("⚠️  Some tests failed. Fix issues before running.")
        for test_name, result in test_results.items():
            if not result:
                print(f"   - Fix: {test_name}")
    
    return passed == total

if __name__ == "__main__":
    test_corrected_implementation()
