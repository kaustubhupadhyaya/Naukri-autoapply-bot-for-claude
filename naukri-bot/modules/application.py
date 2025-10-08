"""
Application Module - Handles job application submission
"""

import time
import logging
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from utils.helpers import smart_delay, extract_job_id, sanitize_filename
from chatbot.chatbot_handler import ChatbotHandler

logger = logging.getLogger(__name__)


class ApplicationModule:
    """Handles job application process"""
    
    def __init__(self, driver, config, database):
        self.driver = driver
        self.config = config
        self.database = database
        self.chatbot_handler = ChatbotHandler(driver, config)
        
        # Statistics
        self.applied = 0
        self.failed = 0
        self.skipped = 0
    
    def apply_to_job(self, job_url):
        """
        Apply to a single job
        Returns: True if successful, False otherwise
        """
        try:
            job_id = extract_job_id(job_url)
            
            # Check if already applied
            if self.database.is_job_applied(job_id):
                logger.info("⏩ Already applied, skipping")
                self.skipped += 1
                return False
            
            # Navigate to job
            logger.info(f"🌐 Opening job: {job_url}")
            self.driver.get(job_url)
            smart_delay(2, 3)
            
            # Check if external redirect
            if self._is_external_redirect():
                logger.info("🔗 External job posting, skipping")
                self.skipped += 1
                return False
            
            # Click Easy Apply button
            if not self._click_easy_apply():
                logger.warning("❌ Easy Apply button not found")
                self.failed += 1
                return False
            
            smart_delay(1, 2)
            
            # Handle chatbot if present
            chatbot_handled = self.chatbot_handler.handle_chatbot(timeout=3)
            
            if chatbot_handled:
                logger.info(f"💬 Chatbot handled - {self.chatbot_handler.questions_answered} questions answered")
            
            # Submit application
            if self._submit_application():
                logger.info("✅ Application submitted successfully")
                
                # Save to database
                self.database.add_applied_job(
                    job_id=job_id,
                    job_url=job_url,
                    status='applied'
                )
                
                self.applied += 1
                return True
            else:
                logger.error("❌ Application submission failed")
                self._take_debug_screenshot(job_id)
                self.failed += 1
                return False
                
        except Exception as e:
            logger.error(f"Application error: {e}")
            self._take_debug_screenshot(extract_job_id(job_url))
            self.failed += 1
            return False
    
    def _is_external_redirect(self):
        """Check if job redirects to external site"""
        current_url = self.driver.current_url.lower()
        
        external_domains = [
            'linkedin.com',
            'indeed.com',
            'monster.com',
            'shine.com',
            'naukrigulf.com'
        ]
        
        return any(domain in current_url for domain in external_domains)
    
    def _click_easy_apply(self):
        """Click Easy Apply button"""
        easy_apply_selectors = [
            "button.btn-primary",
            "button:contains('Apply')",
            "a:contains('Apply')",
            "button[class*='apply']",
            "//button[contains(text(), 'Apply')]",
            "//span[contains(text(), 'Apply')]/.."
        ]
        
        for selector in easy_apply_selectors:
            try:
                if selector.startswith('//'):
                    button = self.driver.find_element(By.XPATH, selector)
                elif ':contains' in selector:
                    text = 'Apply'
                    button = self.driver.find_element(
                        By.XPATH,
                        f"//{selector.split(':')[0]}[contains(text(), '{text}')]"
                    )
                else:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    logger.info("✅ Easy Apply button clicked")
                    return True
                    
            except:
                continue
        
        return False
    
    def _submit_application(self):
        """Submit the application"""
        submit_button_selectors = [
            "button[type='submit']",
            "button:contains('Submit')",
            "button:contains('Apply')",
            "button.btn-primary",
            "//button[contains(text(), 'Submit')]",
            "//button[contains(text(), 'Apply')]",
            "input[type='submit']"
        ]
        
        for selector in submit_button_selectors:
            try:
                if selector.startswith('//'):
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                elif ':contains' in selector:
                    tag = selector.split(':')[0]
                    text = selector.split("'")[1]
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            f"//{tag}[contains(text(), '{text}')]"
                        ))
                    )
                else:
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    logger.info("✅ Submit button clicked")
                    smart_delay(2, 3)
                    
                    # Verify submission
                    if self._verify_submission():
                        return True
                        
            except TimeoutException:
                continue
            except Exception as e:
                logger.debug(f"Submit attempt failed: {e}")
                continue
        
        return False
    
    def _verify_submission(self):
        """Verify application was submitted successfully"""
        success_indicators = [
            "div:contains('Application sent')",
            "div:contains('Successfully applied')",
            "div:contains('Application submitted')",
            "//div[contains(text(), 'successfully')]",
            "//div[contains(text(), 'applied')]",
            "span.success"
        ]
        
        for selector in success_indicators:
            try:
                if selector.startswith('//'):
                    element = self.driver.find_element(By.XPATH, selector)
                elif ':contains' in selector:
                    text = selector.split("'")[1]
                    element = self.driver.find_element(
                        By.XPATH,
                        f"//div[contains(text(), '{text}')]"
                    )
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if element.is_displayed():
                    return True
                    
            except:
                continue
        
        return False
    
    def _take_debug_screenshot(self, job_id):
        """Take screenshot for debugging"""
        try:
            from pathlib import Path
            
            screenshot_dir = Path('debug_screenshots')
            screenshot_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"failed_{job_id}_{timestamp}.png"
            
            filepath = screenshot_dir / filename
            self.driver.save_screenshot(str(filepath))
            
            logger.info(f"📸 Debug screenshot saved: {filepath}")
            
        except Exception as e:
            logger.debug(f"Could not save screenshot: {e}")
    
    def get_statistics(self):
        """Get application statistics"""
        return {
            'applied': self.applied,
            'failed': self.failed,
            'skipped': self.skipped
        }