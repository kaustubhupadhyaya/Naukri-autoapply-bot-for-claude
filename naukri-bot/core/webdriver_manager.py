"""
WebDriver Manager - Handles browser setup and recovery
"""

import os
import logging
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


class WebDriverManager:
    """Manages WebDriver creation and recovery"""
    
    def __init__(self, config):
        self.config = config
        self.driver = None
    
    def create_driver(self):
        """Create and return WebDriver instance"""
        logger.info("🌐 Initializing Edge WebDriver...")
        
        options = EdgeOptions()
        
        # Headless mode
        if self.config['webdriver'].get('headless', False):
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        
        # User data directory (for persistent login)
        user_data_dir = self.config['webdriver'].get('user_data_dir', '')
        if user_data_dir:
            options.add_argument(f'--user-data-dir={user_data_dir}')
        
        # Performance optimizations
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # Method 1: Try webdriver-manager
            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ WebDriver initialized (auto-download)")
            except Exception as e:
                logger.debug(f"Auto-download failed: {e}")
                
                # Method 2: Try manual path
                driver_path = self.config['webdriver'].get('edge_driver_path', '')
                if driver_path and os.path.exists(driver_path):
                    service = EdgeService(driver_path)
                    self.driver = webdriver.Edge(service=service, options=options)
                    logger.info("✅ WebDriver initialized (manual path)")
                else:
                    # Method 3: Try system driver
                    self.driver = webdriver.Edge(options=options)
                    logger.info("✅ WebDriver initialized (system)")
            
            # Set timeouts
            self.driver.implicitly_wait(self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            
            return self.driver
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize WebDriver: {e}")
            raise
    
    def is_session_valid(self):
        """Check if WebDriver session is still valid"""
        if not self.driver:
            return False
        
        try:
            self.driver.current_url
            return True
        except:
            return False
    
    def recover_session(self):
        """Attempt to recover WebDriver session"""
        logger.warning("🔄 Attempting session recovery...")
        
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            self.driver = self.create_driver()
            return True
        except:
            logger.error("❌ Session recovery failed")
            return False
    
    def quit(self):
        """Safely close WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except:
                pass