"""
Naukri Profile Refresher - COMPLETE FIXED VERSION
- Text-based element finding for reliability
- Improved save button detection
- Better error handling and reporting
- Chrome WebDriver compatible with GitHub Actions
- Skills update as fallback strategy for reliability

SCHEDULE (GitHub Actions):
- Runs every hour at :00 (e.g., 7:00, 8:00, 9:00...)
- Active from 7:00 AM to 10:00 PM IST
- Total: 16 automatic updates daily
- Discord notifications on completion (requires DISCORD_WEBHOOK_URL secret)
"""

import os
import time
import json
import random
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NaukriProfileRefresher:
    """Complete fixed version with robust save functionality"""
    
    def __init__(self, config_file="config.json"):
        """Initialize with flexible config reading"""
        self.config = self._load_config(config_file)
        self.driver = None
        self.wait = None
        
        # Simplified to most reliable strategies
        self.update_strategies = [
            'headline_toggle',
            'summary_fullstop_toggle',
            'skills_update'
        ]
        
        # State tracking files
        self.state_files = {
            'headline_toggle': 'headline_toggle_state.txt',
            'summary_fullstop': 'summary_fullstop_state.txt'
        }
        
        self.last_strategy_file = "last_strategy.txt"
        
    def _load_config(self, config_file):
        """Load configuration from ANY config.json structure"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Handle MULTIPLE config structures
            credentials = None
            
            # Structure 1: "credentials" (most common)
            if 'credentials' in config:
                credentials = {
                    'email': config['credentials']['email'],
                    'password': config['credentials']['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (credentials structure)")
            
            # Structure 2: "login"
            elif 'login' in config:
                credentials = {
                    'email': config['login']['email'],
                    'password': config['login']['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (login structure)")
            
            # Structure 3: Direct email/password
            elif 'email' in config and 'password' in config:
                credentials = {
                    'email': config['email'],
                    'password': config['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (direct structure)")
            
            else:
                raise ValueError("Could not find credentials in config file")
            
            # Store full config + ensure credentials are accessible
            config['credentials'] = credentials
            return config
            
        except FileNotFoundError:
            logger.error(f"❌ Config file '{config_file}' not found!")
            raise
        except Exception as e:
            logger.error(f"❌ Config loading failed: {e}")
            raise
    
    def setup_driver(self, debug_mode=False):
        """Setup Chrome WebDriver with improved settings"""
        try:
            logger.info("🔧 Setting up Chrome WebDriver...")
            
            options = webdriver.ChromeOptions()
            
            # Headless mode for automation (disabled in debug mode)
            if not debug_mode:
                options.add_argument('--headless')
                logger.info("Running in headless mode")
            else:
                logger.info("Running in visible mode (debug)")
            
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            
            # Anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User agent
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Window size
            options.add_argument('--window-size=1920,1080')
            
            # Try automatic Chrome driver setup
            try:
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("✅ Chrome driver auto-download successful")
            except Exception as e:
                logger.warning(f"Auto-download failed: {e}")
                # Try manual paths
                manual_paths = [
                    "/usr/bin/chromedriver",
                    "/usr/local/bin/chromedriver",
                    r"C:\WebDrivers\chromedriver.exe",
                    r"C:\chromedriver\chromedriver.exe",
                    "chromedriver"
                ]
                
                driver_found = False
                for path in manual_paths:
                    if os.path.exists(path):
                        logger.info(f"🔄 Using manual path: {path}")
                        service = ChromeService(path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                        driver_found = True
                        break
                
                if not driver_found:
                    logger.error("❌ No Chrome driver found!")
                    return False
            
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 20)
            
            logger.info("✅ Chrome driver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Chrome driver setup failed: {e}")
            return False
    
    def login_to_naukri(self):
        """Login to Naukri using config credentials"""
        try:
            logger.info("🔐 Logging into Naukri...")
            
            # Navigate to Naukri login
            self.driver.get('https://www.naukri.com/nlogin/login')
            time.sleep(3)
            
            # Handle cookie consent if present
            try:
                cookie_buttons = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Got it')]",
                    "//button[contains(@class, 'cookies-accept')]"
                ]
                for xpath in cookie_buttons:
                    try:
                        button = self.driver.find_element(By.XPATH, xpath)
                        button.click()
                        time.sleep(1)
                        break
                    except:
                        continue
            except:
                pass
            
            # Fill email - try multiple selectors
            email_field = None
            email_selectors = [
                "usernameField",
                "emailField",
                "email"
            ]
            
            for selector_id in email_selectors:
                try:
                    email_field = self.wait.until(
                        EC.presence_of_element_located((By.ID, selector_id))
                    )
                    break
                except:
                    continue
            
            if not email_field:
                # Try by placeholder
                try:
                    email_field = self.driver.find_element(
                        By.XPATH, "//input[contains(@placeholder, 'Email') or contains(@placeholder, 'email')]"
                    )
                except:
                    logger.error("❌ Could not find email field")
                    return False
            
            email_field.clear()
            email_field.send_keys(self.config['credentials']['email'])
            time.sleep(1)
            
            # Fill password - try multiple selectors
            password_field = None
            password_selectors = [
                "passwordField",
                "password"
            ]
            
            for selector_id in password_selectors:
                try:
                    password_field = self.driver.find_element(By.ID, selector_id)
                    break
                except:
                    continue
            
            if not password_field:
                # Try by type
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                except:
                    logger.error("❌ Could not find password field")
                    return False
            
            password_field.clear()
            password_field.send_keys(self.config['credentials']['password'])
            time.sleep(1)
            
            # Click login button
            login_button = None
            login_selectors = [
                "//button[contains(text(), 'Login')]",
                "//button[@type='submit']",
                "//button[contains(@class, 'loginButton')]"
            ]
            
            for xpath in login_selectors:
                try:
                    login_button = self.driver.find_element(By.XPATH, xpath)
                    login_button.click()
                    break
                except:
                    continue
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login successful
            if "naukri.com/mnjuser" in self.driver.current_url or "homepage" in self.driver.current_url:
                logger.info("✅ Login successful!")
                return True
            else:
                logger.warning("⚠️ Login may have issues - continuing anyway")
                return True
                
        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            return False
    
    def _find_and_click_edit(self, section_text):
        """
        Find section by text, then click its edit button
        This is more reliable than CSS selectors
        """
        try:
            logger.info(f"🔍 Looking for '{section_text}' section...")
            
            # Strategy 1: Find heading text, then find edit icon in same container
            try:
                # Find the section by its heading text
                section_xpath = f"//div[contains(., '{section_text}')]"
                section_element = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, section_xpath))
                )
                
                # Scroll to the section
                self.driver.execute_script("arguments[0].scrollIntoView(true);", section_element)
                time.sleep(1)
                
                # Find edit button/icon within or near this section
                edit_selectors = [
                    f"//div[contains(., '{section_text}')]//span[contains(@class, 'edit')]",
                    f"//div[contains(., '{section_text}')]//button[contains(@class, 'edit')]",
                    f"//div[contains(., '{section_text}')]//a[contains(@class, 'edit')]",
                    f"//div[contains(., '{section_text}')]//*[@title='Edit' or @aria-label='Edit']",
                    f"//div[contains(., '{section_text}')]//i[contains(@class, 'edit')]",
                    f"//span[text()='{section_text}']/following-sibling::*[contains(@class, 'edit')]",
                    f"//span[contains(text(), '{section_text}')]/parent::*//*[contains(@class, 'edit')]"
                ]
                
                for selector in edit_selectors:
                    try:
                        edit_button = self.driver.find_element(By.XPATH, selector)
                        if edit_button.is_displayed():
                            # Try regular click first
                            try:
                                edit_button.click()
                                logger.info(f"✅ Clicked edit for '{section_text}'")
                                time.sleep(2)
                                return True
                            except:
                                # If regular click fails, try JavaScript click
                                self.driver.execute_script("arguments[0].click();", edit_button)
                                logger.info(f"✅ JS clicked edit for '{section_text}'")
                                time.sleep(2)
                                return True
                    except:
                        continue
                
            except TimeoutException:
                logger.warning(f"Could not find section with text '{section_text}'")
            
            # Strategy 2: Try finding by class names that might contain the section
            section_class_mappings = {
                "Resume headline": ["resumeHeadline", "resume-headline", "headline"],
                "Profile summary": ["summary", "profileSummary", "profile-summary"],
                "Key skills": ["keySkills", "key-skills", "skills"]
            }
            
            if section_text in section_class_mappings:
                for class_name in section_class_mappings[section_text]:
                    try:
                        edit_xpath = f"//*[contains(@class, '{class_name}')]//*[contains(@class, 'edit') or @title='Edit']"
                        edit_button = self.driver.find_element(By.XPATH, edit_xpath)
                        if edit_button.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", edit_button)
                            time.sleep(1)
                            self.driver.execute_script("arguments[0].click();", edit_button)
                            logger.info(f"✅ Found and clicked edit via class '{class_name}'")
                            time.sleep(2)
                            return True
                    except:
                        continue
            
            logger.error(f"❌ Could not find edit button for '{section_text}'")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error clicking edit for '{section_text}': {e}")
            return False
    
    def _find_profile_field(self, field_identifiers):
        """
        Find input/textarea fields using multiple strategies
        field_identifiers: list of possible names, ids, or placeholders
        """
        try:
            # Try by name attribute
            for identifier in field_identifiers:
                try:
                    field = self.driver.find_element(By.NAME, identifier)
                    if field.is_displayed():
                        return field
                except:
                    continue
            
            # Try by ID
            for identifier in field_identifiers:
                try:
                    field = self.driver.find_element(By.ID, identifier)
                    if field.is_displayed():
                        return field
                except:
                    continue
            
            # Try by placeholder
            for identifier in field_identifiers:
                try:
                    field = self.driver.find_element(
                        By.XPATH, f"//textarea[contains(@placeholder, '{identifier}')] | //input[contains(@placeholder, '{identifier}')]"
                    )
                    if field.is_displayed():
                        return field
                except:
                    continue
            
            # Try any visible textarea (last resort)
            try:
                textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                for textarea in textareas:
                    if textarea.is_displayed() and textarea.is_enabled():
                        return textarea
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding field: {e}")
            return None
    
    def _click_save_button(self):
        """
        ENHANCED VERSION with debugging: Finds and clicks save button with extensive logging
        """
        try:
            logger.info("🔍 Starting save button search...")
            
            # First, let's see ALL buttons on the page for debugging
            try:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                logger.info(f"📊 Found {len(all_buttons)} total buttons on page")
                
                # Log all visible button texts for debugging
                for idx, btn in enumerate(all_buttons[:10]):  # Check first 10 buttons
                    try:
                        if btn.is_displayed():
                            btn_text = btn.text.strip()
                            btn_class = btn.get_attribute("class") or "no-class"
                            btn_type = btn.get_attribute("type") or "no-type"
                            logger.info(f"  Button {idx}: text='{btn_text}', class='{btn_class}', type='{btn_type}'")
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Could not enumerate buttons: {e}")
            
            # Extended list of save button selectors
            save_selectors = [
                # Text-based selectors
                "//button[contains(translate(text(), 'SAVE', 'save'), 'save')]",
                "//button[contains(translate(text(), 'UPDATE', 'update'), 'update')]",
                "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]",
                "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
                "//button[contains(translate(text(), 'OK', 'ok'), 'ok')]",
                "//button[contains(translate(text(), 'DONE', 'done'), 'done')]",
                
                # Class-based selectors
                "//button[contains(@class, 'save')]",
                "//button[contains(@class, 'submit')]",
                "//button[contains(@class, 'primary')]",
                "//button[contains(@class, 'btn-primary')]",
                "//button[contains(@class, 'positive')]",
                
                # Type-based selectors
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[@type='button'][contains(@class, 'primary')]",
                
                # Form selectors
                "//form//button[@type='submit']",
                "//form//button[contains(@class, 'primary')]",
                "//form//button[not(@type='button') and not(@type='reset')]",
                
                # Modal/Dialog selectors
                "//div[@role='dialog']//button[contains(@class, 'primary')]",
                "//div[@role='dialog']//button[@type='submit']",
                "//div[contains(@class, 'modal')]//button[contains(@class, 'primary')]",
                
                # Naukri-specific possibilities
                "//button[@id='saveButton']",
                "//button[contains(@ng-click, 'save')]",
                "//button[contains(@onclick, 'save')]"
            ]
            
            # Try each selector
            for selector in save_selectors:
                try:
                    # Don't wait too long for each selector
                    save_button = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    
                    if save_button.is_displayed() and save_button.is_enabled():
                        btn_text = save_button.text or "no-text"
                        logger.info(f"🎯 Found potential save button: '{btn_text}' with selector: {selector}")
                        
                        # Try to click it
                        try:
                            save_button.click()
                        except:
                            # If regular click fails, use JavaScript
                            self.driver.execute_script("arguments[0].click();", save_button)
                        
                        logger.info(f"✅ Successfully clicked save button: '{btn_text}'")
                        time.sleep(3)
                        return True
                        
                except TimeoutException:
                    continue
                except Exception as e:
                    continue
            
            # Ultra last resort - click ANY visible button that might be save
            logger.warning("⚠️ Trying ultra last resort - any button that might be save...")
            try:
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for button in buttons:
                    try:
                        if button.is_displayed() and button.is_enabled():
                            btn_text = button.text.strip().lower()
                            btn_class = (button.get_attribute("class") or "").lower()
                            
                            # Check if this could be a save button
                            save_keywords = ['save', 'update', 'submit', 'apply', 'done', 'ok', 'confirm']
                            class_keywords = ['primary', 'submit', 'save', 'positive', 'success']
                            
                            if any(keyword in btn_text for keyword in save_keywords) or \
                               any(keyword in btn_class for keyword in class_keywords):
                                logger.info(f"🎲 Attempting to click button: '{button.text}'")
                                self.driver.execute_script("arguments[0].click();", button)
                                logger.info(f"✅ Clicked button: '{button.text}'")
                                time.sleep(3)
                                return True
                    except:
                        continue
            except Exception as e:
                logger.error(f"Ultra last resort failed: {e}")
            
            # If we reach here, we couldn't find the save button
            logger.error("❌ Could not find save button after trying all methods")
            
            # Take a screenshot for debugging
            try:
                screenshot_path = f"save_button_not_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"📸 Screenshot saved: {screenshot_path}")
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Critical error in save button function: {e}")
            return False
    
    def _human_type(self, element, text):
        """Type text with faster, more reasonable delays"""
        element.clear()
        # Much faster typing - 2-5 milliseconds per character instead of 50-150ms
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.002, 0.005))  # Reduced from 0.05-0.15
    
    def _get_toggle_state(self, key):
        """Get current toggle state from file"""
        try:
            if os.path.exists(self.state_files.get(key, '')):
                with open(self.state_files[key], 'r') as f:
                    return f.read().strip() == 'True'
        except:
            pass
        return False
    
    def _set_toggle_state(self, key, value):
        """Save toggle state to file"""
        try:
            with open(self.state_files.get(key, f'{key}_state.txt'), 'w') as f:
                f.write(str(value))
        except:
            pass
    
    def get_next_strategy(self):
        """Get the next update strategy in rotation"""
        try:
            if os.path.exists(self.last_strategy_file):
                with open(self.last_strategy_file, 'r') as f:
                    last_strategy = f.read().strip()
                    if last_strategy in self.update_strategies:
                        last_index = self.update_strategies.index(last_strategy)
                        next_index = (last_index + 1) % len(self.update_strategies)
                        return self.update_strategies[next_index]
        except:
            pass
        
        return self.update_strategies[0]
    
    def save_last_strategy(self, strategy):
        """Save the last used strategy"""
        try:
            with open(self.last_strategy_file, 'w') as f:
                f.write(strategy)
        except:
            pass
    
    def update_profile(self):
        """Navigate to profile and make updates with skills_update as fallback"""
        try:
            logger.info("📝 Navigating to profile edit page...")
            
            # Navigate to profile
            profile_urls = [
                'https://www.naukri.com/mnjuser/profile',
                'https://www.naukri.com/mnjuser/profile?id=&altresid='
            ]
            
            for url in profile_urls:
                self.driver.get(url)
                time.sleep(3)
                if "profile" in self.driver.current_url:
                    break
            
            # Get next strategy
            strategy = self.get_next_strategy()
            logger.info(f"🔄 Using strategy: {strategy}")
            
            # Execute strategy
            success = False
            if strategy == 'headline_toggle':
                success = self._update_headline()
            elif strategy == 'summary_fullstop_toggle':
                success = self._update_summary()
            elif strategy == 'skills_update':
                success = self._update_skills()
            
            if success:
                self.save_last_strategy(strategy)
                logger.info(f"✅ Profile update successful using {strategy}")
                return True
            else:
                # FALLBACK TO SKILLS_UPDATE - the most reliable strategy
                logger.warning(f"⚠️ Strategy {strategy} failed, trying fallback: skills_update")
                
                # Navigate back to profile if needed
                if "profile" not in self.driver.current_url:
                    self.driver.get('https://www.naukri.com/mnjuser/profile')
                    time.sleep(3)
                
                # Try skills_update as fallback
                fallback_success = self._update_skills()
                
                if fallback_success:
                    # Still save the original strategy as "attempted" to maintain rotation
                    self.save_last_strategy(strategy)
                    logger.info(f"✅ Profile update successful using fallback (skills_update)")
                    return True
                else:
                    logger.error(f"❌ Both {strategy} and fallback failed")
                    return False
            
        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            # Last ditch effort - try skills_update
            try:
                logger.info("🆘 Attempting emergency fallback to skills_update...")
                if "profile" not in self.driver.current_url:
                    self.driver.get('https://www.naukri.com/mnjuser/profile')
                    time.sleep(3)
                if self._update_skills():
                    logger.info("✅ Emergency fallback successful!")
                    return True
            except:
                pass
            return False
    
    def _update_headline(self):
        """Toggle between two headline versions with proper error handling"""
        try:
            logger.info("🎯 Updating headline...")
            
            # Click edit for Resume headline section
            if not self._find_and_click_edit("Resume headline"):
                logger.error("Could not open headline edit")
                return False
            
            time.sleep(2)
            
            # Find the headline field
            headline_field = self._find_profile_field([
                "resumeHeadline",
                "headline",
                "Headline",
                "Resume headline"
            ])
            
            if not headline_field:
                logger.error("Could not find headline field")
                return False
            
            # Get current headline
            current_headline = headline_field.get_attribute('value') or headline_field.text
            
            # Define two headline versions
            headline_a = "Data Engineer | Python | SQL | AWS"
            headline_b = "Data Engineer | Python | SQL | Cloud"
            
            # If current headline matches neither, use the current with a minor change
            if headline_a not in current_headline and headline_b not in current_headline:
                # Just toggle a period at the end
                if current_headline.rstrip().endswith('.'):
                    new_headline = current_headline.rstrip()[:-1]
                else:
                    new_headline = current_headline.rstrip() + '.'
            else:
                # Toggle between our two versions
                should_use_b = self._get_toggle_state('headline_toggle')
                new_headline = headline_b if should_use_b else headline_a
                self._set_toggle_state('headline_toggle', not should_use_b)
            
            # Update the field
            headline_field.clear()
            self._human_type(headline_field, new_headline)
            time.sleep(1)
            
            # Save changes - WITH PROPER ERROR HANDLING
            if self._click_save_button():
                logger.info(f"✅ Headline successfully updated to: {new_headline[:50]}...")
                return True
            else:
                logger.error("❌ Failed to save headline changes")
                return False
            
        except Exception as e:
            logger.error(f"❌ Headline update failed: {e}")
            return False
    
    def _update_summary(self):
        """Toggle fullstop at the end of summary with proper error handling"""
        try:
            logger.info("🎯 Updating summary...")
            
            # Click edit for Profile summary section
            if not self._find_and_click_edit("Profile summary"):
                # Try alternative text
                if not self._find_and_click_edit("Summary"):
                    logger.error("Could not open summary edit")
                    return False
            
            time.sleep(2)
            
            # Find the summary field
            summary_field = self._find_profile_field([
                "summary",
                "profileSummary",
                "Summary",
                "Profile summary"
            ])
            
            if not summary_field:
                logger.error("Could not find summary field")
                return False
            
            # Get current summary
            current_summary = summary_field.get_attribute('value') or summary_field.text
            
            # Toggle fullstop
            if current_summary.rstrip().endswith('.'):
                new_summary = current_summary.rstrip()[:-1]
                logger.info("➖ Removing fullstop from summary")
            else:
                new_summary = current_summary.rstrip() + '.'
                logger.info("➕ Adding fullstop to summary")
            
            # Update the field
            summary_field.clear()
            self._human_type(summary_field, new_summary)
            time.sleep(1)
            
            # Save changes - WITH PROPER ERROR HANDLING
            if self._click_save_button():
                logger.info("✅ Summary successfully updated")
                return True
            else:
                logger.error("❌ Failed to save summary changes")
                return False
            
        except Exception as e:
            logger.error(f"❌ Summary update failed: {e}")
            return False
    
    def _update_skills(self):
        """Update skills section with proper error handling"""
        try:
            logger.info("🎯 Updating skills...")
            
            # Click edit for Key skills section
            if not self._find_and_click_edit("Key skills"):
                # Try alternative text
                if not self._find_and_click_edit("Skills"):
                    logger.error("Could not open skills edit")
                    return False
            
            time.sleep(3)
            
            # For skills, just opening and saving is enough to trigger an update
            # The act of visiting the section counts as activity
            
            # Save changes - WITH PROPER ERROR HANDLING
            if self._click_save_button():
                logger.info("✅ Skills section successfully updated")
                return True
            else:
                logger.error("❌ Failed to save skills changes")
                return False
            
        except Exception as e:
            logger.error(f"❌ Skills update failed: {e}")
            return False
    
    def run_profile_refresh(self, debug_mode=False):
        """Main execution method"""
        try:
            logger.info("🚀 Starting Naukri Profile Refresh...")
            
            # Setup driver
            if not self.setup_driver(debug_mode=debug_mode):
                logger.error("❌ Failed to setup driver")
                return False
            
            # Login
            if not self.login_to_naukri():
                logger.error("❌ Failed to login")
                return False
            
            # Update profile
            if not self.update_profile():
                logger.error("❌ Failed to update profile")
                return False
            
            logger.info("🎉 Profile refresh completed successfully!")
            
            # Log session info
            self._log_session()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Profile refresh failed: {e}")
            return False
        
        finally:
            if self.driver:
                self.driver.quit()
    
    def _log_session(self):
        """Log session information"""
        try:
            session_info = {
                'timestamp': datetime.now().isoformat(),
                'status': 'success',
                'strategy_used': self.get_next_strategy()
            }
            
            with open('profile_refresh_log.json', 'w') as f:
                json.dump(session_info, f, indent=2)
                
        except Exception as e:
            logger.error(f"Logging failed: {e}")

# Main execution
if __name__ == "__main__":
    import sys
    
    print("🔄 Naukri Profile Refresher (COMPLETE FIXED VERSION)")
    print("✅ Enhanced debugging + Fast typing + Save button detection")
    print("=" * 60)
    
    # Check for debug mode flag
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv
    if debug_mode:
        print("🔍 RUNNING IN DEBUG MODE (visible browser)")
    
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh(debug_mode=debug_mode)
    
    if success:
        print("✅ Profile refresh completed successfully!")
    else:
        print("❌ Profile refresh failed - check logs above")
        print("\n💡 TIP: Run with --debug flag to see the browser:")
        print("   python naukri_profile_refresher.py --debug")
    
    sys.exit(0 if success else 1)