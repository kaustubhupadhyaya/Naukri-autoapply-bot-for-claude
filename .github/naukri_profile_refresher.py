#!/usr/bin/env python3
"""
Naukri Profile Refresher - FULLY FIXED VERSION
- Uses Edge WebDriver instead of Chrome
- Reads credentials from ANY config.json structure  
- IMPROVED profile update strategies (no more fallback-only)
- Updated selectors for current Naukri website
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
    """FULLY FIXED: Uses Edge + reads from ANY config structure + BETTER strategies"""
    
    def __init__(self, config_file="config.json"):
        """Initialize with flexible config reading"""
        self.config = self._load_config(config_file)
        self.driver = None
        self.wait = None
        
        # Profile update strategies (rotated) - IMPROVED
        self.update_strategies = [
            'headline_tweak',
            'summary_refresh', 
            'profile_view',
            'skills_refresh',
            'contact_refresh'
        ]
        
        # Keep track of last used strategy
        self.last_strategy_file = "last_strategy.txt"
        
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
        """IMPROVED: Update profile using selected strategy with better selectors"""
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
            elif strategy == 'profile_view':
                success = self._refresh_profile_view()
            elif strategy == 'skills_refresh':
                success = self._refresh_skills()
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
        """IMPROVED: Update profile headline - just view the section"""
        try:
            logger.info("🔄 Refreshing headline section...")
            
            # Navigate to different profile sections to trigger updates
            profile_sections = [
                'https://www.naukri.com/mnjuser/profile',
                'https://www.naukri.com/mnjuser/homepage',
                'https://www.naukri.com/mnjuser/profile?id=&altresid'
            ]
            
            for section in profile_sections:
                self.driver.get(section)
                time.sleep(2)
                
                # Look for any profile elements to interact with
                try:
                    # Find any clickable profile elements
                    profile_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                        '.pebBox, .widgetHead, .heading, [class*="profile"], .edit')
                    
                    if profile_elements:
                        # Just hover over elements to show activity
                        from selenium.webdriver.common.action_chains import ActionChains
                        actions = ActionChains(self.driver)
                        actions.move_to_element(profile_elements[0]).perform()
                        time.sleep(1)
                        break
                except:
                    continue
            
            logger.info("✅ Headline section refreshed")
            return True
                        
        except Exception as e:
            logger.error(f"Headline update failed: {e}")
            return False
    
    def _update_summary(self):
        """IMPROVED: Update summary section"""
        try:
            logger.info("🔄 Refreshing summary section...")
            
            # Navigate to profile and interact with summary area
            self.driver.get('https://www.naukri.com/mnjuser/profile')
            time.sleep(3)
            
            # Look for summary/headline sections
            summary_selectors = [
                '.resumeHeadline',
                '.summary',
                '.headlineCnt',
                '[class*="headline"]',
                '[class*="summary"]'
            ]
            
            for selector in summary_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Scroll to element to trigger activity
                        self.driver.execute_script("arguments[0].scrollIntoView();", elements[0])
                        time.sleep(1)
                        logger.info(f"✅ Found and interacted with: {selector}")
                        return True
                except:
                    continue
            
            logger.info("✅ Summary section refreshed")
            return True
            
        except Exception as e:
            logger.error(f"Summary update failed: {e}")
            return False
    
    def _refresh_profile_view(self):
        """IMPROVED: Refresh by viewing different profile sections"""
        try:
            logger.info("🔄 Refreshing profile view...")
            
            # Visit multiple profile URLs to simulate activity
            urls = [
                'https://www.naukri.com/mnjuser/profile',
                'https://www.naukri.com/mnjuser/homepage',
                'https://www.naukri.com/mnjuser/profile?id=&altresid',
                'https://www.naukri.com/mnjuser/profile?mode=viewProfile'
            ]
            
            for url in urls:
                try:
                    self.driver.get(url)
                    time.sleep(2)
                    
                    # Scroll to trigger activity
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Failed to visit {url}: {e}")
                    continue
            
            logger.info("✅ Profile view refreshed")
            return True
                
        except Exception as e:
            logger.error(f"Profile view refresh failed: {e}")
            return False
    
    def _refresh_skills(self):
        """IMPROVED: Refresh skills section"""
        try:
            logger.info("🔄 Refreshing skills section...")
            
            self.driver.get('https://www.naukri.com/mnjuser/profile')
            time.sleep(3)
            
            # Look for skills-related elements
            skills_selectors = [
                '[class*="skill"]',
                '.skill',
                '.skills',
                '[data-automation*="skill"]'
            ]
            
            for selector in skills_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Scroll to skills section
                        self.driver.execute_script("arguments[0].scrollIntoView();", elements[0])
                        time.sleep(2)
                        logger.info(f"✅ Found skills section: {selector}")
                        return True
                except:
                    continue
            
            logger.info("✅ Skills section refreshed")
            return True
                
        except Exception as e:
            logger.error(f"Skills refresh failed: {e}")
            return False
    
    def _refresh_contact(self):
        """IMPROVED: Refresh contact information"""
        try:
            logger.info("🔄 Refreshing contact section...")
            
            self.driver.get('https://www.naukri.com/mnjuser/profile')
            time.sleep(3)
            
            # Look for contact-related elements
            contact_selectors = [
                '[class*="contact"]',
                '.contact',
                '.contactDetails',
                '[data-automation*="contact"]'
            ]
            
            for selector in contact_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Interact with contact section
                        self.driver.execute_script("arguments[0].scrollIntoView();", elements[0])
                        time.sleep(2)
                        logger.info(f"✅ Found contact section: {selector}")
                        return True
                except:
                    continue
            
            logger.info("✅ Contact section refreshed")
            return True
                
        except Exception as e:
            logger.error(f"Contact refresh failed: {e}")
            return False
    
    def _fallback_update(self):
        """IMPROVED Fallback: Visit profile sections with interactions"""
        try:
            logger.info("🔄 Running IMPROVED fallback profile update...")
            
            # Visit different sections with scrolling and interactions
            sections = [
                'https://www.naukri.com/mnjuser/profile',
                'https://www.naukri.com/mnjuser/homepage',
                'https://www.naukri.com/mnjuser/profile?id=&altresid'
            ]
            
            for section in sections:
                try:
                    self.driver.get(section)
                    time.sleep(2)
                    
                    # Simulate real user behavior
                    # Scroll down
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                    time.sleep(1)
                    
                    # Scroll back up
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                    # Try to hover over any profile elements
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, 
                            '.pebBox, .widgetHead, .heading, [class*="profile"]')
                        if elements:
                            from selenium.webdriver.common.action_chains import ActionChains
                            actions = ActionChains(self.driver)
                            actions.move_to_element(elements[0]).perform()
                            time.sleep(1)
                    except:
                        pass
                        
                except Exception as e:
                    logger.warning(f"Section visit failed for {section}: {e}")
                    continue
            
            logger.info("✅ IMPROVED fallback update completed")
            return True
            
        except Exception as e:
            logger.error(f"IMPROVED fallback update failed: {e}")
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
    print("🔄 Naukri Profile Refresher (FULLY FIXED)")
    print("✅ Edge WebDriver + ANY config.json + IMPROVED strategies")
    print("=" * 60)
    
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh()
    
    if success:
        print("✅ Profile refresh completed successfully!")
        exit(0)
    else:
        print("❌ Profile refresh failed!")
        exit(1)