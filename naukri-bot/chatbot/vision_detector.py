"""
Vision Detector - Uses Gemini Vision to detect questions (TIER 2)
"""

import json
import logging
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class VisionDetector:
    """Uses Gemini Vision to detect questions in screenshots"""
    
    def __init__(self, driver, gemini_model):
        self.driver = driver
        self.gemini_model = gemini_model
    
    def detect_question_with_vision(self):
        """
        Use Gemini Vision to detect questions in modal
        Returns: dict with question info or None
        """
        if not self.gemini_model:
            logger.debug("Gemini model not available for vision detection")
            return None
        
        try:
            # Take screenshot
            screenshot_base64 = self.driver.get_screenshot_as_base64()
            
            # Convert to PIL Image
            from PIL import Image
            image_bytes = base64.b64decode(screenshot_base64)
            image = Image.open(BytesIO(image_bytes))
            
            # Create prompt for Gemini
            prompt = """
            Analyze this screenshot of a job application form.
            
            Find and extract:
            1. The question being asked (if any visible)
            2. The type of input required (text, number, dropdown, radio, checkbox)
            3. Available options (if dropdown or radio buttons visible)
            
            Return ONLY a valid JSON object with this structure:
            {
                "question": "the exact question text or null if no question visible",
                "input_type": "text|number|dropdown|radio|checkbox|null",
                "options": ["option1", "option2"] or null
            }
            
            DO NOT include any explanation, only the JSON object.
            """
            
            # Generate response
            response = self.gemini_model.generate_content([prompt, image])
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            if result.get('question'):
                logger.info(f"📸 Vision detected question: '{result['question'][:80]}...'")
                return result
            
            return None
            
        except Exception as e:
            logger.debug(f"Vision detection failed: {e}")
            return None
    
    def analyze_full_form(self):
        """
        Analyze entire form to extract all questions
        Returns: list of question dicts
        """
        if not self.gemini_model:
            return []
        
        try:
            screenshot_base64 = self.driver.get_screenshot_as_base64()
            
            from PIL import Image
            image_bytes = base64.b64decode(screenshot_base64)
            image = Image.open(BytesIO(image_bytes))
            
            prompt = """
            Analyze this job application form screenshot.
            
            Extract ALL visible questions/fields in order from top to bottom.
            
            Return ONLY a valid JSON array:
            [
                {
                    "question": "question text",
                    "input_type": "text|number|dropdown|radio|checkbox",
                    "options": ["option1", "option2"] or null,
                    "order": 1
                },
                ...
            ]
            
            DO NOT include explanation, only JSON array.
            """
            
            response = self.gemini_model.generate_content([prompt, image])
            response_text = response.text.strip()
            
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            questions = json.loads(response_text)
            
            logger.info(f"📸 Vision extracted {len(questions)} questions from form")
            return questions
            
        except Exception as e:
            logger.debug(f"Full form analysis failed: {e}")
            return []