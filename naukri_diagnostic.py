import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('naukri_diagnostic.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NaukriDiagnostic:
    def __init__(self):
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """Setup Edge WebDriver"""
        try:
            options = webdriver.EdgeOptions()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            service = EdgeService(executable_path="C:\\WebDrivers\\msedgedriver.exe")  # Update path
            self.driver = webdriver.Edge(service=service, options=options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            self.driver.set_page_load_timeout(45)
            
            logger.info("WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            return False
    
    def login(self):
        """Login to Naukri"""
        try:
            self.driver.get('https://www.naukri.com/nlogin/login')
            time.sleep(5)
            
            # Fill credentials
            username_field = self.wait.until(EC.element_to_be_clickable((By.ID, 'usernameField')))
            username_field.clear()
            username_field.send_keys("kaustubh.upadhyaya1@gmail.com")  # Your email
            
            password_field = self.wait.until(EC.element_to_be_clickable((By.ID, 'passwordField')))
            password_field.clear()
            password_field.send_keys("9880380081@kK")  # Your password
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            time.sleep(8)
            logger.info("Login completed")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def analyze_job_page_structure(self):
        """Analyze the structure of job listing pages"""
        test_urls = [
            "https://www.naukri.com/data-engineer-jobs-in-bengaluru-1",
            "https://www.naukri.com/python-developer-jobs-in-bengaluru-1",
            "https://www.naukri.com/etl-developer-jobs-in-bengaluru-1"
        ]
        
        for url in test_urls:
            logger.info(f"\n=== Analyzing URL: {url} ===")
            try:
                self.driver.get(url)
                time.sleep(8)
                
                # Save page source for manual inspection
                with open(f"page_source_{url.split('/')[-1]}.html", 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                
                # Analyze with BeautifulSoup
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Look for various possible job container elements
                potential_selectors = [
                    'article',
                    'div[class*="job"]',
                    'div[class*="tuple"]',
                    'div[class*="card"]',
                    'div[class*="listing"]',
                    'div[data-job-id]',
                    'div[data-id]'
                ]
                
                logger.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
                
                for selector in potential_selectors:
                    elements = soup.select(selector)
                    if elements:
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        
                        # Print first element's structure
                        if elements:
                            first_element = elements[0]
                            logger.info(f"First element HTML (first 500 chars): {str(first_element)[:500]}")
                            
                            # Look for links within this element
                            links = first_element.find_all('a', href=True)
                            if links:
                                logger.info(f"Found {len(links)} links in first element")
                                for i, link in enumerate(links[:3]):  # First 3 links
                                    logger.info(f"Link {i+1}: {link.get('href')} - Text: {link.get_text(strip=True)[:100]}")
                    else:
                        logger.info(f"No elements found with selector: {selector}")
                
                # Try to find any divs that contain job-related text
                job_keywords = ['apply', 'job', 'position', 'role', 'hiring', 'company']
                for keyword in job_keywords:
                    elements = soup.find_all(text=lambda text: text and keyword.lower() in text.lower())
                    if elements:
                        logger.info(f"Found {len(elements)} text elements containing '{keyword}'")
                        
                # Print all unique class names on the page
                all_classes = set()
                for element in soup.find_all(True):
                    if element.get('class'):
                        all_classes.update(element.get('class'))
                
                job_related_classes = [cls for cls in all_classes if any(keyword in cls.lower() 
                                     for keyword in ['job', 'card', 'tuple', 'listing', 'apply'])]
                
                if job_related_classes:
                    logger.info(f"Job-related CSS classes found: {job_related_classes}")
                else:
                    logger.info("No job-related CSS classes found")
                
                # Check if page loaded properly
                if "no jobs found" in self.driver.page_source.lower():
                    logger.warning("Page shows 'No jobs found'")
                
                if "please try a different search" in self.driver.page_source.lower():
                    logger.warning("Page suggests trying different search")
                
                logger.info("="*50)
                
            except Exception as e:
                logger.error(f"Error analyzing {url}: {e}")
                continue
    
    def test_direct_search(self):
        """Test using Naukri's search functionality"""
        try:
            logger.info("\n=== Testing Direct Search ===")
            self.driver.get('https://www.naukri.com/')
            time.sleep(5)
            
            # Try to find search boxes
            search_selectors = [
                '#qsb-keyword-sugg',
                'input[placeholder*="keyword"]',
                'input[placeholder*="designation"]',
                '#suggestor-value'
            ]
            
            for selector in search_selectors:
                try:
                    search_box = self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"Found search box with selector: {selector}")
                    
                    search_box.clear()
                    search_box.send_keys("Data Engineer")
                    time.sleep(2)
                    
                    # Look for search button
                    search_button_selectors = [
                        '.qsbSubmit',
                        'button[type="submit"]',
                        '.search-button'
                    ]
                    
                    for btn_selector in search_button_selectors:
                        try:
                            search_btn = self.driver.find_element(By.CSS_SELECTOR, btn_selector)
                            search_btn.click()
                            logger.info(f"Clicked search button with selector: {btn_selector}")
                            time.sleep(8)
                            
                            # Analyze results page
                            current_url = self.driver.current_url
                            logger.info(f"Search results URL: {current_url}")
                            
                            # Save this page source too
                            with open("search_results_page.html", 'w', encoding='utf-8') as f:
                                f.write(self.driver.page_source)
                            
                            return True
                        except:
                            continue
                    
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Direct search test failed: {e}")
    
    def run_diagnosis(self):
        """Run complete diagnosis"""
        try:
            logger.info("Starting Naukri website structure diagnosis")
            
            if not self.setup_driver():
                return False
            
            if not self.login():
                return False
            
            # Test both direct URLs and search functionality
            self.analyze_job_page_structure()
            self.test_direct_search()
            
            logger.info("Diagnosis completed. Check the log file and saved HTML files.")
            
        except Exception as e:
            logger.error(f"Diagnosis failed: {e}")
        finally:
            if self.driver:
                input("Press Enter to close browser and see results...")
                self.driver.quit()

if __name__ == "__main__":
    diagnostic = NaukriDiagnostic()
    diagnostic.run_diagnosis()