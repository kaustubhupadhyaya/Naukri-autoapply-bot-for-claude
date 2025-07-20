import pandas as pd
import time
import json
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('naukri_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntelligentNaukriBot:
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.skipped = 0
        self.applied_list = {'passed': [], 'failed': [], 'skipped': []}
        self.processed_jobs = set()
        
        # Initialize simple job tracking
        self.init_job_database()
        
        # VERIFIED selectors from your diagnostic results
        self.job_card_selector = '.srp-jobtuple-wrapper[data-job-id]'
        self.job_title_selector = 'a.title'
        
        # Apply button selectors for individual job pages
        self.apply_button_selectors = [
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//button[contains(@class, 'apply')]",
            "//div[contains(@class, 'apply-button')]//button",
            "//*[@id='apply-button']"
        ]
        
        logger.info("Bot initialized successfully")
    
    def load_config(self, config_file):
        """Load configuration with smart defaults"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                logger.info("Configuration loaded successfully")
                return config
        except FileNotFoundError:
            logger.info("Config file not found. Creating default configuration...")
            default_config = {
                "credentials": {
                    "email": "kaustubh.upadhyaya1@gmail.com",
                    "password": "9880380081@kK"
                },
                "personal_info": {
                    "firstname": "Kaustubh",
                    "lastname": "Upadhyaya",
                    "phone": "9880380081"
                },
                "job_search": {
                    "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer"],
                    "location": "bengaluru",
                    "max_applications_per_session": 20,
                    "pages_per_keyword": 3,
                    "preferred_companies": ["Microsoft", "Google", "Amazon", "Netflix"],
                    "avoid_companies": ["TCS", "Infosys", "Wipro"]
                },
                "webdriver": {
                    "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                    "implicit_wait": 15,
                    "page_load_timeout": 45
                },
                "bot_behavior": {
                    "min_delay": 3,
                    "max_delay": 7,
                    "typing_delay": 0.1
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            logger.info(f"Default config created at {config_file}")
            return default_config
    
    def init_job_database(self):
        """Initialize simple job tracking database"""
        try:
            self.db_conn = sqlite3.connect('naukri_jobs.db')
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT,
                    job_title TEXT,
                    application_date TIMESTAMP,
                    status TEXT
                )
            ''')
            self.db_conn.commit()
            logger.info("Job database initialized")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            self.db_conn = None
    
    def setup_driver(self):
        """Setup Edge WebDriver with auto-download"""
        try:
            logger.info("Setting up browser...")
            
            options = webdriver.EdgeOptions()
            
            # Browser options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            if self.config.get('webdriver', {}).get('headless', False):
                options.add_argument('--headless')
            
            # Auto-download and setup WebDriver
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Configure driver
            self.driver.implicitly_wait(self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            
            # Anti-detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("✅ Browser setup successful")
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            raise
    
    def smart_delay(self, min_delay=None, max_delay=None):
        """Smart delay with random variation"""
        try:
            min_delay = min_delay or self.config.get('bot_behavior', {}).get('min_delay', 3)
            max_delay = max_delay or self.config.get('bot_behavior', {}).get('max_delay', 7)
            
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
        except Exception:
            time.sleep(random.uniform(3, 7))
    
    def human_type(self, element, text):
        """Type like a human with random delays"""
        try:
            element.clear()
            typing_delay = self.config.get('bot_behavior', {}).get('typing_delay', 0.1)
            
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, typing_delay))
        except Exception:
            element.clear()
            element.send_keys(text)
            time.sleep(1)
    
    def login(self):
        """Enhanced login with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_retries}")
                self.driver.get('https://www.naukri.com/nlogin/login')
                self.smart_delay(3, 6)
                
                # Fill username
                username_field = self.wait.until(
                    EC.element_to_be_clickable((By.ID, 'usernameField'))
                )
                self.human_type(username_field, self.config['credentials']['email'])
                self.smart_delay(1, 2)
                
                # Fill password
                password_field = self.wait.until(
                    EC.element_to_be_clickable((By.ID, 'passwordField'))
                )
                self.human_type(password_field, self.config['credentials']['password'])
                self.smart_delay(1, 2)
                
                # Click login button
                login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                self.driver.execute_script("arguments[0].click();", login_button)
                
                # Wait for login success
                self.smart_delay(5, 8)
                
                # Check if login was successful
                success_indicators = [
                    'naukri.com' in self.driver.current_url and 'login' not in self.driver.current_url,
                    len(self.driver.find_elements(By.CLASS_NAME, 'nI-gNb-drawer__icon')) > 0,
                    len(self.driver.find_elements(By.CLASS_NAME, 'view-profile-wrapper')) > 0
                ]
                
                if any(success_indicators):
                    logger.info("Login successful!")
                    return True
                else:
                    logger.warning(f"Login attempt {attempt + 1} failed")
                    if attempt < max_retries - 1:
                        self.smart_delay(5, 10)
                        continue
                        
            except Exception as e:
                logger.error(f"Login attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    self.smart_delay(5, 10)
                    continue
        
        logger.error("All login attempts failed")
        return False
    
    def is_job_already_applied(self, job_id):
        """Check if we already applied to this job"""
        if not self.db_conn:
            return False
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applied_jobs WHERE job_id = ?", (job_id,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception:
            return False
    
    def save_job_application(self, job_data, status='applied'):
        """Save job application to database"""
        if not self.db_conn:
            return
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO applied_jobs 
                (job_id, job_url, job_title, application_date, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                job_data.get('job_id', ''),
                job_data.get('url', ''),
                job_data.get('title', ''),
                datetime.now(),
                status
            ))
            self.db_conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save job application: {e}")
    
    def analyze_job_quality(self, job_card_text):
        """Simple job quality analysis"""
        job_text = job_card_text.lower()
        score = 0
        
        # Preferred keywords
        preferred = ['remote', 'hybrid', 'senior', 'lead', 'full time']
        for keyword in preferred:
            if keyword in job_text:
                score += 5
        
        # Avoid keywords
        avoid = ['intern', 'trainee', 'fresher only']
        for keyword in avoid:
            if keyword in job_text:
                score -= 15
        
        # Company preferences
        preferred_companies = self.config.get('job_search', {}).get('preferred_companies', [])
        avoid_companies = self.config.get('job_search', {}).get('avoid_companies', [])
        
        for company in preferred_companies:
            if company.lower() in job_text:
                score += 10
        
        for company in avoid_companies:
            if company.lower() in job_text:
                score -= 20
        
        return score
    
    def extract_jobs_from_page(self):
        """Extract job information from current page using verified selectors"""
        jobs = []
        
        try:
            # Wait for job listings to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector))
            )
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            self.smart_delay(2, 3)
            
            # Find all job cards using the VERIFIED selector from diagnostic
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, self.job_card_selector)
            logger.info(f"Found {len(job_cards)} job cards on page")
            
            for i, card in enumerate(job_cards):
                try:
                    # Extract job ID to avoid duplicates
                    job_id = card.get_attribute('data-job-id')
                    if job_id in self.processed_jobs or self.is_job_already_applied(job_id):
                        continue
                    
                    # Extract job title and URL using VERIFIED selector
                    title_element = card.find_element(By.CSS_SELECTOR, self.job_title_selector)
                    job_url = title_element.get_attribute('href')
                    job_title = title_element.get_attribute('title') or title_element.text
                    
                    if job_url and job_id:
                        # Analyze job quality
                        job_quality_score = self.analyze_job_quality(card.text)
                        
                        # Only include jobs that meet quality threshold
                        if job_quality_score >= -10:
                            job_data = {
                                'job_id': job_id,
                                'url': job_url,
                                'title': job_title,
                                'quality_score': job_quality_score
                            }
                            
                            jobs.append(job_data)
                            self.processed_jobs.add(job_id)
                            logger.info(f"Job {i+1}: {job_title} (Score: {job_quality_score})")
                        else:
                            logger.info(f"Job {i+1}: {job_title} rejected (Score: {job_quality_score})")
                            self.skipped += 1
                        
                except Exception as e:
                    logger.warning(f"Error extracting job {i+1}: {e}")
                    continue
            
            logger.info(f"Extracted {len(jobs)} quality jobs from page")
            return jobs
            
        except TimeoutException:
            logger.warning("No job cards found on page")
            return []
        except Exception as e:
            logger.error(f"Error extracting jobs: {e}")
            return []
    
    def scrape_job_links(self):
        """Scrape job links using intelligent strategies"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        all_jobs = []
        
        for keyword_index, keyword in enumerate(keywords):
            logger.info(f"Scraping keyword {keyword_index + 1}/{len(keywords)}: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                try:
                    # Build URL
                    clean_keyword = keyword.lower().replace(' ', '-')
                    clean_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_location}-{page}"
                    
                    logger.info(f"Page {page}/{pages_per_keyword}: {url}")
                    
                    self.driver.get(url)
                    self.smart_delay(4, 7)
                    
                    # Extract jobs from current page
                    page_jobs = self.extract_jobs_from_page()
                    
                    if page_jobs:
                        all_jobs.extend(page_jobs)
                        logger.info(f"Page {page}: Found {len(page_jobs)} quality jobs")
                    else:
                        logger.warning(f"Page {page}: No quality jobs found")
                        if page > 2:  # Stop if no jobs on multiple pages
                            break
                    
                    self.smart_delay(2, 4)
                    
                except Exception as e:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {e}")
                    continue
            
            self.smart_delay(3, 6)  # Delay between keywords
        
        # Sort jobs by quality score
        all_jobs.sort(key=lambda x: x['quality_score'], reverse=True)
        self.joblinks = [job['url'] for job in all_jobs]
        
        logger.info(f"Total quality jobs found: {len(self.joblinks)}")
        
        # Save job data
        if all_jobs:
            df = pd.DataFrame(all_jobs)
            df.to_csv(f"scraped_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)
        
        return len(self.joblinks) > 0
    
    def apply_to_job(self, job_url, job_index):
        """Apply to a single job with enhanced error handling"""
        try:
            logger.info(f"Applying to job {job_index}: {job_url}")
            
            # Navigate to job page
            self.driver.get(job_url)
            self.smart_delay(4, 7)
            
            # Check if already applied
            page_source = self.driver.page_source.lower()
            if any(indicator in page_source for indicator in ['already applied', 'application sent']):
                logger.info("Already applied to this job")
                return False
            
            # Random scroll to mimic reading
            self.driver.execute_script("window.scrollBy(0, 300)")
            self.smart_delay(1, 3)
            
            # Find and click apply button
            apply_button_clicked = False
            for selector in self.apply_button_selectors:
                try:
                    apply_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Scroll to button
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                    self.smart_delay(1, 2)
                    
                    # Try clicking
                    try:
                        apply_button.click()
                        logger.info(f"Apply button clicked using: {selector}")
                        apply_button_clicked = True
                        break
                    except ElementClickInterceptedException:
                        # JavaScript click fallback
                        self.driver.execute_script("arguments[0].click();", apply_button)
                        logger.info(f"Apply button clicked via JS using: {selector}")
                        apply_button_clicked = True
                        break
                        
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue
            
            if not apply_button_clicked:
                logger.warning("No apply button found")
                return False
            
            self.smart_delay(3, 5)
            
            # Handle application form
            self.handle_application_form()
            
            # Save to database
            job_id = job_url.split('-')[-1] if '-' in job_url else str(time.time())
            self.save_job_application({
                'job_id': job_id,
                'url': job_url,
                'title': 'Applied Job'
            }, 'applied')
            
            logger.info("Application completed successfully")
            return True
                
        except Exception as e:
            logger.error(f"Error applying to job {job_url}: {e}")
            return False
    
    def handle_application_form(self):
        """Handle additional application forms"""
        try:
            self.smart_delay(2, 3)
            
            # Common form fields
            form_fields = [
                ('CUSTOM-FIRSTNAME', self.config['personal_info']['firstname']),
                ('firstname', self.config['personal_info']['firstname']),
                ('CUSTOM-LASTNAME', self.config['personal_info']['lastname']),
                ('lastname', self.config['personal_info']['lastname']),
                ('phone', self.config['personal_info'].get('phone', '')),
                ('mobile', self.config['personal_info'].get('phone', ''))
            ]
            
            filled_fields = 0
            for field_id, value in form_fields:
                if not value:
                    continue
                    
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    if field.is_displayed() and field.is_enabled():
                        self.human_type(field, str(value))
                        filled_fields += 1
                        self.smart_delay(0.5, 1)
                except NoSuchElementException:
                    continue
            
            if filled_fields > 0:
                logger.info(f"Filled {filled_fields} form fields")
            
            # Submit form
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
                        self.driver.execute_script("arguments[0].click();", submit_button)
                        logger.info("Form submitted")
                        self.smart_delay(2, 3)
                        return
                except NoSuchElementException:
                    continue
            
        except Exception as e:
            logger.warning(f"Form handling error: {e}")
    
    def apply_to_jobs(self):
        """Apply to all scraped jobs with intelligent limits"""
        max_applications = self.config['job_search']['max_applications_per_session']
        
        logger.info(f"Starting job applications (max: {max_applications})")
        
        for i, job_url in enumerate(self.joblinks, 1):
            if self.applied >= max_applications:
                logger.info(f"Reached session limit: {max_applications}")
                break
            
            try:
                success = self.apply_to_job(job_url, i)
                
                if success:
                    self.applied += 1
                    self.applied_list['passed'].append(job_url)
                    logger.info(f"SUCCESS: {self.applied}/{max_applications} applications sent")
                else:
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    logger.info(f"FAILED: {self.failed} failures")
                
                # Check for daily quota exceeded
                if 'daily quota' in self.driver.page_source.lower():
                    logger.info("Daily quota exceeded. Stopping.")
                    break
                
                # Smart delay between applications
                self.smart_delay(5, 10)
                
            except Exception as e:
                logger.error(f"Unexpected error with job {i}: {e}")
                self.failed += 1
                self.applied_list['failed'].append(job_url)
                continue
    
    def save_results(self):
        """Save application results with detailed statistics"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save basic results
            max_len = max(
                len(self.applied_list['passed']),
                len(self.applied_list['failed']),
                len(self.applied_list.get('skipped', []))
            )
            
            results_data = {
                'successful_applications': self.applied_list['passed'] + [''] * (max_len - len(self.applied_list['passed'])),
                'failed_applications': self.applied_list['failed'] + [''] * (max_len - len(self.applied_list['failed'])),
                'skipped_applications': self.applied_list.get('skipped', []) + [''] * (max_len - len(self.applied_list.get('skipped', [])))
            }
            
            df = pd.DataFrame(results_data)
            df.to_csv(f"naukri_results_{timestamp}.csv", index=False)
            
            # Summary
            summary = {
                'timestamp': timestamp,
                'total_jobs_found': len(self.joblinks),
                'successful_applications': self.applied,
                'failed_applications': self.failed,
                'skipped_jobs': self.skipped,
                'success_rate': f"{(self.applied / len(self.joblinks) * 100):.2f}%" if self.joblinks else "0%"
            }
            
            with open(f"naukri_summary_{timestamp}.json", 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Results saved with timestamp: {timestamp}")
            logger.info(f"SUMMARY - Found: {len(self.joblinks)}, Applied: {self.applied}, Failed: {self.failed}, Skipped: {self.skipped}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def run(self):
        """Main execution method - the core automation workflow"""
        try:
            print("🚀 Starting Intelligent Naukri Job Application Bot")
            print("=" * 60)
            
            # Step 1: Setup WebDriver
            logger.info("Setting up browser...")
            if not self.setup_driver():
                logger.error("Failed to setup browser")
                return False
            
            # Step 2: Login to Naukri
            logger.info("Logging into Naukri...")
            if not self.login():
                logger.error("Failed to login to Naukri")
                return False
            
            # Step 3: Scrape job listings
            logger.info("Starting intelligent job search...")
            if not self.scrape_job_links():
                logger.error("No quality jobs found matching criteria")
                return False
            
            print(f"✅ Found {len(self.joblinks)} quality jobs, starting applications...")
            
            # Step 4: Apply to jobs
            logger.info("Starting job applications...")
            self.apply_to_jobs()
            
            # Step 5: Save results
            logger.info("Saving results...")
            self.save_results()
            
            # Final summary
            print("\n" + "=" * 60)
            print("🎉 NAUKRI AUTOMATION SESSION COMPLETE")
            print("=" * 60)
            print(f"🔍 Jobs Found: {len(self.joblinks)}")
            print(f"✅ Applications Sent: {self.applied}")
            print(f"❌ Applications Failed: {self.failed}")
            print(f"⏭️  Jobs Skipped: {self.skipped}")
            print(f"📈 Success Rate: {(self.applied / len(self.joblinks) * 100):.1f}%" if self.joblinks else "0%")
            print("=" * 60)
            
            logger.info("Bot execution completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Bot execution failed: {e}")
            return False
        
        finally:
            # Cleanup
            if hasattr(self, 'db_conn') and self.db_conn:
                self.db_conn.close()
            if self.driver:
                input("\nPress Enter to close browser...")
                self.driver.quit()
                logger.info("Browser closed")

# Main execution
if __name__ == "__main__":
    print("🤖 Intelligent Naukri Auto-Apply Bot v2.0")
    print("=" * 50)
    
    bot = IntelligentNaukriBot()
    success = bot.run()
    
    if success:
        print("\n✅ Bot completed successfully! Check the generated reports.")
    else:
        print("\n❌ Bot failed. Check logs for details.")