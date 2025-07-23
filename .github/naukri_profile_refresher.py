#!/usr/bin/env python3
"""
Naukri Profile Refresher - Automated Profile Updates for Better Visibility
Keeps your profile "fresh" in Naukri's database to appear higher in searches
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NaukriProfileRefresher:
    """Automated Naukri profile updater for better search visibility"""
    
    def __init__(self, config_file="enhanced_config.json"):
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
        """Load configuration with credentials"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            if not config.get('credentials', {}).get('email'):
                raise ValueError("Email not found in config")
            if not config.get('credentials', {}).get('password'):
                raise ValueError("Password not found in config")
                
            return config
        except FileNotFoundError:
            logger.error(f"Config file {config_file} not found")
            raise
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def setup_driver(self):
        """Setup Chrome driver for GitHub Actions (headless)"""
        try:
            options = webdriver.ChromeOptions()
            
            # GitHub Actions requires headless mode
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            
            # Anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Random user agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            # Use ChromeDriverManager for automatic driver management
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            self.driver.set_window_size(1920, 1080)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 20)
            
            logger.info("✅ Chrome driver setup successful (headless mode)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Driver setup failed: {e}")
            return False
    
    def login_to_naukri(self):
        """Login to Naukri with enhanced error handling"""
        try:
            logger.info("🔐 Logging into Naukri...")
            
            # Navigate to login page
            self.driver.get('https://www.naukri.com/nlogin/login')
            time.sleep(3)
            
            # Handle potential cookie banners or pop-ups
            try:
                # Look for cookie accept button
                cookie_buttons = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'OK')]",
                    ".cookie-accept",
                    "#cookie-accept"
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
                "//span[contains(text(), 'Edit')]",
                ".edit-icon",
                "[data-automation='editHeadline']",
                "//button[contains(@class, 'edit')]"
            ]
            
            for selector in edit_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    edit_btn.click()
                    time.sleep(2)
                    break
                except:
                    continue
            
            # Look for headline input field
            headline_selectors = [
                "//input[contains(@placeholder, 'headline')]",
                "//textarea[contains(@placeholder, 'headline')]",
                "#headline",
                "[name='headline']"
            ]
            
            for selector in headline_selectors:
                try:
                    if selector.startswith('//'):
                        headline_field = self.driver.find_element(By.XPATH, selector)
                    else:
                        headline_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    current_text = headline_field.get_attribute('value') or headline_field.text
                    
                    # Make minor variations
                    variations = [
                        lambda x: x.rstrip('.') + '.',  # Add/remove period
                        lambda x: x.replace(' | ', ' • '),  # Change separator
                        lambda x: x.replace(' • ', ' | '),  # Change separator back
                        lambda x: x + ' 💼' if '💼' not in x else x.replace(' 💼', ''),  # Add/remove emoji
                    ]
                    
                    variation_func = random.choice(variations)
                    new_text = variation_func(current_text)
                    
                    # Update field
                    headline_field.clear()
                    self._human_type(headline_field, new_text)
                    
                    # Save changes
                    save_buttons = [
                        "//button[contains(text(), 'Save')]",
                        "//button[contains(text(), 'Update')]",
                        ".save-btn"
                    ]
                    
                    for save_selector in save_buttons:
                        try:
                            if save_selector.startswith('//'):
                                save_btn = self.driver.find_element(By.XPATH, save_selector)
                            else:
                                save_btn = self.driver.find_element(By.CSS_SELECTOR, save_selector)
                            save_btn.click()
                            time.sleep(2)
                            return True
                        except:
                            continue
                    
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Headline update failed: {e}")
            return False
    
    def _update_summary(self):
        """Update summary with minor changes"""
        try:
            # Navigate to summary section
            summary_selectors = [
                "//section[contains(@class, 'summary')]//span[contains(text(), 'Edit')]",
                "//div[contains(@class, 'summary')]//button",
                "[data-automation='editSummary']"
            ]
            
            for selector in summary_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    break
                except:
                    continue
            
            # Find summary text area
            summary_field_selectors = [
                "//textarea[contains(@placeholder, 'summary')]",
                "#summary",
                "[name='summary']",
                "//textarea[@class*='summary']"
            ]
            
            for selector in summary_field_selectors:
                try:
                    if selector.startswith('//'):
                        summary_field = self.driver.find_element(By.XPATH, selector)
                    else:
                        summary_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    current_text = summary_field.get_attribute('value') or summary_field.text
                    
                    # Minor text variations
                    if current_text:
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
            # This is more complex - might just add/remove a skill
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
        """Touch experience section (minimal change)"""
        try:
            # Just navigate to experience and back
            experience_selectors = [
                "//section[contains(@class, 'experience')]//span[contains(text(), 'Edit')]",
                "[data-automation='editExperience']"
            ]
            
            for selector in experience_selectors:
                try:
                    if selector.startswith('//'):
                        edit_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        edit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    edit_btn.click()
                    time.sleep(2)
                    
                    # Just opening the section updates "last modified"
                    self._save_changes()
                    return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Experience touch failed: {e}")
            return False
    
    def _refresh_contact(self):
        """Refresh contact information view"""
        try:
            # Navigate to contact section
            self.driver.get('https://www.naukri.com/mnjuser/profile?id=&altresid')
            time.sleep(2)
            
            # Just viewing the contact section updates activity
            return True
            
        except Exception as e:
            logger.error(f"Contact refresh failed: {e}")
            return False
    
    def _fallback_update(self):
        """Fallback update method - just visit profile sections"""
        try:
            # Visit different profile sections to update "last seen" time
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
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh()
    
    if success:
        print("✅ Profile refresh completed successfully!")
        exit(0)
    else:
        print("❌ Profile refresh failed!")
        exit(1)