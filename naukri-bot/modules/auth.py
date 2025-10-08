"""
Authentication Module - Handles login and session management
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.helpers import smart_delay, human_type

logger = logging.getLogger(__name__)


class AuthModule:
    """Handles authentication and login"""
    
    def __init__(self, driver, config):
        self.driver = driver
        self.config = config
    
    def login(self):
        """
        Login to Naukri.com
        Returns: True if successful, False otherwise
        """
        try:
            logger.info("🔐 Logging in to Naukri.com...")
            
            # Navigate to login page
            self.driver.get("https://www.naukri.com/nlogin/login")
            smart_delay(2, 3)
            
            # Get credentials
            email = self.config['credentials']['email']
            password = self.config['credentials']['password']
            
            # Check if already logged in
            if self._is_logged_in():
                logger.info("✅ Already logged in")
                return True
            
            # Find and fill email field
            if not self._enter_email(email):
                logger.error("Failed to enter email")
                return False
            
            smart_delay(0.5, 1)
            
            # Find and fill password field
            if not self._enter_password(password):
                logger.error("Failed to enter password")
                return False
            
            smart_delay(0.5, 1)
            
            # Click login button
            if not self._click_login_button():
                logger.error("Failed to click login button")
                return False
            
            # Wait for login to complete
            smart_delay(3, 5)
            
            # Verify login success
            if self._is_logged_in():
                logger.info("✅ Login successful")
                return True
            else:
                logger.error("❌ Login failed - not logged in after attempt")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def _is_logged_in(self):
        """Check if user is already logged in"""
        logged_in_indicators = [
            "a[title='My Naukri']",
            "div.nI-gNb-drawer__icon",
            "a.nI-gNb-drawer__icon",
            "div[class*='user-name']",
            "div[class*='logout']"
        ]
        
        for selector in logged_in_indicators:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    return True
            except:
                continue
        
        return False
    
    def _enter_email(self, email):
        """Enter email in login form"""
        email_selectors = [
            '#usernameField',
            "input[placeholder*='Email']",
            "input[placeholder*='email']",
            "input[type='email']",
            "input[name='email']",
            "input[id*='email']"
        ]
        
        for selector in email_selectors:
            try:
                email_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                if email_field.is_displayed() and email_field.is_enabled():
                    email_field.clear()
                    human_type(email_field, email)
                    logger.info("✅ Email entered")
                    return True
                    
            except:
                continue
        
        return False
    
    def _enter_password(self, password):
        """Enter password in login form"""
        password_selectors = [
            '#passwordField',
            "input[placeholder*='Password']",
            "input[placeholder*='password']",
            "input[type='password']",
            "input[name='password']",
            "input[id*='password']"
        ]
        
        for selector in password_selectors:
            try:
                password_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                if password_field.is_displayed() and password_field.is_enabled():
                    password_field.clear()
                    human_type(password_field, password)
                    logger.info("✅ Password entered")
                    return True
                    
            except:
                continue
        
        return False
    
    def _click_login_button(self):
        """Click login/submit button"""
        login_button_selectors = [
            "button[type='submit']",
            "button.btn-primary",
            "button[class*='login']",
            "//button[contains(text(), 'Login')]",
            "//button[contains(text(), 'Sign in')]"
        ]
        
        for selector in login_button_selectors:
            try:
                if selector.startswith('//'):
                    button = self.driver.find_element(By.XPATH, selector)
                else:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    logger.info("✅ Login button clicked")
                    return True
                    
            except:
                continue
        
        return False
    
    def logout(self):
        """Logout from Naukri"""
        try:
            logger.info("Logging out...")
            
            # Find logout link
            logout_selectors = [
                "a[href*='logout']",
                "a[title='Logout']",
                "//a[contains(text(), 'Logout')]"
            ]
            
            for selector in logout_selectors:
                try:
                    if selector.startswith('//'):
                        logout_link = self.driver.find_element(By.XPATH, selector)
                    else:
                        logout_link = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if logout_link.is_displayed():
                        logout_link.click()
                        logger.info("✅ Logged out successfully")
                        return True
                        
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False