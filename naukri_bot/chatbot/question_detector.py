"""
Question Detector - Detects questions using multiple strategies
"""

import logging
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class QuestionDetector:
    """Detects questions in chatbot using multiple strategies"""
    
    def __init__(self, driver):
        self.driver = driver
        
        # Comprehensive question selectors (Tier 1 improvement)
        self.question_selectors = [
            # Labels (most common)
            "label",
            "label[for]",
            
            # Question divs
            "div[class*='question']",
            "div[class*='label']",
            "div[class*='title']",
            "div[class*='field-label']",
            
            # Spans
            "span[class*='question']",
            "span[class*='label']",
            
            # Paragraphs
            "p[class*='question']",
            
            # Text before inputs
            "div:has(input) label",
            "div:has(select) label",
            "div:has(textarea) label",
            
            # Specific patterns
            "*[data-question]",
            "*[aria-label]"
        ]
        
        # Keywords that indicate a real question
        self.question_keywords = [
            'experience', 'years', 'ctc', 'salary', 'notice', 
            'location', 'relocate', 'comfortable', 'current',
            'expected', 'period', 'shift', 'joining', 'available'
        ]
    
    def detect_question(self):
        """
        Detect question using multiple selectors
        Returns: (question_text, question_element) or (None, None)
        """
        for selector in self.question_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for elem in elements:
                    if not elem.is_displayed():
                        continue
                    
                    text = elem.text.strip()
                    
                    # Validate if this is a real question
                    if self._is_valid_question(text):
                        logger.info(f"❓ Question detected: '{text[:80]}...'")
                        return text, elem
                        
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return None, None
    
    def _is_valid_question(self, text):
        """Check if text is a valid question"""
        if not text:
            return False
        
        # Must have minimum length
        if len(text) < 3:
            return False
        
        # Check for question mark
        if '?' in text:
            return True
        
        # Check for minimum length
        if len(text) > 10:
            return True
        
        # Check for question keywords
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in self.question_keywords):
            return True
        
        return False
    
    def detect_submit_button(self):
        """Detect if submit button is visible (indicates completion)"""
        submit_selectors = [
            "button[type='submit']",
            "button:contains('Submit')",
            "button:contains('Apply')",
            "input[type='submit']"
        ]
        
        for selector in submit_selectors:
            try:
                if ':contains' in selector:
                    # Use XPath for text matching
                    text = selector.split("'")[1]
                    from selenium.webdriver.common.by import By
                    btn = self.driver.find_element(
                        By.XPATH, 
                        f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
                    )
                else:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if btn.is_displayed() and btn.is_enabled():
                    return btn
                    
            except:
                continue
        
        return None