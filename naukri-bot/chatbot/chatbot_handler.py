"""
Chatbot Handler - Main chatbot interaction logic (TIER 1 COMPLETE)
"""

import time
import csv
import logging
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .question_detector import QuestionDetector
from .answer_provider import AnswerProvider
from .qa_dictionary import QADictionary

logger = logging.getLogger(__name__)


class ChatbotHandler:
    """
    Complete Chatbot Handler with all Tier 1 improvements:
    - Multiple question selectors
    - Q&A dictionary loading
    - Comprehensive answer strategies
    - Question logging
    - Radio button & dropdown support
    """
    
    def __init__(self, driver, config):
        self.driver = driver
        self.config = config
        
        # Initialize components
        self.qa_dictionary = QADictionary()
        self.answer_provider = AnswerProvider(config, self.qa_dictionary)
        self.question_detector = QuestionDetector(driver)
        
        self.questions_answered = 0
    
    def handle_chatbot(self, timeout=5):
        """
        Main chatbot handler with improved detection (TIER 1 COMPLETE)
        Returns: True if chatbot handled, False if no chatbot
        """
        try:
            # Wait for chatbot modal
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    "div[class*='chatbot'], div[class*='modal'], div[class*='apply-form']"
                ))
            )
            
            logger.info("💬 Chatbot/Modal detected")
            
            start_time = time.time()
            max_interaction_time = 60  # Increased from 30
            self.questions_answered = 0
            
            while (time.time() - start_time) < max_interaction_time:
                try:
                    # Detect question
                    question_text, question_element = self.question_detector.detect_question()
                    
                    # If no question found, check if we're done
                    if not question_text:
                        submit_btn = self.question_detector.detect_submit_button()
                        
                        if submit_btn:
                            logger.info(f"✅ Chatbot completed - {self.questions_answered} questions answered")
                            return True
                        
                        # No question and no submit = stuck or done
                        logger.warning("⚠️ No question found, exiting chatbot")
                        break
                    
                    # Log question to CSV
                    self._log_question(question_text)
                    logger.info(f"❓ Q{self.questions_answered + 1}: '{question_text[:80]}...'")
                    
                    # Get answer
                    answer = self.answer_provider.get_answer(question_text)
                    
                    if not answer:
                        answer = 'Yes'  # Ultimate fallback
                    
                    logger.info(f"💡 Answer: '{answer}'")
                    
                    # Submit answer
                    if self._submit_answer(answer):
                        self.questions_answered += 1
                        logger.info(f"✅ Answer submitted ({self.questions_answered} total)")
                        time.sleep(1)  # Wait for next question
                    else:
                        logger.warning("⚠️ Could not submit answer")
                        break
                        
                except NoSuchElementException:
                    break
                except Exception as e:
                    logger.debug(f"Chatbot interaction error: {e}")
                    break
            
            logger.info(f"✅ Chatbot session ended - {self.questions_answered} questions answered")
            return True
            
        except TimeoutException:
            logger.info("No chatbot detected")
            return False
        except Exception as e:
            logger.error(f"Chatbot handler error: {e}")
            return False
    
    def _submit_answer(self, answer):
        """Submit answer (handles text, dropdown, radio buttons)"""
        
        # Try text input
        if self._submit_text_input(answer):
            return True
        
        # Try dropdown
        if self._submit_dropdown(answer):
            return True
        
        # Try radio buttons
        if self._submit_radio(answer):
            return True
        
        # Try checkbox
        if self._submit_checkbox(answer):
            return True
        
        return False
    
    def _submit_text_input(self, answer):
        """Submit text/number input"""
        input_selectors = [
            "input[type='text']",
            "input[type='number']",
            "input:not([type='hidden']):not([type='submit']):not([type='radio']):not([type='checkbox'])",
            "textarea"
        ]
        
        for selector in input_selectors:
            try:
                inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for inp in inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        inp.clear()
                        inp.send_keys(answer)
                        
                        # Click next/submit button
                        if self._click_next_button():
                            return True
                        
            except:
                continue
        
        return False
    
    def _submit_dropdown(self, answer):
        """Submit dropdown selection"""
        try:
            from selenium.webdriver.support.ui import Select
            
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            
            for select_elem in selects:
                if select_elem.is_displayed() and select_elem.is_enabled():
                    select = Select(select_elem)
                    
                    # Try selecting by visible text
                    try:
                        select.select_by_visible_text(answer)
                    except:
                        try:
                            # Try by value
                            select.select_by_value(answer)
                        except:
                            # Select first non-empty option
                            for option in select.options[1:]:
                                if option.text.strip():
                                    option.click()
                                    break
                    
                    # Click next button
                    if self._click_next_button():
                        return True
                    
        except Exception as e:
            logger.debug(f"Dropdown submission failed: {e}")
        
        return False
    
    def _submit_radio(self, answer):
        """Submit radio button selection"""
        try:
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            
            if not radios:
                return False
            
            # Try to match answer to radio label
            for radio in radios:
                try:
                    radio_id = radio.get_attribute('id')
                    
                    if radio_id:
                        label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                        label_text = label.text.strip().lower()
                        
                        # Check if answer matches
                        if answer.lower() in label_text or label_text in answer.lower():
                            if radio.is_displayed():
                                radio.click()
                            else:
                                label.click()
                            
                            logger.info(f"✅ Selected radio: {label_text}")
                            
                            # Click next button
                            if self._click_next_button():
                                return True
                            
                except:
                    continue
            
            # Default: click first radio
            if radios[0].is_displayed():
                radios[0].click()
                
                if self._click_next_button():
                    return True
                    
        except Exception as e:
            logger.debug(f"Radio button submission failed: {e}")
        
        return False
    
    def _submit_checkbox(self, answer):
        """Submit checkbox selection"""
        try:
            # For yes/no questions with checkboxes
            if answer.lower() in ['yes', 'true', '1']:
                checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                
                for checkbox in checkboxes:
                    if checkbox.is_displayed() and not checkbox.is_selected():
                        checkbox.click()
                        
                        if self._click_next_button():
                            return True
                        
        except Exception as e:
            logger.debug(f"Checkbox submission failed: {e}")
        
        return False
    
    def _click_next_button(self):
        """Click next/continue/submit button"""
        button_selectors = [
            ("xpath", "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]"),
            ("xpath", "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]"),
            ("xpath", "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]"),
            ("css", "button[type='button']"),
            ("css", "button[type='submit']")
        ]
        
        for selector_type, selector in button_selectors:
            try:
                if selector_type == "xpath":
                    btn = self.driver.find_element(By.XPATH, selector)
                else:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    time.sleep(0.5)
                    return True
                    
            except:
                continue
        
        return False
    
    def _log_question(self, question):
        """Log question to CSV for future reference"""
        try:
            csv_file = 'chatbot_questions.csv'
            file_exists = Path(csv_file).exists()
            
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow(['timestamp', 'question'])
                
                writer.writerow([datetime.now().isoformat(), question])
                
        except Exception as e:
            logger.debug(f"Could not log question: {e}")


# Import Path for _log_question
from pathlib import Path