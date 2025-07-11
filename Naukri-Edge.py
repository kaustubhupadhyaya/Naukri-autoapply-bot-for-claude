import pandas as pd
import time
import json
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
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

class ImprovedNaukriBot:
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.applied_list = {'passed': [], 'failed': []}
        
        # Multiple possible selectors for job cards (current as of 2025)
        self.job_card_selectors = [
            '.jobTuple',
            '.job-card',
            '.job-tuple',
            '.srp-jobtuple-wrapper',
            '.job-listing',
            '[data-job-id]',
            '.job-item'
        ]
        
        # Multiple possible selectors for job titles/links
        self.job_link_selectors = [
            'a.title',
            'a[title]',
            '.job-title a',
            '.title a',
            'h3 a',
            'h2 a',
            '.job-title-link'
        ]
        
        # Apply button selectors
        self.apply_button_selectors = [
            "//button[contains(text(), 'Apply')]",
            "//a[contains(text(), 'Apply')]",
            "//span[contains(text(), 'Apply')]",
            "//*[@id='apply-button']",
            "//*[contains(@class, 'apply-button')]",
            "//*[contains(@class, 'btn-apply')]",
            "//button[contains(@class, 'naukri-apply')]",
            "//div[contains(@class, 'apply-button')]//button",
            "//div[contains(text(), 'Apply')]"
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
                "email": "your_email@example.com",
                "password": "your_password"
            },
            "personal_info": {
                "firstname": "Kaustubh",
                "lastname": "Upadhyaya"
            },
            "job_search": {
                "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer"],
                "location": "bengaluru",  # Simplified location
                "max_applications": 50,
                "pages_per_keyword": 3
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 15,
                "page_load_timeout": 45
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Default config created at {config_file}. Please update with your details.")
    
    def setup_driver(self):
        """Setup Edge WebDriver with anti-detection measures"""
        try:
            options = webdriver.EdgeOptions()
            
            # Enhanced anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-gpu')
            options.add_argument('--remote-debugging-port=9222')
            
            # Randomize user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
            ]
            options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            service = EdgeService(executable_path=self.config['webdriver']['edge_driver_path'])
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Execute scripts to remove automation indicators
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
    
    def random_delay(self, min_delay=1, max_delay=4):
        """Add random delay to simulate human behavior"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def login(self):
        """Login to Naukri with enhanced error handling"""
        try:
            self.driver.get('https://www.naukri.com/nlogin/login')
            self.random_delay(3, 6)
            
            # Wait for and fill username
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'usernameField'))
            )
            username_field.clear()
            # Type slowly to mimic human behavior
            for char in self.config['credentials']['email']:
                username_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            self.random_delay(1, 2)
            
            # Wait for and fill password
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'passwordField'))
            )
            password_field.clear()
            # Type slowly to mimic human behavior
            for char in self.config['credentials']['password']:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            self.random_delay(1, 2)
            
            # Click login button instead of pressing Enter
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for successful login
            try:
                self.wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, 'nI-gNb-drawer__icon')),
                        EC.presence_of_element_located((By.CLASS_NAME, 'view-profile-wrapper')),
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'user-name')]")),
                        EC.url_contains('mnjuser')
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
        """Build proper search URL for Naukri"""
        base_url = "https://www.naukri.com"
        
        # Clean keyword and location
        clean_keyword = keyword.lower().replace(' ', '-').replace(',', '')
        
        if location:
            clean_location = location.lower().replace(' ', '-').replace(',', '')
            url = f"{base_url}/{clean_keyword}-jobs-in-{clean_location}-{page}"
        else:
            url = f"{base_url}/{clean_keyword}-jobs-{page}"
        
        return url
    
    def wait_for_jobs_to_load(self):
        """Wait for job listings to load using multiple strategies"""
        strategies = [
            # Strategy 1: Wait for any job card selector
            lambda: self.wait.until(
                EC.any_of(*[EC.presence_of_element_located((By.CSS_SELECTOR, selector)) 
                           for selector in self.job_card_selectors])
            ),
            # Strategy 2: Wait for specific job elements
            lambda: self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'job')]"))
            ),
            # Strategy 3: Wait for search results container
            lambda: self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'list'))
            )
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                strategy()
                logger.info(f"Jobs loaded using strategy {i+1}")
                return True
            except TimeoutException:
                continue
        
        return False
    
    def extract_job_links_from_page(self):
        """Extract job links using multiple parsing methods"""
        job_links = []
        
        # Wait for page to fully load
        self.random_delay(3, 6)
        
        # Try multiple methods to find job links
        methods = [
            self.extract_with_beautiful_soup,
            self.extract_with_selenium_direct,
            self.extract_with_xpath_search
        ]
        
        for method in methods:
            try:
                links = method()
                if links:
                    job_links.extend(links)
                    logger.info(f"Found {len(links)} jobs using {method.__name__}")
                    break
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        # Remove duplicates
        job_links = list(set(job_links))
        return job_links
    
    def extract_with_beautiful_soup(self):
        """Extract using BeautifulSoup"""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        job_links = []
        
        # Try different selectors
        for job_selector in self.job_card_selectors:
            job_articles = soup.select(job_selector)
            if job_articles:
                for article in job_articles:
                    for link_selector in self.job_link_selectors:
                        link_elem = article.select_one(link_selector)
                        if link_elem and link_elem.get('href'):
                            href = link_elem.get('href')
                            if href.startswith('/'):
                                href = 'https://www.naukri.com' + href
                            job_links.append(href)
                            break
                break
        
        return job_links
    
    def extract_with_selenium_direct(self):
        """Extract using Selenium directly"""
        job_links = []
        
        # Try to find job links directly
        link_selectors = [
            "//a[contains(@href, '/job-listings/')]",
            "//a[contains(@href, 'naukri.com/job')]",
            "//div[contains(@class, 'job')]//a[@href]",
            "//h2//a[@href]",
            "//h3//a[@href]"
        ]
        
        for selector in link_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for element in elements:
                    href = element.get_attribute('href')
                    if href and ('job' in href.lower() or 'listing' in href.lower()):
                        job_links.append(href)
                if job_links:
                    break
            except Exception as e:
                continue
        
        return job_links
    
    def extract_with_xpath_search(self):
        """Extract using comprehensive XPath search"""
        job_links = []
        
        # Comprehensive XPath patterns
        xpath_patterns = [
            "//article//a[@href]",
            "//div[contains(@class, 'tuple')]//a[@href]",
            "//div[contains(@class, 'card')]//a[@href]",
            "//*[@data-job-id]//a[@href]",
            "//div[contains(@class, 'listing')]//a[@href]"
        ]
        
        for pattern in xpath_patterns:
            try:
                elements = self.driver.find_elements(By.XPATH, pattern)
                for element in elements:
                    href = element.get_attribute('href')
                    if href and any(keyword in href.lower() for keyword in ['job', 'listing', 'detail']):
                        job_links.append(href)
                if job_links:
                    break
            except Exception:
                continue
        
        return job_links
    
    def scrape_job_links(self):
        """Enhanced job link scraping"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        for keyword in keywords:
            logger.info(f"Scraping jobs for keyword: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                try:
                    url = self.build_search_url(keyword, location, page)
                    logger.info(f"Scraping page: {url}")
                    
                    self.driver.get(url)
                    self.random_delay(4, 8)
                    
                    # Wait for jobs to load
                    if not self.wait_for_jobs_to_load():
                        logger.warning(f"No jobs loaded on page {page} for keyword '{keyword}'")
                        continue
                    
                    # Scroll to load more content
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    self.random_delay(2, 4)
                    
                    # Extract job links
                    page_links = self.extract_job_links_from_page()
                    
                    if page_links:
                        self.joblinks.extend(page_links)
                        logger.info(f"Found {len(page_links)} jobs on page {page}")
                    else:
                        logger.warning(f"No job links extracted from page {page} for keyword '{keyword}'")
                    
                    self.random_delay(2, 5)
                    
                except Exception as e:
                    logger.error(f"Error scraping page {page} for keyword '{keyword}': {e}")
                    continue
        
        logger.info(f"Total job links scraped: {len(self.joblinks)}")
        return len(self.joblinks) > 0
    
    def find_apply_button(self):
        """Find apply button using multiple strategies"""
        for selector in self.apply_button_selectors:
            try:
                element = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                return element
            except TimeoutException:
                continue
        return None
    
    def apply_to_jobs(self):
        """Enhanced job application process"""
        max_applications = self.config['job_search']['max_applications']
        
        for i, job_link in enumerate(self.joblinks):
            if self.applied >= max_applications:
                logger.info(f"Reached maximum applications limit: {max_applications}")
                break
            
            try:
                logger.info(f"Applying to job {i+1}/{len(self.joblinks)}: {job_link}")
                self.driver.get(job_link)
                self.random_delay(4, 8)
                
                # Find and click apply button
                apply_button = self.find_apply_button()
                
                if not apply_button:
                    logger.warning(f"No apply button found for: {job_link}")
                    self.failed += 1
                    self.applied_list['failed'].append(job_link)
                    continue
                
                # Scroll to button and click
                self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                self.random_delay(1, 2)
                
                try:
                    apply_button.click()
                except ElementClickInterceptedException:
                    # Try JavaScript click if regular click fails
                    self.driver.execute_script("arguments[0].click();", apply_button)
                
                self.random_delay(2, 4)
                
                # Handle additional form fields
                self.handle_application_form()
                
                self.applied += 1
                self.applied_list['passed'].append(job_link)
                logger.info(f"Successfully applied to job {i+1}. Total applied: {self.applied}")
                
                # Check for daily quota
                if self.check_daily_quota_exceeded():
                    logger.info("Daily quota exceeded. Stopping applications.")
                    break
                
            except Exception as e:
                logger.error(f"Error applying to job {job_link}: {e}")
                self.failed += 1
                self.applied_list['failed'].append(job_link)
                continue
            
            self.random_delay(3, 7)
    
    def handle_application_form(self):
        """Enhanced form handling"""
        try:
            form_fields = [
                ('CUSTOM-FIRSTNAME', self.config['personal_info']['firstname']),
                ('firstname', self.config['personal_info']['firstname']),
                ('CUSTOM-LASTNAME', self.config['personal_info']['lastname']),
                ('lastname', self.config['personal_info']['lastname'])
            ]
            
            for field_id, value in form_fields:
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    field.clear()
                    field.send_keys(value)
                    self.random_delay(0.5, 1)
                except NoSuchElementException:
                    continue
            
            # Submit form
            submit_selectors = [
                "//button[contains(text(), 'Submit')]",
                "//button[contains(text(), 'Apply')]",
                "//input[@type='submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.XPATH, selector)
                    submit_button.click()
                    self.random_delay(1, 2)
                    break
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error handling application form: {e}")
    
    def check_daily_quota_exceeded(self):
        """Check for quota exceeded messages"""
        quota_indicators = [
            "daily quota",
            "limit reached",
            "maximum applications",
            "quota exceeded",
            "limit exceeded"
        ]
        
        try:
            page_text = self.driver.page_source.lower()
            return any(indicator in page_text for indicator in quota_indicators)
        except Exception:
            return False
    
    def save_results(self):
        """Save application results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = f"naukri_applied_{timestamp}.csv"
            
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
            logger.info("Starting Improved Naukri job application bot")
            
            if not self.setup_driver():
                return False
            
            if not self.login():
                return False
            
            if not self.scrape_job_links():
                logger.error("No job links found. Exiting.")
                return False
            
            self.apply_to_jobs()
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
    bot = ImprovedNaukriBot()
    bot.run()