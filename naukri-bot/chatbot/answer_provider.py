"""
Answer Provider - Provides answers using multiple methods
"""

import logging
from .qa_dictionary import QADictionary

logger = logging.getLogger(__name__)


class AnswerProvider:
    """Provides answers using multiple strategies"""
    
    def __init__(self, config, qa_dictionary):
        self.config = config
        self.qa_dictionary = qa_dictionary
        self.gemini_model = None
        
        # Initialize Gemini if API key available
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini model if API key available"""
        api_key = self.config.get('gemini_api_key', '')
        
        if not api_key or api_key == '':
            logger.info("No Gemini API key, skipping Gemini initialization")
            return
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
            logger.info("✅ Gemini initialized")
        except Exception as e:
            logger.warning(f"Gemini initialization failed: {e}")
    
    def get_answer(self, question):
        """
        Get answer using comprehensive strategy (Tier 1 improvement)
        Order: Config → QA Dictionary → Keyword → Gemini → Smart Defaults
        """
        
        # Method 1: Check hardcoded config
        answer = self._get_config_answer(question)
        if answer:
            logger.info(f"💡 Answer from config: '{answer}'")
            return answer
        
        # Method 2: Check QA dictionary (exact + fuzzy)
        answer = self.qa_dictionary.get_fuzzy_answer(question)
        if answer:
            logger.info(f"💡 Answer from QA dictionary: '{answer}'")
            return answer
        
        # Method 3: Keyword matching
        answer = self._get_keyword_answer(question)
        if answer:
            logger.info(f"💡 Answer from keywords: '{answer}'")
            return answer
        
        # Method 4: Use Gemini
        if self.gemini_model:
            answer = self._get_gemini_answer(question)
            if answer:
                logger.info(f"💡 Answer from Gemini: '{answer}'")
                return answer
        
        # Method 5: Smart defaults
        answer = self._get_smart_default(question)
        if answer:
            logger.info(f"💡 Answer from smart defaults: '{answer}'")
            return answer
        
        # Fallback
        logger.warning(f"⚠️ No answer found for: '{question[:50]}'")
        return self.config.get('chatbot_answers', {}).get('default_answer', 'Yes')
    
    def _get_config_answer(self, question):
        """Get answer from config.json"""
        if 'chatbot_answers' not in self.config:
            return None
        
        qa_dict = self.config['chatbot_answers']
        question_lower = question.lower()
        
        for key, value in qa_dict.items():
            if key.lower() in question_lower:
                return str(value)
        
        return None
    
    def _get_keyword_answer(self, question):
        """Get answer using keyword matching"""
        question_lower = question.lower()
        
        # Experience questions
        if any(word in question_lower for word in ['experience', 'years']):
            if 'python' in question_lower:
                return self.config.get('chatbot_answers', {}).get('experience', '5')
            return self.config.get('chatbot_answers', {}).get('experience', '5')
        
        # CTC questions
        if 'current' in question_lower and 'ctc' in question_lower:
            return self.config.get('chatbot_answers', {}).get('current_ctc', '15')
        
        if 'expected' in question_lower and 'ctc' in question_lower:
            return self.config.get('chatbot_answers', {}).get('expected_ctc', '20')
        
        # Notice period
        if 'notice' in question_lower:
            return self.config.get('chatbot_answers', {}).get('notice_period', '30')
        
        # Location
        if 'location' in question_lower or 'relocate' in question_lower:
            return self.config.get('job_search', {}).get('location', 'Bengaluru')
        
        return None
    
    def _get_gemini_answer(self, question):
        """Get answer using Gemini"""
        if not self.gemini_model:
            return None
        
        try:
            # Create profile context
            profile_context = f"""
            User Profile:
            - Experience: {self.config.get('chatbot_answers', {}).get('experience', '5')} years
            - Current CTC: {self.config.get('chatbot_answers', {}).get('current_ctc', '15')} LPA
            - Expected CTC: {self.config.get('chatbot_answers', {}).get('expected_ctc', '20')} LPA
            - Notice Period: {self.config.get('chatbot_answers', {}).get('notice_period', '30')} days
            - Location: {self.config.get('job_search', {}).get('location', 'Bengaluru')}
            
            Question: {question}
            
            Provide a concise, direct answer (1-5 words max). If yes/no question, answer Yes or No.
            """
            
            response = self.gemini_model.generate_content(profile_context)
            answer = response.text.strip()
            
            # Clean up answer
            if len(answer) > 50:
                answer = answer[:50]
            
            return answer
            
        except Exception as e:
            logger.debug(f"Gemini answer failed: {e}")
            return None
    
    def _get_smart_default(self, question):
        """Get smart default based on question type"""
        question_lower = question.lower()
        
        # Yes/No questions - default Yes
        yes_no_indicators = [
            'are you', 'do you', 'can you', 'will you', 
            'comfortable', 'willing', 'able to'
        ]
        
        if any(indicator in question_lower for indicator in yes_no_indicators):
            return 'Yes'
        
        # Location questions
        if 'location' in question_lower:
            return self.config.get('job_search', {}).get('location', 'Bengaluru')
        
        return None