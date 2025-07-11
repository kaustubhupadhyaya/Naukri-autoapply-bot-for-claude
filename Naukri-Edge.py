import pandas as pd
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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

class NaukriBot:
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.applied_list = {'passed': [], 'failed': []}
        
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
                "email": "your_email@example.com",
                "password": "your_password"
            },
            "personal_info": {
                "firstname": "Your_FirstName",
                "lastname": "Your_LastName"
            },
            "job_search": {
                "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer"],
                "location": "Bengaluru, Karnataka, India",
                "max_applications": 50,
                "pages_per_keyword": 3
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 10,
                "page_load_timeout": 30
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Default config created at {config_file}. Please update with your details.")
    
    def setup_driver(self):
        """Setup Edge WebDriver with optimal settings"""
        try:
            options = webdriver.EdgeOptions()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            service = EdgeService(executable_path=self.config['webdriver']['edge_driver_path'])
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            
            logger.info("WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            return False
    
    def login(self):
        """Login to Naukri with better error handling"""
        try:
            self.driver.get('https://login.naukri.com/')
            
            # Wait for and fill username
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'usernameField'))
            )
            username_field.clear()
            username_field.send_keys(self.config['credentials']['email'])
            
            # Wait for and fill password
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'passwordField'))
            )
            password_field.clear()
            password_field.send_keys(self.config['credentials']['password'])
            password_field.send_keys(Keys.ENTER)
            
            # Wait for successful login (check for profile or dashboard element)
            try:
                self.wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, 'nI-gNb-drawer__icon')),
                        EC.presence_of_element_located((By.CLASS_NAME, 'view-profile-wrapper'))
                    )
                )
                logger.info("Login successful")
                return True
            except TimeoutException:
                logger.error("Login failed - timeout waiting for dashboard")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def scrape_job_links(self):
        """Scrape job links with improved error handling"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        for keyword in keywords:
            logger.info(f"Scraping jobs for keyword: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                try:
                    # Build URL
                    if location:
                        url = f"https://www.naukri.com/{keyword.lower().replace(' ', '-')}-jobs-in-{location.lower().replace(' ', '-').replace(',', '')}-{page}"
                    else:
                        url = f"https://www.naukri.com/{keyword.lower().replace(' ', '-')}-jobs-{page}"
                    
                    logger.info(f"Scraping page: {url}")
                    self.driver.get(url)
                    
                    # Wait for job listings to load
                    try:
                        self.wait.until(
                            EC.presence_of_element_located((By.CLASS_NAME, 'jobTuple'))
                        )
                    except TimeoutException:
                        logger.warning(f"No jobs found on page {page} for keyword '{keyword}'")
                        continue
                    
                    # Parse job links
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    job_articles = soup.find_all('article', class_='jobTuple')
                    
                    page_links = []
                    for article in job_articles:
                        try:
                            link_elem = article.find('a', class_='title')
                            if link_elem and link_elem.get('href'):
                                href = link_elem.get('href')
                                if href.startswith('/'):
                                    href = 'https://www.naukri.com' + href
                                page_links.append(href)
                        except Exception as e:
                            logger.warning(f"Error parsing job link: {e}")
                            continue
                    
                    self.joblinks.extend(page_links)
                    logger.info(f"Found {len(page_links)} jobs on page {page}")
                    
                    time.sleep(2)  # Respectful scraping
                    
                except Exception as e:
                    logger.error(f"Error scraping page {page} for keyword '{keyword}': {e}")
                    continue
        
        logger.info(f"Total job links scraped: {len(self.joblinks)}")
        return len(self.joblinks) > 0
    
    def apply_to_jobs(self):
        """Apply to jobs with improved error handling"""
        max_applications = self.config['job_search']['max_applications']
        
        for i, job_link in enumerate(self.joblinks):
            if self.applied >= max_applications:
                logger.info(f"Reached maximum applications limit: {max_applications}")
                break
            
            try:
                logger.info(f"Applying to job {i+1}/{len(self.joblinks)}: {job_link}")
                self.driver.get(job_link)
                
                # Wait for page to load
                time.sleep(3)
                
                # Look for apply button with multiple selectors
                apply_button = None
                apply_selectors = [
                    (By.XPATH, "//button[contains(text(), 'Apply')]"),
                    (By.XPATH, "//a[contains(text(), 'Apply')]"),
                    (By.CLASS_NAME, "apply-button"),
                    (By.ID, "apply-button")
                ]
                
                for selector in apply_selectors:
                    try:
                        apply_button = self.wait.until(
                            EC.element_to_be_clickable(selector)
                        )
                        break
                    except TimeoutException:
                        continue
                
                if not apply_button:
                    logger.warning(f"No apply button found for: {job_link}")
                    self.failed += 1
                    self.applied_list['failed'].append(job_link)
                    continue
                
                # Click apply button
                apply_button.click()
                time.sleep(2)
                
                # Handle additional form fields if present
                self.handle_application_form()
                
                self.applied += 1
                self.applied_list['passed'].append(job_link)
                logger.info(f"Successfully applied to job {i+1}. Total applied: {self.applied}")
                
                # Check for daily quota exceeded
                if self.check_daily_quota_exceeded():
                    logger.info("Daily quota exceeded. Stopping applications.")
                    break
                
            except Exception as e:
                logger.error(f"Error applying to job {job_link}: {e}")
                self.failed += 1
                self.applied_list['failed'].append(job_link)
                continue
            
            time.sleep(3)  # Respectful automation
    
    def handle_application_form(self):
        """Handle additional form fields during application"""
        try:
            # Check for first name field
            try:
                firstname_field = self.driver.find_element(By.ID, 'CUSTOM-FIRSTNAME')
                firstname_field.clear()
                firstname_field.send_keys(self.config['personal_info']['firstname'])
            except NoSuchElementException:
                pass
            
            # Check for last name field
            try:
                lastname_field = self.driver.find_element(By.ID, 'CUSTOM-LASTNAME')
                lastname_field.clear()
                lastname_field.send_keys(self.config['personal_info']['lastname'])
            except NoSuchElementException:
                pass
            
            # Submit form if submit button exists
            try:
                submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]")
                submit_button.click()
                time.sleep(2)
            except NoSuchElementException:
                pass
                
        except Exception as e:
            logger.warning(f"Error handling application form: {e}")
    
    def check_daily_quota_exceeded(self):
        """Check if daily application quota is exceeded"""
        try:
            quota_message = self.driver.find_element(
                By.XPATH, 
                "//*[contains(text(), 'daily quota') or contains(text(), 'limit reached')]"
            )
            return True
        except NoSuchElementException:
            return False
    
    def save_results(self):
        """Save application results to CSV"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = f"naukri_applied_{timestamp}.csv"
            
            # Prepare data for CSV
            max_len = max(len(self.applied_list['passed']), len(self.applied_list['failed']))
            
            data = {
                'passed': self.applied_list['passed'] + [''] * (max_len - len(self.applied_list['passed'])),
                'failed': self.applied_list['failed'] + [''] * (max_len - len(self.applied_list['failed']))
            }
            
            df = pd.DataFrame(data)
            df.to_csv(csv_file, index=False)
            
            logger.info(f"Results saved to {csv_file}")
            logger.info(f"Total applied: {self.applied}, Total failed: {self.failed}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def run(self):
        """Main execution method"""
        try:
            logger.info("Starting Naukri job application bot")
            
            # Setup WebDriver
            if not self.setup_driver():
                return False
            
            # Login
            if not self.login():
                return False
            
            # Scrape job links
            if not self.scrape_job_links():
                logger.error("No job links found. Exiting.")
                return False
            
            # Apply to jobs
            self.apply_to_jobs()
            
            # Save results
            self.save_results()
            
            logger.info("Bot execution completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Bot execution failed: {e}")
            return False
        
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

if __name__ == "__main__":
    bot = NaukriBot()
    bot.run()