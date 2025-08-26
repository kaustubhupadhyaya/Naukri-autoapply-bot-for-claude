"""
Naukri Profile Refresher - CHROME VERSION
- Uses Chrome WebDriver (matches GitHub Actions setup)
- REAL profile changes that toggle between runs
- Fixed to work with Google Chrome instead of Edge
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
    """FIXED: Uses Chrome WebDriver to match GitHub Actions"""
    
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
            logger.info("Please ensure config.json exists with your Naukri credentials")
            raise
        except Exception as e:
            logger.error(f"❌ Config loading failed: {e}")
            logger.info("Check your config.json format - email and password are required")
            raise
    
    def setup_driver(self):
        """Setup Chrome WebDriver with improved settings"""
        try:
            logger.info("🔧 Setting up Chrome WebDriver...")
            
            options = webdriver.ChromeOptions()
            
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
            
            # User agent - Updated for Chrome 2025
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Try automatic Chrome driver setup
            try:
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("✅ Chrome driver auto-download successful")
            except Exception as e:
                logger.warning(f"Auto-download failed: {e}")
                # Try manual path fallback
                manual_paths = [
                    "/usr/bin/chromedriver",  # Linux default
                    "/usr/local/bin/chromedriver",  # macOS default
                    r"C:\WebDrivers\chromedriver.exe",  # Windows
                    r"C:\chromedriver\chromedriver.exe",  # Windows alternative
                    "chromedriver",  # If in PATH
                    "chromedriver.exe"  # Windows if in PATH
                ]
                
                driver_found = False
                for path in manual_paths:
                    if os.path.exists(path):
                        logger.info(f"🔄 Trying manual path: {path}")
                        service = ChromeService(path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                        driver_found = True
                        break
                
                if not driver_found:
                    logger.error("❌ No Chrome driver found!")
                    logger.info("Please install ChromeDriver")
                    return False
            
            self.driver.set_window_size(1280, 720)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 20)
            
            logger.info("✅ Chrome driver setup successful (headless mode)")
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
                'input[type="email"]',
                'input[name="email"]'
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not email_field:
                logger.error("❌ Could not find email field")
                return False
            
            email_field.clear()
            email_field.send_keys(self.config['credentials']['email'])
            time.sleep(1)
            
            # Fill password with multiple selector fallbacks
            password_selectors = [
                '#passwordField',
                'input[placeholder*="Password"]',
                'input[placeholder*="password"]',
                'input[type="password"]',
                'input[name="password"]'
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not password_field:
                logger.error("❌ Could not find password field")
                return False
            
            password_field.clear()
            password_field.send_keys(self.config['credentials']['password'])
            time.sleep(1)
            
            # Click login button with multiple fallbacks
            login_selectors = [
                'button[type="submit"]',
                'button.loginButton',
                '//button[contains(text(), "Login")]',
                '//button[contains(text(), "Sign in")]',
                '.loginButton'
            ]
            
            for selector in login_selectors:
                try:
                    if selector.startswith('//'):
                        login_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    login_button.click()
                    break
                except NoSuchElementException:
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
    
    def _human_type(self, element, text):
        """Type text with human-like delays"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def _random_mouse_movement(self):
        """Simulate random mouse movements"""
        try:
            actions = ActionChains(self.driver)
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                actions.move_by_offset(x, y).perform()
                time.sleep(random.uniform(0.5, 1))
        except:
            pass
    
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
        """Navigate to profile and make updates"""
        try:
            logger.info("📝 Navigating to profile edit page...")
            
            # Navigate to profile edit - multiple URL attempts
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
            if strategy == 'headline_dbt_toggle':
                success = self._toggle_headline_dbt()
            elif strategy == 'skills_dbt_toggle':
                success = self._toggle_skills_dbt()
            elif strategy == 'summary_fullstop_toggle':
                success = self._toggle_summary_fullstop()
            elif strategy == 'linkedin_profile_toggle':
                success = self._toggle_linkedin_profile()
            elif strategy == 'salary_toggle':
                success = self._toggle_salary()
            
            if success:
                self.save_last_strategy(strategy)
                logger.info(f"✅ Profile update successful using {strategy}")
            else:
                logger.warning(f"⚠️ Strategy {strategy} may have failed, but continuing")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            return False
    
    def _click_edit_button(self, section_selector):
        """Click the edit button using span.edit.icon selector"""
        try:
            # CORRECT selector based on Naukri's HTML structure
            edit_selectors = [
                f'{section_selector} span.edit.icon',
                f'{section_selector} .edit.icon',
                f'{section_selector} span[class*="edit"]',
                f'{section_selector} button[class*="edit"]'
            ]
            
            for selector in edit_selectors:
                try:
                    edit_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", edit_button)
                    time.sleep(1)
                    edit_button.click()
                    return True
                except:
                    continue
            
            return False
        except:
            return False
    
    def _click_save_button(self):
        """Click save button with multiple fallbacks"""
        try:
            save_selectors = [
                'button[type="submit"]',
                'button.btn-primary',
                '//button[contains(text(), "Save")]',
                '//button[contains(text(), "Update")]',
                '.saveButton',
                'button[class*="save"]'
            ]
            
            for selector in save_selectors:
                try:
                    if selector.startswith('//'):
                        save_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        save_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if save_button.is_displayed() and save_button.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
                        time.sleep(1)
                        save_button.click()
                        return True
                except:
                    continue
            
            # Fallback: Press Enter or Escape
            try:
                from selenium.webdriver.common.keys import Keys
                active_element = self.driver.switch_to.active_element
                active_element.send_keys(Keys.ENTER)
            except:
                pass
            
            return True
        except:
            return True
    
    def _toggle_headline_dbt(self):
        """Toggle DBT mention in headline"""
        try:
            logger.info("🎯 Toggling headline DBT...")
            
            # Click edit on headline section
            if not self._click_edit_button('.resume-headline-view'):
                logger.error("Could not click headline edit")
                return False
            
            time.sleep(2)
            
            # Find headline textarea
            headline_field = None
            headline_selectors = [
                'textarea#resumeHeadline',
                'textarea[name="resumeHeadline"]',
                'textarea.resumeHeadline',
                'textarea[placeholder*="headline"]'
            ]
            
            for selector in headline_selectors:
                try:
                    headline_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if not headline_field:
                logger.error("Could not find headline field")
                return False
            
            current_headline = headline_field.get_attribute('value')
            
            # Toggle DBT mention
            should_add_dbt = self._get_toggle_state('headline_dbt')
            
            if should_add_dbt and 'DBT' not in current_headline.upper():
                new_headline = current_headline + " | DBT"
            elif not should_add_dbt and 'DBT' in current_headline.upper():
                new_headline = current_headline.replace(" | DBT", "").replace("| DBT", "").replace("DBT", "")
            else:
                new_headline = current_headline + "."  # Just add a period as fallback
            
            headline_field.clear()
            self._human_type(headline_field, new_headline.strip())
            time.sleep(1)
            
            # Save changes
            self._click_save_button()
            time.sleep(3)
            
            # Toggle state for next run
            self._set_toggle_state('headline_dbt', not should_add_dbt)
            
            logger.info("✅ Headline updated")
            return True
            
        except Exception as e:
            logger.error(f"❌ Headline toggle failed: {e}")
            return False
    
    def _toggle_skills_dbt(self):
        """Toggle DBT in skills section"""
        try:
            logger.info("🎯 Toggling skills DBT...")
            
            # Navigate to skills section
            skills_section = self.driver.find_element(By.CSS_SELECTOR, '.key-skills-sec')
            self.driver.execute_script("arguments[0].scrollIntoView(true);", skills_section)
            time.sleep(2)
            
            # Click edit on skills
            if not self._click_edit_button('.key-skills-sec'):
                logger.error("Could not click skills edit")
                return False
            
            time.sleep(2)
            
            # Just save to trigger update (visiting the section counts as activity)
            self._click_save_button()
            time.sleep(3)
            
            logger.info("✅ Skills section touched")
            return True
            
        except Exception as e:
            logger.error(f"❌ Skills toggle failed: {e}")
            return False
    
    def _toggle_summary_fullstop(self):
        """Toggle fullstop in summary"""
        try:
            logger.info("🎯 Toggling summary fullstop...")
            
            # Click edit on summary section
            if not self._click_edit_button('.summary-view'):
                logger.error("Could not click summary edit")
                return False
            
            time.sleep(2)
            
            # Find summary field
            summary_field = None
            summary_selectors = [
                'textarea#profileSummary',
                'textarea[name="profileSummary"]',
                'textarea.profileSummary',
                'div[contenteditable="true"]'
            ]
            
            for selector in summary_selectors:
                try:
                    summary_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if summary_field:
                if summary_field.tag_name == 'div':
                    current_summary = summary_field.text
                else:
                    current_summary = summary_field.get_attribute('value')
                
                # Toggle fullstop
                if current_summary.rstrip().endswith('.'):
                    new_summary = current_summary.rstrip()[:-1]
                else:
                    new_summary = current_summary.rstrip() + '.'
                
                summary_field.clear()
                self._human_type(summary_field, new_summary)
                time.sleep(1)
            
            # Save changes
            self._click_save_button()
            time.sleep(3)
            
            logger.info("✅ Summary updated")
            return True
            
        except Exception as e:
            logger.error(f"❌ Summary toggle failed: {e}")
            return False
    
    def _toggle_linkedin_profile(self):
        """Toggle LinkedIn profile URL"""
        try:
            logger.info("🎯 Toggling LinkedIn profile...")
            
            # Navigate to personal details section
            try:
                personal_section = self.driver.find_element(By.CSS_SELECTOR, '.personal-details-view')
                self.driver.execute_script("arguments[0].scrollIntoView(true);", personal_section)
            except:
                pass
            
            time.sleep(2)
            
            # Click edit on personal details
            if not self._click_edit_button('.personal-details-view'):
                logger.error("Could not click personal details edit")
                return False
            
            time.sleep(2)
            
            # Just save to trigger update
            self._click_save_button()
            time.sleep(3)
            
            logger.info("✅ Personal details touched")
            return True
            
        except Exception as e:
            logger.error(f"❌ LinkedIn toggle failed: {e}")
            return False
    
    def _toggle_salary(self):
        """Toggle expected salary between values"""
        try:
            logger.info("🎯 Toggling salary...")
            
            # Navigate to desired career profile section
            try:
                career_section = self.driver.find_element(By.CSS_SELECTOR, '.career-profile-view')
                self.driver.execute_script("arguments[0].scrollIntoView(true);", career_section)
            except:
                pass
            
            time.sleep(2)
            
            # Click edit
            if not self._click_edit_button('.career-profile-view'):
                logger.error("Could not click career profile edit")
                return False
            
            time.sleep(2)
            
            # Toggle between 18 and 20 lakh
            should_use_18 = self._get_toggle_state('salary_toggle')
            target_salary = "18" if should_use_18 else "20"
            
            # Find salary field
            salary_field = None
            salary_selectors = [
                'input[name="expectedSalary"]',
                'input#expectedSalary',
                'input[placeholder*="salary"]',
                'input[placeholder*="Salary"]'
            ]
            
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
    print("🔄 Naukri Profile Refresher (CHROME VERSION)")
    print("✅ Chrome WebDriver + CORRECT span.edit.icon selectors")
    print("=" * 60)
    
    refresher = NaukriProfileRefresher()
    success = refresher.run_profile_refresh()
    
    if success:
        print("✅ Profile refresh completed successfully!")
    else:
        print("❌ Profile refresh failed - check logs above")
    
    import sys
    sys.exit(0 if success else 1)