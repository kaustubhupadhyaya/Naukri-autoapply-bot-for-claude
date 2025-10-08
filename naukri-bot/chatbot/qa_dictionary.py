"""
Q&A Dictionary Manager - Loads and manages question-answer pairs
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class QADictionary:
    """Manages Q&A dictionary for chatbot"""
    
    def __init__(self, dictionary_file='qa_dictionary.json'):
        self.dictionary_file = dictionary_file
        self.qa_dict = {}
        self.load_dictionary()
    
    def load_dictionary(self):
        """Load Q&A dictionary from file"""
        if not Path(self.dictionary_file).exists():
            logger.info("No QA dictionary found, creating default...")
            self._create_default_dictionary()
            return
        
        try:
            with open(self.dictionary_file, 'r', encoding='utf-8') as f:
                self.qa_dict = json.load(f)
            
            logger.info(f"✅ Loaded {len(self.qa_dict)} Q&A pairs")
            
        except Exception as e:
            logger.error(f"Failed to load QA dictionary: {e}")
            self.qa_dict = {}
    
    def _create_default_dictionary(self):
        """Create default Q&A dictionary"""
        default_qa = {
            "What is your notice period?": "30 days",
            "What is your current CTC in Lacs per annum?": "15",
            "What is your expected CTC in Lacs per annum?": "20",
            "How many years of experience do you have in Python?": "5",
            "Are you comfortable working on 24x7 shifts?": "Yes",
            "Are you on a career break?": "No",
            "Country Code": "+91",
            "Current Location": "Bengaluru",
            "Preferred Location": "Bengaluru",
            "Total Relevant Experience": "5 years",
            "Are you comfortable working in rotational shifts?": "Yes",
            "Can you join immediately?": "Yes",
            "Are you willing to relocate?": "Yes"
        }
        
        self.qa_dict = default_qa
        self.save_dictionary()
        logger.info(f"✅ Created default QA dictionary with {len(default_qa)} pairs")
    
    def get_answer(self, question):
        """Get answer for question (exact match)"""
        return self.qa_dict.get(question)
    
    def get_fuzzy_answer(self, question):
        """Get answer using fuzzy matching"""
        question_lower = question.lower()
        
        # Try exact match first
        if question in self.qa_dict:
            return self.qa_dict[question]
        
        # Try case-insensitive
        for q, a in self.qa_dict.items():
            if q.lower() == question_lower:
                return a
        
        # Try substring match
        for q, a in self.qa_dict.items():
            if q.lower() in question_lower or question_lower in q.lower():
                return a
        
        return None
    
    def add_qa(self, question, answer):
        """Add Q&A pair to dictionary"""
        self.qa_dict[question] = answer
        self.save_dictionary()
        logger.info(f"💾 Saved Q&A: '{question[:50]}' → '{answer}'")
    
    def save_dictionary(self):
        """Save dictionary to file"""
        try:
            with open(self.dictionary_file, 'w', encoding='utf-8') as f:
                json.dump(self.qa_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save QA dictionary: {e}")