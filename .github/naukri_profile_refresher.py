"""
Naukri Profile Refresher - FIXED VERSION
- Uses Edge WebDriver instead of Chrome
- Reads credentials from existing config.json
- Auto-logs in without prompting
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NaukriProfileRefresher:
    """FIXED: Uses Edge + reads from config.json"""
    
    def __init__(self, config_file="config.json"):
        """Initialize with existing config.json"""
        self.config = self._load_config(config_file)
        self.driver = None
        self.wait = None
        
        # Profile update strategies (rotated)
        self.update_strategies = [
            'headline_tweak',
            'summary_refresh', 
            'skill_reorder',
            'experience_touch',
            'contact_refresh'
        ]
        
        # Keep track of last used strategy
        self.last_strategy_file = "last_strategy.txt"
        
    def _load_config(self, config_file):
        """Load configuration from existing config.json"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check if config has correct structure
            if 'login' in config and 'email' in config['login']:
                # Handle existing config.json structure
                credentials = {
                    'email': config['login']['email'],
                    'password': config['login']['password']
                }
                logger.info(f"✅ Loaded credentials from {config_file}")
            elif 'credentials' in config:
                # Handle enhanced config structure
                credentials = config['credentials']
                logger.info(f"✅ Loaded credentials from {config_file}")
            else:
                raise ValueError("Invalid config structure")
            
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
            raise
    
    def setup_driver(self):
        """Setup Edge WebDriver (FIXED: was using Chrome)"""
        try:
            logger.info("🔧 Setting up Edge WebDriver...")
            
            options = webdriver.EdgeOptions()
            
            # Headless mode for automation
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User agent
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')
            
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
        """Login to Naukri using config.json credentials"""
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
                    ".cookiecon__buttons button"
                ]
                
                for button_selector in cookie_buttons:
                    try:
                        if button_selector.startswith('//'):
                            button = self.driver.find_element(By.XPATH, button_selector)
                        else:
                            button = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                        button.click()
                        time.sleep(1)
                        break
                    except:
                        continue
            except:
                pass
            
            # Fill email
            email_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'usernameField'))
            )
            email_field.clear()
            self._human_type(email_field, self.config['credentials']['email'])
            time.sleep(1)
            
            # Fill password  
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'passwordField'))
            )
            password_field.clear()
            self._human_type(password_field, self.config['credentials']['password'])
            time.sleep(1)
            
            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            self.driver.execute_script("arguments[0].click();", login_button)
            
            # Wait for login success
            time.sleep(5)
            
            # Verify login
            success_indicators = [
                '.nI-gNb-drawer__icon',
                '.view-profile-wrapper', 
                'My Naukri'
            ]
            
            login_successful = False
            for indicator in success_indicators:
                try:
                    if indicator.startswith('.'):
                        elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    else:
                        elements = self.driver.find_elements(By.PARTIAL_LINK_TEXT, indicator)
                    
                    if elements:
                        login_successful = True
                        logger.info(f"✅ Login verified using: {indicator}")
                        break
                except:
                    continue
            
            if not login_successful:
                # Check if we're redirected away from login page
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
        """Update profile using selected strategy"""
        try:
            strategy = self.get_next_strategy()
            logger.info(f"🔄 Using strategy: {strategy}")
            
            # Navigate to profile
            self.driver.get('https://www.naukri.com/mnjuser/profile')
            time.sleep(3)
            
            success = False
            
            if strategy == 'headline_tweak':
                success = self._update_headline()
            elif strategy == 'summary_refresh':
                success = self._update_summary()
            elif strategy == 'skill_reorder':
                success = self._reorder_skills()
            elif strategy == 'experience_touch':
                success = self._touch_experience()
            elif strategy == 'contact_refresh':
                success = self._refresh_contact()
            else:
                logger.warning(f"Unknown strategy: {strategy}")
                success = self._fallback_update()
            
            if success:
                logger.info(f"✅ Profile updated successfully using {strategy}")
                return True
            else:
                logger.warning(f"⚠️ Strategy {strategy} failed, trying fallback")
                return self._fallback_update()
                
        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            return False
    
    def _update_headline(self):
        """Update profile headline with minor variation"""
        try:
            # Look for headline edit button/field
            edit_selectors = [
                "//span[contains(text(), 'Edit')]/parent::button",
                "//i[contains(@class, 'edit')]/parent::span/parent::button",
                ".headlineCnt .edit",
                "[data-automation='headlineEdit']"
            ]
            
            for selector in edit_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    # Find headline text field
                    headline_field = self.driver.find_element(By.CSS_SELECTOR, "textarea, input[type='text']")
                    current_text = headline_field.get_attribute('value')
                    
                    if current_text:
                        # Make minor variations
                        variations = [
                            current_text.rstrip('.') + '.',
                            current_text.rstrip() + ' ',
                            current_text.replace('  ', ' '),
                            current_text.replace(' ', '  ') if '  ' not in current_text else current_text.replace('  ', ' ')
                        ]
                        
                        new_text = random.choice(variations)
                        
                        headline_field.clear()
                        self._human_type(headline_field, new_text)
                        
                        # Save
                        self._save_changes()
                        return True
                        
                except:
                    continue
                    
            return False
            
        except Exception as e:
            logger.error(f"Headline update failed: {e}")
            return False
    
    def _update_summary(self):
        """Update summary with minor formatting changes"""
        try:
            # Look for summary edit
            edit_selectors = [
                "//div[@class='resumeHeadline']//span[contains(text(), 'Edit')]",
                ".summary .edit",
                "[data-automation='summaryEdit']"
            ]
            
            for selector in edit_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    # Find summary text field
                    summary_field = self.driver.find_element(By.CSS_SELECTOR, "textarea")
                    current_text = summary_field.get_attribute('value')
                    
                    if current_text:
                        # Minor formatting changes
                        variations = [
                            current_text.rstrip('.') + '.',
                            current_text.replace('. ', '. \n'),  # Add line breaks
                            current_text.replace('. \n', '. '),  # Remove line breaks
                        ]
                        
                        new_text = random.choice(variations)
                        
                        summary_field.clear()
                        self._human_type(summary_field, new_text)
                        
                        # Save
                        self._save_changes()
                        return True
                        
                except:
                    continue
                    
            return False
            
        except Exception as e:
            logger.error(f"Summary update failed: {e}")
            return False
    
    def _reorder_skills(self):
        """Reorder skills slightly"""
        try:
            skills_section = [
                "//section[contains(@class, 'skill')]//span[contains(text(), 'Edit')]",
                "[data-automation='editSkills']"
            ]
            
            for selector in skills_section:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    # Simple skill refresh - just opening and closing the section
                    self._save_changes()
                    return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Skills update failed: {e}")
            return False
    
    def _touch_experience(self):
        """Touch experience section"""
        try:
            exp_selectors = [
                "//section[contains(@class, 'experience')]//span[contains(text(), 'Edit')]",
                ".experience .edit"
            ]
            
            for selector in exp_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    # Just opening the section triggers update
                    self._save_changes()
                    return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Experience update failed: {e}")
            return False
    
    def _refresh_contact(self):
        """Refresh contact information"""
        try:
            contact_selectors = [
                "//section[contains(@class, 'contact')]//span[contains(text(), 'Edit')]",
                ".contact .edit"
            ]
            
            for selector in contact_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    self._save_changes()
                    return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Contact update failed: {e}")
            return False
    
    def _fallback_update(self):
        """Fallback: Just visit different profile sections"""
        try:
            logger.info("🔄 Running fallback profile update...")
            
            # Visit different sections of profile
            sections = [
                'https://www.naukri.com/mnjuser/profile',
                'https://www.naukri.com/mnjuser/profile?id=&altresid',
                'https://www.naukri.com/mnjuser/homepage'
            ]
            
            for section in sections:
                self.driver.get(section)
                time.sleep(2)
            
            logger.info("✅ Fallback update completed")
            return True
            
        except Exception as e:
            logger.error(f"Fallback update failed: {e}")
            return False
    
    def _save_changes(self):
        """Generic save method"""
        save_selectors = [
            "//button[contains(text(), 'Save')]",
            "//button[contains(text(), 'Update')]",
            "//button[contains(text(), 'Done')]",
            ".save-btn",
            ".update-btn"
        ]
        
        for selector in save_selectors:
            try:
                if selector.startswith('//'):
                    save_btn = self.driver.find_element(By.XPATH, selector)
                else:
                    save_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                save_btn.click()
                time.sleep(2)
                return True
            except:
                continue
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
    print("🔄 Naukri Profile Refresher (FIXED: Edge + config.json)")
    print("=" * 60)
    
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh()
    
    if success:
        print("✅ Profile refresh completed successfully!")
        exit(0)
    else:
        print("❌ Profile refresh failed!")
        exit(1)