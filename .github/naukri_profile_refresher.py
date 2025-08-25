 """
Naukri Profile Refresher - SPAN-BASED SELECTORS VERSION
- Uses Edge WebDriver with CORRECT span selectors (not buttons!)
- REAL profile changes that toggle between runs
- Fixed based on actual Naukri HTML structure using <span class="edit icon">
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
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NaukriProfileRefresher:
    """FIXED: Uses correct span.edit.icon selectors based on real Naukri HTML"""
    
    def __init__(self, config_file="config.json"):
        """Initialize with flexible config reading"""
        self.config = self._load_config(config_file)
        self.driver = None
        self.wait = None
        
        # Targeted update strategies - REAL CHANGES
        self.update_strategies = [
            'headline_dbt_toggle',
            'skills_dbt_toggle', 
            'summary_fullstop_toggle',
            'linkedin_profile_toggle',
            'salary_toggle'
        ]
        
        # State tracking files for toggle functionality
        self.state_files = {
            'headline_dbt': 'headline_dbt_state.txt',
            'skills_dbt': 'skills_dbt_state.txt', 
            'summary_fullstop': 'summary_fullstop_state.txt',
            'linkedin_profile': 'linkedin_profile_state.txt',
            'salary_toggle': 'salary_toggle_state.txt'
        }
        
        self.last_strategy_file = "last_strategy.txt"
        
        # Your specific profile data
        self.linkedin_url = "https://www.linkedin.com/in/kaustubh-upadhyaya/"
        
    def _load_config(self, config_file):
        """Load configuration from ANY config.json structure"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Handle MULTIPLE config structures
            credentials = None
            
            # Structure 1: "credentials" (user's current structure)
            if 'credentials' in config:
                credentials = {
                    'email': config['credentials']['email'],
                    'password': config['credentials']['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (credentials structure)")
            
            # Structure 2: "login" (alternative structure)
            elif 'login' in config:
                credentials = {
                    'email': config['login']['email'],
                    'password': config['login']['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (login structure)")
            
            # Structure 3: Direct email/password (fallback)
            elif 'email' in config and 'password' in config:
                credentials = {
                    'email': config['email'],
                    'password': config['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file} (direct structure)")
            
            else:
                raise ValueError("No valid credentials structure found in config")
            
            if not credentials['email'] or not credentials['password']:
                raise ValueError("Email or password is empty")
            
            # Return standardized config
            return {
                'credentials': credentials,
                'personal_info': config.get('personal_info', {
                    'firstname': credentials['email'].split('@')[0],
                    'lastname': 'User'
                })
            }
            
        except FileNotFoundError:
            logger.error(f"❌ Config file {config_file} not found!")
            logger.info("Please ensure config.json exists with your Naukri credentials")
            raise
        except Exception as e:
            logger.error(f"❌ Config loading failed: {e}")
            logger.info("Check your config.json format - email and password are required")
            raise
    
    def setup_driver(self):
        """Setup Edge WebDriver with improved settings"""
        try:
            logger.info("🔧 Setting up Edge WebDriver...")
            
            options = webdriver.EdgeOptions()
            
            # Headless mode for automation
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            
            # Anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User agent - Updated for 2024
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')
            
            # Try automatic Edge driver setup
            try:
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ Edge driver auto-download successful")
            except Exception as e:
                logger.warning(f"Auto-download failed: {e}")
                # Try manual path fallback
                manual_paths = [
                    r"C:\WebDrivers\msedgedriver.exe",
                    r"C:\edgedriver\msedgedriver.exe",
                    "msedgedriver.exe"  # If in PATH
                ]
                
                driver_found = False
                for path in manual_paths:
                    if os.path.exists(path):
                        logger.info(f"🔄 Trying manual path: {path}")
                        service = EdgeService(path)
                        self.driver = webdriver.Edge(service=service, options=options)
                        driver_found = True
                        break
                
                if not driver_found:
                    logger.error("❌ No Edge driver found! Please install Edge WebDriver")
                    return False
            
            self.driver.set_window_size(1280, 720)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 20)
            
            logger.info("✅ Edge driver setup successful (headless mode)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Edge driver setup failed: {e}")
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
                cookie_selectors = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Got it')]",
                    "//button[contains(text(), 'Allow')]",
                    ".cookiecon__buttons button",
                    "#accept-cookies"
                ]
                
                for selector in cookie_selectors:
                    try:
                        if selector.startswith('//'):
                            button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        else:
                            button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        button.click()
                        time.sleep(1)
                        break
                    except TimeoutException:
                        continue
            except:
                pass
            
            # Fill email with multiple selector fallbacks
            email_selectors = [
                '#usernameField',
                'input[placeholder*="Email"]',
                'input[placeholder*="email"]',
                'input[name="email"]',
                'input[type="email"]'
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not email_field:
                logger.error("❌ Could not find email field")
                return False
            
            email_field.clear()
            self._human_type(email_field, self.config['credentials']['email'])
            time.sleep(1)
            
            # Fill password with multiple selector fallbacks
            password_selectors = [
                '#passwordField',
                'input[placeholder*="Password"]',
                'input[placeholder*="password"]',
                'input[name="password"]',
                'input[type="password"]'
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not password_field:
                logger.error("❌ Could not find password field")
                return False
            
            password_field.clear()
            self._human_type(password_field, self.config['credentials']['password'])
            time.sleep(1)
            
            # Click login button
            login_selectors = [
                "//button[@type='submit']",
                "//button[contains(text(), 'Login')]",
                ".loginButton",
                "input[type='submit']"
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    if selector.startswith('//'):
                        login_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if login_button:
                self.driver.execute_script("arguments[0].click();", login_button)
            else:
                logger.error("❌ Could not find login button")
                return False
            
            # Wait for login success
            time.sleep(5)
            
            # Verify login with updated selectors
            success_indicators = [
                '.nI-gNb-drawer__icon',  # Profile menu icon
                '.view-profile-wrapper',  # Profile link
                '.nI-gNb-userName',  # Username display
                '[data-ga-track="dashboard_menu_wrapper"]'  # Dashboard menu
            ]
            
            login_successful = False
            for indicator in success_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements and elements[0].is_displayed():
                        login_successful = True
                        logger.info(f"✅ Login verified using: {indicator}")
                        break
                except:
                    continue
            
            if not login_successful:
                # Check URL redirect as backup verification
                current_url = self.driver.current_url.lower()
                if 'login' not in current_url and 'nlogin' not in current_url:
                    login_successful = True
                    logger.info("✅ Login verified by URL redirect")
            
            if login_successful:
                logger.info("🎉 Login successful!")
                return True
            else:
                logger.error("❌ Login failed - could not verify success")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            return False
    
    def _human_type(self, element, text):
        """Type text like a human"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def _get_toggle_state(self, state_key):
        """Get current toggle state (True = add, False = remove)"""
        state_file = self.state_files.get(state_key)
        if not state_file:
            return True
        
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    return f.read().strip().lower() == 'true'
            else:
                return True  # Default to add
        except:
            return True
    
    def _set_toggle_state(self, state_key, state):
        """Set toggle state for next run"""
        state_file = self.state_files.get(state_key)
        if state_file:
            try:
                with open(state_file, 'w') as f:
                    f.write('true' if state else 'false')
            except:
                pass
    
    def _click_edit_span(self, text_content, timeout=10):
        """Click edit span by finding text content first - FIXED WITH TEXT-BASED XPATH!"""
        
        # First, verify the text exists on the page
        try:
            text_elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text_content}')]")
            if not text_elements:
                logger.warning(f"⚠️ No text '{text_content}' found on page")
                self._debug_available_edit_spans(text_content)
                return False
            else:
                logger.info(f"✅ Found {len(text_elements)} elements containing '{text_content}'")
        except:
            pass
        
        # PRIMARY: Text-based XPath selectors (the correct approach)
        text_based_selectors = [
            # Find the text, then navigate to sibling edit span
            f"//span[contains(text(), '{text_content}')]/following-sibling::span[contains(@class, 'edit')]",
            f"//span[contains(text(), '{text_content}')]/following-sibling::*[contains(@class, 'edit')]",
            
            # Find the text, then navigate to parent's edit span  
            f"//span[contains(text(), '{text_content}')]/parent::*//*[contains(@class, 'edit')]",
            f"//span[contains(text(), '{text_content}')]/parent::*//span[contains(@class, 'edit')]",
            
            # Find the text, then navigate up and find edit span
            f"//span[contains(text(), '{text_content}')]/ancestor::*[1]//*[contains(@class, 'edit')]",
            f"//span[contains(text(), '{text_content}')]/ancestor::*[2]//*[contains(@class, 'edit')]",
            
            # Alternative class patterns
            f"//span[contains(text(), '{text_content}')]/following-sibling::span[@class='edit icon']",
            f"//span[contains(text(), '{text_content}')]/parent::*//span[@class='edit icon']",
            
            # More flexible text matching
            f"//*[contains(text(), '{text_content}')]/parent::*//*[contains(@class, 'edit')]",
            f"//*[contains(text(), '{text_content}')]/following-sibling::*[contains(@class, 'edit')]"
        ]
        
        for selector in text_based_selectors:
            try:
                edit_span = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", edit_span)
                time.sleep(1)
                edit_span.click()
                logger.info(f"✅ Clicked edit span for '{text_content}' using: {selector[:80]}...")
                return True
            except:
                continue
        
        # Debug: Show available edit spans
        self._debug_available_edit_spans(text_content)
        logger.warning(f"⚠️ Could not find edit span for: {text_content}")
        return False
    
    def _debug_available_edit_spans(self, target_text):
        """Debug helper: Show available edit spans with better text matching"""
        try:
            logger.info(f"🔍 DEBUG: Looking for '{target_text}' edit span, available edit elements:")
            
            # Find all edit spans and their context
            edit_spans = self.driver.find_elements(By.CSS_SELECTOR, '.edit.icon, span.edit.icon, [class*="edit"]')
            
            for i, span in enumerate(edit_spans[:10]):
                try:
                    if span.is_displayed():
                        # Get parent element text to understand context
                        parent = span.find_element(By.XPATH, './ancestor::*[1]')
                        parent_text = parent.text.strip()[:50]
                        
                        # Check if this might be our target
                        match_indicator = ""
                        if target_text.lower() in parent_text.lower():
                            match_indicator = " 🎯 POSSIBLE MATCH!"
                        
                        logger.info(f"   {i+1}. Edit span near: '{parent_text}'{match_indicator}")
                        
                        # Show XPath that would find this element
                        if match_indicator:
                            logger.info(f"      Try XPath: //span[contains(text(), '{target_text}')]/following-sibling::span[contains(@class, 'edit')]")
                            
                except Exception as e:
                    logger.info(f"   {i+1}. Edit span (error getting context: {e})")
            
            if len(edit_spans) > 10:
                logger.info(f"   ... and {len(edit_spans) - 10} more edit spans")
            
            # Also show all text content that might contain our target
            logger.info(f"🔍 All text containing '{target_text}':")
            try:
                text_elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{target_text}')]")
                for i, element in enumerate(text_elements[:5]):
                    if element.is_displayed():
                        logger.info(f"   Text {i+1}: '{element.text.strip()[:50]}'")
            except:
                logger.info("   Could not find text elements")
                
        except Exception as e:
            logger.warning(f"Debug failed: {e}")
    
    def _click_save_button(self, timeout=5):
        """Click save/update button in modal"""
        save_selectors = [
            "//button[contains(text(), 'Save')]",
            "//button[contains(text(), 'Update')]", 
            "//button[contains(text(), 'Done')]",
            ".btn-dark-ot",
            "button[type='submit']",
            ".save-btn"
        ]
        
        for selector in save_selectors:
            try:
                if selector.startswith('//'):
                    save_btn = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    save_btn = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                save_btn.click()
                logger.info(f"✅ Clicked save button: {selector}")
                return True
            except:
                continue
        
        logger.warning("⚠️ Could not find save button")
        return False
    
    def get_next_strategy(self):
        """Get next update strategy in rotation"""
        try:
            if os.path.exists(self.last_strategy_file):
                with open(self.last_strategy_file, 'r') as f:
                    last_strategy = f.read().strip()
                
                try:
                    last_index = self.update_strategies.index(last_strategy)
                    next_index = (last_index + 1) % len(self.update_strategies)
                except ValueError:
                    next_index = 0
            else:
                next_index = 0
            
            strategy = self.update_strategies[next_index]
            
            # Save current strategy
            with open(self.last_strategy_file, 'w') as f:
                f.write(strategy)
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error getting strategy: {e}")
            return self.update_strategies[0]
    
    def update_profile(self):
        """TARGETED: Update profile using specific strategies with smart fallback"""
        try:
            strategy = self.get_next_strategy()
            logger.info(f"🔄 Using strategy: {strategy}")
            
            # Navigate to profile
            self.driver.get('https://www.naukri.com/mnjuser/profile?id=&altresid')
            time.sleep(4)
            
            success = False
            
            if strategy == 'headline_dbt_toggle':
                success = self._headline_dbt_toggle()
            elif strategy == 'skills_dbt_toggle':
                success = self._skills_dbt_toggle()
            elif strategy == 'summary_fullstop_toggle':
                success = self._summary_fullstop_toggle()
            elif strategy == 'linkedin_profile_toggle':
                success = self._linkedin_profile_toggle()
            elif strategy == 'salary_toggle':
                success = self._salary_toggle()
            
            if success:
                logger.info(f"✅ Profile updated successfully using {strategy}")
                return True
            else:
                # Smart fallback: try next strategy in line
                logger.warning(f"⚠️ Strategy {strategy} failed, trying next strategy")
                return self._try_next_strategy(strategy)
                
        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            return False
    
    def _try_next_strategy(self, failed_strategy):
        """Try the next strategy in line as fallback"""
        try:
            current_index = self.update_strategies.index(failed_strategy)
            next_index = (current_index + 1) % len(self.update_strategies)
            next_strategy = self.update_strategies[next_index]
            
            logger.info(f"🔄 Trying fallback strategy: {next_strategy}")
            
            success = False
            
            if next_strategy == 'headline_dbt_toggle':
                success = self._headline_dbt_toggle()
            elif next_strategy == 'skills_dbt_toggle':
                success = self._skills_dbt_toggle()
            elif next_strategy == 'summary_fullstop_toggle':
                success = self._summary_fullstop_toggle()
            elif next_strategy == 'linkedin_profile_toggle':
                success = self._linkedin_profile_toggle()
            elif next_strategy == 'salary_toggle':
                success = self._salary_toggle()
            
            if success:
                logger.info(f"✅ Fallback strategy {next_strategy} succeeded")
                return True
            else:
                logger.warning(f"⚠️ Fallback strategy {next_strategy} also failed")
                # Try one more strategy
                final_index = (next_index + 1) % len(self.update_strategies)
                final_strategy = self.update_strategies[final_index]
                
                logger.info(f"🔄 Final attempt with: {final_strategy}")
                
                if final_strategy == 'headline_dbt_toggle':
                    success = self._headline_dbt_toggle()
                elif final_strategy == 'skills_dbt_toggle':
                    success = self._skills_dbt_toggle()
                elif final_strategy == 'summary_fullstop_toggle':
                    success = self._summary_fullstop_toggle()
                elif final_strategy == 'linkedin_profile_toggle':
                    success = self._linkedin_profile_toggle()
                elif final_strategy == 'salary_toggle':
                    success = self._salary_toggle()
                
                if success:
                    logger.info(f"✅ Final strategy {final_strategy} succeeded")
                    return True
                else:
                    logger.error("❌ All strategies failed")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Fallback strategy failed: {e}")
            return False
    
    def _headline_dbt_toggle(self):
        """Toggle DBT in headline - FIXED WITH TEXT-BASED SELECTORS"""
        try:
            logger.info("🔄 Toggling DBT in headline...")
            
            # Click headline edit span using the actual visible text
            if not self._click_edit_span("Resume headline"):
                logger.error("❌ Could not find headline edit span")
                return False
            
            time.sleep(3)
            
            # Find headline text field in the modal
            headline_selectors = [
                'textarea[name="headline"]',
                'textarea[placeholder*="headline"]',
                'textarea[placeholder*="Headline"]',
                'input[name="headline"]',
                'textarea',
                'input[type="text"]'
            ]
            
            headline_field = None
            for selector in headline_selectors:
                try:
                    fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for field in fields:
                        if field.is_displayed() and field.is_enabled():
                            headline_field = field
                            break
                    if headline_field:
                        break
                except:
                    continue
            
            if not headline_field:
                logger.error("❌ Could not find headline field")
                return False
            
            current_text = headline_field.get_attribute('value') or headline_field.text
            should_add = self._get_toggle_state('headline_dbt')
            
            if should_add:
                # Add DBT if not present
                if 'DBT' not in current_text:
                    new_text = current_text.strip() + ', DBT'
                    logger.info("➕ Adding DBT to headline")
                else:
                    logger.info("ℹ️ DBT already in headline")
                    new_text = current_text
            else:
                # Remove DBT if present
                if 'DBT' in current_text:
                    new_text = current_text.replace(', DBT', '').replace('DBT,', '').replace('DBT', '').strip()
                    logger.info("➖ Removing DBT from headline")
                else:
                    logger.info("ℹ️ DBT not in headline")
                    new_text = current_text
            
            # Update the field
            headline_field.clear()
            time.sleep(1)
            self._human_type(headline_field, new_text)
            time.sleep(2)
            
            # Save changes
            self._click_save_button()
            time.sleep(3)
            
            # Toggle state for next run
            self._set_toggle_state('headline_dbt', not should_add)
            
            logger.info("✅ Headline DBT toggle completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Headline DBT toggle failed: {e}")
            return False
    
    def _skills_dbt_toggle(self):
        """Toggle DBT in skills - FIXED WITH TEXT-BASED SELECTORS"""
        try:
            logger.info("🔄 Toggling DBT in skills...")
            
            # Click skills edit span using the actual visible text
            if not self._click_edit_span("Key skills"):
                logger.error("❌ Could not find skills edit span")
                return False
            
            time.sleep(3)
            
            should_add = self._get_toggle_state('skills_dbt')
            
            if should_add:
                # Add DBT skill
                logger.info("➕ Adding DBT skill")
                
                # Look for skill input field
                skill_input_selectors = [
                    'input[placeholder*="skill"]',
                    'input[placeholder*="Skill"]',
                    'input[name*="skill"]',
                    '.skill-input input',
                    'input[type="text"]',
                    'input[placeholder*="Enter"]'
                ]
                
                skill_field = None
                for selector in skill_input_selectors:
                    try:
                        fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for field in fields:
                            if field.is_displayed() and field.is_enabled():
                                skill_field = field
                                break
                        if skill_field:
                            break
                    except:
                        continue
                
                if skill_field:
                    skill_field.clear()
                    self._human_type(skill_field, "DBT")
                    time.sleep(1)
                    
                    # Try to add the skill
                    self._click_save_button()
                else:
                    logger.error("❌ Could not find skill input field")
                    return False
            else:
                # Remove DBT skill
                logger.info("➖ Removing DBT skill")
                
                # Look for DBT skill to delete
                dbt_skill_selectors = [
                    "//span[contains(text(), 'DBT')]/following-sibling::*",
                    "//span[contains(text(), 'DBT')]/parent::*//*[contains(@class, 'delete')]",
                    "//span[contains(text(), 'DBT')]/parent::*//*[contains(text(), '×')]",
                    "//span[contains(text(), 'DBT')]/parent::*//*[contains(@title, 'delete')]"
                ]
                
                deleted = False
                for selector in dbt_skill_selectors:
                    try:
                        delete_btn = self.driver.find_element(By.XPATH, selector)
                        if delete_btn.is_displayed():
                            delete_btn.click()
                            logger.info("✅ DBT skill deleted")
                            deleted = True
                            break
                    except:
                        continue
                
                if not deleted:
                    logger.warning("⚠️ DBT skill not found to delete")
                
                # Save changes
                self._click_save_button()
            
            time.sleep(3)
            
            # Toggle state for next run
            self._set_toggle_state('skills_dbt', not should_add)
            
            logger.info("✅ Skills DBT toggle completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Skills DBT toggle failed: {e}")
            return False
    
    def _summary_fullstop_toggle(self):
        """Toggle full stop at end of summary - FIXED WITH TEXT-BASED SELECTORS"""
        try:
            logger.info("🔄 Toggling full stop in summary...")
            
            # Click summary edit span using the actual visible text
            if not self._click_edit_span("Profile summary"):
                logger.error("❌ Could not find summary edit span")
                return False
            
            time.sleep(3)
            
            # Find summary text field
            summary_selectors = [
                'textarea[name="summary"]',
                'textarea[placeholder*="summary"]',
                'textarea[placeholder*="Summary"]',
                'textarea'
            ]
            
            summary_field = None
            for selector in summary_selectors:
                try:
                    fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for field in fields:
                        if field.is_displayed() and field.is_enabled():
                            summary_field = field
                            break
                    if summary_field:
                        break
                except:
                    continue
            
            if not summary_field:
                logger.error("❌ Could not find summary field")
                return False
            
            current_text = summary_field.get_attribute('value') or summary_field.text
            should_add = self._get_toggle_state('summary_fullstop')
            
            if should_add:
                # Add full stop if not present
                if not current_text.endswith('.'):
                    new_text = current_text.strip() + '.'
                    logger.info("➕ Adding full stop to summary")
                else:
                    logger.info("ℹ️ Full stop already present")
                    new_text = current_text
            else:
                # Remove full stop if present
                if current_text.endswith('.'):
                    new_text = current_text.rstrip('.')
                    logger.info("➖ Removing full stop from summary")
                else:
                    logger.info("ℹ️ No full stop to remove")
                    new_text = current_text
            
            # Update the field
            summary_field.clear()
            self._human_type(summary_field, new_text)
            time.sleep(2)
            
            # Save changes
            self._click_save_button()
            time.sleep(3)
            
            # Toggle state for next run
            self._set_toggle_state('summary_fullstop', not should_add)
            
            logger.info("✅ Summary full stop toggle completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Summary full stop toggle failed: {e}")
            return False
    
    def _linkedin_profile_toggle(self):
        """Toggle LinkedIn profile URL - FIXED WITH TEXT-BASED SELECTORS"""
        try:
            logger.info("🔄 Toggling LinkedIn profile...")
            
            # For LinkedIn profile, we need to handle both existing and new profiles
            # First try to find existing online profile section
            try:
                # Look for existing online profile to edit
                if self._click_edit_span("Online profile"):
                    logger.info("✅ Found existing online profile to edit")
                else:
                    # Try to find "Add" button for online profile in accomplishments section
                    add_selectors = [
                        "//button[contains(text(), 'Add') and contains(preceding-sibling::*//text(), 'Online profile')]",
                        "//a[contains(text(), 'Add') and contains(preceding-sibling::*//text(), 'Online profile')]", 
                        "//a[contains(@href, 'profile') and contains(text(), 'Add')]",
                        "//button[contains(@class, 'blue-text') and contains(text(), 'Add')]"
                    ]
                    
                    found_add = False
                    for selector in add_selectors:
                        try:
                            add_btn = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            add_btn.click()
                            logger.info(f"✅ Clicked add button: {selector[:50]}...")
                            found_add = True
                            break
                        except:
                            continue
                    
                    if not found_add:
                        logger.error("❌ Could not find online profile edit span or add button")
                        return False
            except Exception as e:
                logger.error(f"❌ Error finding online profile section: {e}")
                return False
            
            time.sleep(3)
            
            should_add = self._get_toggle_state('linkedin_profile')
            
            if should_add:
                # Add LinkedIn profile
                logger.info("➕ Adding LinkedIn profile")
                
                # Look for URL input field
                url_selectors = [
                    'input[placeholder*="URL"]',
                    'input[placeholder*="url"]',
                    'input[placeholder*="link"]',
                    'input[placeholder*="profile"]',
                    'input[type="url"]',
                    'input[name*="url"]'
                ]
                
                url_field = None
                for selector in url_selectors:
                    try:
                        fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for field in fields:
                            if field.is_displayed() and field.is_enabled():
                                url_field = field
                                break
                        if url_field:
                            break
                    except:
                        continue
                
                if url_field:
                    url_field.clear()
                    self._human_type(url_field, self.linkedin_url)
                    time.sleep(1)
            else:
                # Remove LinkedIn profile (look for existing one to delete)
                logger.info("➖ Removing LinkedIn profile")
                
                # Look for delete button near LinkedIn URL
                delete_selectors = [
                    f"//a[contains(@href, 'linkedin.com')]/following-sibling::button",
                    f"//span[contains(text(), 'linkedin.com')]/parent::*//*[contains(@class, 'delete')]",
                    "//button[contains(@class, 'delBtn')]"
                ]
                
                for selector in delete_selectors:
                    try:
                        delete_btn = self.driver.find_element(By.XPATH, selector)
                        if delete_btn.is_displayed():
                            delete_btn.click()
                            logger.info("✅ LinkedIn profile deleted")
                            break
                    except:
                        continue
            
            # Save changes
            self._click_save_button()
            time.sleep(3)
            
            # Toggle state for next run
            self._set_toggle_state('linkedin_profile', not should_add)
            
            logger.info("✅ LinkedIn profile toggle completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ LinkedIn profile toggle failed: {e}")
            return False
    
    def _salary_toggle(self):
        """Toggle salary between 17 and 18 lakh - FIXED WITH TEXT-BASED SELECTORS"""
        try:
            logger.info("🔄 Toggling salary expectation...")
            
            # Navigate to career profile section
            self.driver.get('https://www.naukri.com/mnjuser/profile?id=&altresid')
            time.sleep(3)
            
            # Scroll to career profile section
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
            time.sleep(2)
            
            # Click career profile edit span using the actual visible text
            if not self._click_edit_span("Career profile"):
                logger.error("❌ Could not find career profile edit span")
                return False
            
            time.sleep(3)
            
            should_use_18 = self._get_toggle_state('salary_toggle')
            target_salary = "18" if should_use_18 else "17"
            
            logger.info(f"🔄 Setting salary to {target_salary} lakh")
            
            # Look for salary input fields
            salary_selectors = [
                'input[placeholder*="salary"]',
                'input[placeholder*="Salary"]',
                'input[placeholder*="amount"]',
                'input[placeholder*="lakh"]',
                'input[name*="salary"]',
                'input[type="number"]'
            ]
            
            salary_field = None
            for selector in salary_selectors:
                try:
                    fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for field in fields:
                        if field.is_displayed() and field.is_enabled():
                            salary_field = field
                            break
                    if salary_field:
                        break
                except:
                    continue
            
            if salary_field:
                salary_field.clear()
                self._human_type(salary_field, target_salary)
                time.sleep(1)
                
                # Save changes
                self._click_save_button()
                time.sleep(3)
                
                # Toggle state for next run
                self._set_toggle_state('salary_toggle', not should_use_18)
                
                logger.info(f"✅ Salary set to {target_salary} lakh")
                return True
            else:
                logger.error("❌ Could not find salary field")
                return False
            
        except Exception as e:
            logger.error(f"❌ Salary toggle failed: {e}")
            return False
    
    def run_profile_refresh(self):
        """Main execution method"""
        try:
            logger.info("🚀 Starting Naukri Profile Refresh...")
            
            # Setup driver
            if not self.setup_driver():
                return False
            
            # Login
            if not self.login_to_naukri():
                return False
            
            # Update profile
            if not self.update_profile():
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
    print("🔄 Naukri Profile Refresher (SPAN-BASED SELECTORS)")
    print("✅ Edge WebDriver + CORRECT span.edit.icon selectors")
    print("=" * 60)
    
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh()
    
    if success:
        print("✅ Profile refresh completed successfully!")
        exit(0)
    else:
        print("❌ Profile refresh failed!")
        exit(1)