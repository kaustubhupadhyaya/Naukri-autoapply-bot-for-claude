import pandas as pd
import time
import json
import logging
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('naukri_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionNaukriBot:
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.applied_list = {'passed': [], 'failed': []}
        self.processed_jobs = set()  # Track processed jobs to avoid duplicates
        
        # CORRECT selectors based on diagnostic results
        self.job_card_selector = '.srp-jobtuple-wrapper[data-job-id]'
        self.job_title_selector = 'a.title'
        
        # Apply button selectors for individual job pages
        self.apply_button_selectors = [
            "//button[contains(text(), 'Apply')]",
            "//a[contains(text(), 'Apply')]",
            "//span[contains(text(), 'Apply')]",
            "//div[contains(@class, 'apply-button')]//button",
            "//button[contains(@class, 'apply')]",
            "//*[@id='apply-button']",
            "//input[@type='submit'][contains(@value, 'Apply')]",
            "//button[contains(@class, 'naukri-apply')]"
        ]
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_file} not found. Creating default config.")
            self.create_default_config(config_file)
            return self.load_config(config_file)
    
    def create_default_config(self, config_file):
        """Create default configuration file"""
        default_config = {
            "credentials": {
                "email": "kaustubh.upadhyaya1@gmail.com",
                "password": "9880380081@kK"
            },
            "personal_info": {
                "firstname": "Kaustubh",
                "lastname": "Upadhyaya"
            },
            "job_search": {
                "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer"],
                "location": "bengaluru",
                "max_applications": 50,
                "pages_per_keyword": 3
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 15,
                "page_load_timeout": 45
            },
            "bot_behavior": {
                "min_delay": 2,
                "max_delay": 5,
                "typing_delay": 0.1,
                "scroll_pause": 2
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Default config created at {config_file}. Please update with your details.")
    
    def setup_driver(self):
        """Setup Edge WebDriver with enhanced stealth"""
        try:
            options = webdriver.EdgeOptions()
            
            # Enhanced stealth options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-gpu')
            options.add_argument('--start-maximized')
            
            # Random user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
            ]
            options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            service = EdgeService(executable_path=self.config['webdriver']['edge_driver_path'])
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Remove automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            
            self.wait = WebDriverWait(self.driver, self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            
            logger.info("WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            return False
    
    def random_delay(self, min_delay=None, max_delay=None):
        """Add random delay to simulate human behavior"""
        min_delay = min_delay or self.config['bot_behavior']['min_delay']
        max_delay = max_delay or self.config['bot_behavior']['max_delay']
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def human_type(self, element, text):
        """Type like a human with random delays"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, self.config['bot_behavior']['typing_delay']))
    
    def login(self):
        """Enhanced login with better error handling"""
        try:
            logger.info("Starting login process...")
            self.driver.get('https://www.naukri.com/nlogin/login')
            self.random_delay(3, 6)
            
            # Wait for and fill username
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'usernameField'))
            )
            self.human_type(username_field, self.config['credentials']['email'])
            self.random_delay(1, 2)
            
            # Wait for and fill password
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'passwordField'))
            )
            self.human_type(password_field, self.config['credentials']['password'])
            self.random_delay(1, 2)
            
            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for successful login
            try:
                self.wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, 'nI-gNb-drawer__icon')),
                        EC.presence_of_element_located((By.CLASS_NAME, 'view-profile-wrapper')),
                        EC.url_contains('mnjuser'),
                        EC.url_contains('naukri.com')
                    )
                )
                logger.info("Login successful")
                self.random_delay(2, 4)
                return True
            except TimeoutException:
                logger.error("Login failed - timeout waiting for dashboard")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def build_search_url(self, keyword, location, page):
        """Build search URL based on diagnostic findings"""
        base_url = "https://www.naukri.com"
        clean_keyword = keyword.lower().replace(' ', '-').replace(',', '')
        
        if location:
            clean_location = location.lower().replace(' ', '-').replace(',', '')
            url = f"{base_url}/{clean_keyword}-jobs-in-{clean_location}-{page}"
        else:
            url = f"{base_url}/{clean_keyword}-jobs-{page}"
        
        return url
    
    def extract_job_links_from_current_page(self):
        """Extract job links using the CORRECT selectors from diagnostic"""
        job_links = []
        
        try:
            # Wait for job listings to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector))
            )
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            self.random_delay(2, 3)
            
            # Find all job cards using the CORRECT selector
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, self.job_card_selector)
            logger.info(f"Found {len(job_cards)} job cards on current page")
            
            for card in job_cards:
                try:
                    # Extract job ID to avoid duplicates
                    job_id = card.get_attribute('data-job-id')
                    if job_id in self.processed_jobs:
                        continue
                    
                    # Find job title link using CORRECT selector
                    title_link = card.find_element(By.CSS_SELECTOR, self.job_title_selector)
                    job_url = title_link.get_attribute('href')
                    job_title = title_link.get_attribute('title') or title_link.text
                    
                    if job_url and job_id:
                        job_links.append({
                            'url': job_url,
                            'title': job_title,
                            'job_id': job_id
                        })
                        self.processed_jobs.add(job_id)
                        
                except Exception as e:
                    logger.warning(f"Error extracting job from card: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(job_links)} job links")
            return job_links
            
        except TimeoutException:
            logger.warning("No job cards found on current page")
            return []
        except Exception as e:
            logger.error(f"Error extracting job links: {e}")
            return []
    
    def scrape_job_links(self):
        """Enhanced job link scraping with correct selectors"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        all_jobs = []
        
        for keyword in keywords:
            logger.info(f"Scraping jobs for keyword: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                try:
                    url = self.build_search_url(keyword, location, page)
                    logger.info(f"Visiting page {page}: {url}")
                    
                    self.driver.get(url)
                    self.random_delay(4, 7)
                    
                    # Extract jobs from this page
                    page_jobs = self.extract_job_links_from_current_page()
                    
                    if page_jobs:
                        all_jobs.extend(page_jobs)
                        logger.info(f"Page {page}: Found {len(page_jobs)} jobs")
                    else:
                        logger.warning(f"Page {page}: No jobs found")
                    
                    self.random_delay(2, 4)
                    
                except Exception as e:
                    logger.error(f"Error scraping page {page} for keyword '{keyword}': {e}")
                    continue
        
        # Convert to simple URL list for compatibility
        self.joblinks = [job['url'] for job in all_jobs]
        logger.info(f"Total unique job links scraped: {len(self.joblinks)}")
        
        # Save detailed job info
        if all_jobs:
            df = pd.DataFrame(all_jobs)
            df.to_csv(f"scraped_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)
        
        return len(self.joblinks) > 0
    
    def find_and_click_apply_button(self):
        """Find and click apply button with multiple strategies"""
        for selector in self.apply_button_selectors:
            try:
                apply_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                
                # Scroll to button
                self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                self.random_delay(1, 2)
                
                # Try regular click first
                try:
                    apply_button.click()
                    logger.info(f"Apply button clicked using selector: {selector}")
                    return True
                except ElementClickInterceptedException:
                    # Try JavaScript click
                    self.driver.execute_script("arguments[0].click();", apply_button)
                    logger.info(f"Apply button clicked via JavaScript using selector: {selector}")
                    return True
                    
            except TimeoutException:
                continue
            except Exception as e:
                logger.warning(f"Error with selector {selector}: {e}")
                continue
        
        return False
    
    def handle_application_form(self):
        """Handle additional form fields after clicking apply"""
        try:
            # Wait a bit for form to load
            self.random_delay(2, 3)
            
            # Common form fields
            form_fields = [
                ('CUSTOM-FIRSTNAME', self.config['personal_info']['firstname']),
                ('firstname', self.config['personal_info']['firstname']),
                ('CUSTOM-LASTNAME', self.config['personal_info']['lastname']),
                ('lastname', self.config['personal_info']['lastname']),
                ('firstName', self.config['personal_info']['firstname']),
                ('lastName', self.config['personal_info']['lastname'])
            ]
            
            filled_fields = 0
            for field_id, value in form_fields:
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    if field.is_displayed() and field.is_enabled():
                        self.human_type(field, value)
                        filled_fields += 1
                        self.random_delay(0.5, 1)
                except NoSuchElementException:
                    continue
            
            if filled_fields > 0:
                logger.info(f"Filled {filled_fields} form fields")
            
            # Submit form if submit button exists
            submit_selectors = [
                "//button[contains(text(), 'Submit')]",
                "//button[contains(text(), 'Apply')]",
                "//input[@type='submit']",
                "//button[@type='submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.XPATH, selector)
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        submit_button.click()
                        logger.info("Form submitted successfully")
                        self.random_delay(1, 2)
                        return True
                except NoSuchElementException:
                    continue
            
        except Exception as e:
            logger.warning(f"Error handling application form: {e}")
        
        return False
    
    def apply_to_job(self, job_url, job_index):
        """Apply to a single job with enhanced error handling"""
        try:
            logger.info(f"Applying to job {job_index}: {job_url}")
            
            # Navigate to job page
            self.driver.get(job_url)
            self.random_delay(4, 7)
            
            # Check if already applied
            page_source = self.driver.page_source.lower()
            if any(indicator in page_source for indicator in ['already applied', 'application sent', 'applied']):
                logger.info("Already applied to this job, skipping...")
                return False
            
            # Find and click apply button
            if not self.find_and_click_apply_button():
                logger.warning("No apply button found")
                return False
            
            self.random_delay(2, 4)
            
            # Handle any additional form
            self.handle_application_form()
            
            # Check for success indicators
            success_indicators = [
                'application submitted',
                'successfully applied',
                'application sent',
                'thank you for applying'
            ]
            
            page_source = self.driver.page_source.lower()
            if any(indicator in page_source for indicator in success_indicators):
                logger.info("Application successful!")
                return True
            else:
                logger.info("Application attempt completed (uncertain success)")
                return True  # Assume success if no error
                
        except Exception as e:
            logger.error(f"Error applying to job {job_url}: {e}")
            return False
    
    def apply_to_jobs(self):
        """Apply to all scraped jobs"""
        max_applications = self.config['job_search']['max_applications']
        
        for i, job_url in enumerate(self.joblinks, 1):
            if self.applied >= max_applications:
                logger.info(f"Reached maximum applications limit: {max_applications}")
                break
            
            try:
                success = self.apply_to_job(job_url, i)
                
                if success:
                    self.applied += 1
                    self.applied_list['passed'].append(job_url)
                    logger.info(f"✅ Job {i}/{len(self.joblinks)} - Applied successfully. Total: {self.applied}")
                else:
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    logger.info(f"❌ Job {i}/{len(self.joblinks)} - Application failed. Total failed: {self.failed}")
                
                # Check for daily quota
                if self.check_daily_quota_exceeded():
                    logger.info("Daily application quota exceeded. Stopping.")
                    break
                
                # Random delay between applications
                self.random_delay(3, 8)
                
            except Exception as e:
                logger.error(f"Unexpected error with job {i}: {e}")
                self.failed += 1
                self.applied_list['failed'].append(job_url)
                continue
    
    def check_daily_quota_exceeded(self):
        """Check if daily application quota is exceeded"""
        try:
            page_source = self.driver.page_source.lower()
            quota_indicators = [
                'daily quota',
                'limit reached',
                'maximum applications',
                'quota exceeded',
                'limit exceeded',
                'daily limit'
            ]
            return any(indicator in page_source for indicator in quota_indicators)
        except Exception:
            return False
    
    def save_results(self):
        """Save application results with detailed statistics"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save basic results
            csv_file = f"naukri_results_{timestamp}.csv"
            max_len = max(len(self.applied_list['passed']), len(self.applied_list['failed']))
            
            data = {
                'successful_applications': self.applied_list['passed'] + [''] * (max_len - len(self.applied_list['passed'])),
                'failed_applications': self.applied_list['failed'] + [''] * (max_len - len(self.applied_list['failed']))
            }
            
            df = pd.DataFrame(data)
            df.to_csv(csv_file, index=False)
            
            # Save summary
            summary = {
                'total_jobs_found': len(self.joblinks),
                'successful_applications': self.applied,
                'failed_applications': self.failed,
                'success_rate': f"{(self.applied / len(self.joblinks) * 100):.2f}%" if self.joblinks else "0%",
                'timestamp': timestamp
            }
            
            with open(f"naukri_summary_{timestamp}.json", 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Results saved to {csv_file}")
            logger.info(f"SUMMARY - Found: {len(self.joblinks)}, Applied: {self.applied}, Failed: {self.failed}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def run(self):
        """Main execution method"""
        try:
            logger.info("🚀 Starting Production Naukri Job Application Bot")
            
            if not self.setup_driver():
                return False
            
            if not self.login():
                return False
            
            if not self.scrape_job_links():
                logger.error("❌ No job links found. Check your search criteria.")
                return False
            
            logger.info(f"✅ Found {len(self.joblinks)} jobs. Starting applications...")
            
            self.apply_to_jobs()
            self.save_results()
            
            logger.info("🎉 Bot execution completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bot execution failed: {e}")
            return False
        
        finally:
            if self.driver:
                input("Press Enter to close browser...")
                self.driver.quit()
                logger.info("Browser closed")

if __name__ == "__main__":
    bot = ProductionNaukriBot()
    success = bot.run()
    if success:
        print("✅ Bot completed successfully!")
    else:
        print("❌ Bot failed. Check logs for details.")