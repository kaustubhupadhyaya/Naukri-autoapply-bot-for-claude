"""
Auto Learner - Automatically learns questions and improves over time (TIER 3)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AutoLearner:
    """Automatically learns from chatbot interactions"""
    
    def __init__(self, driver, gemini_model, qa_dictionary, vision_detector):
        self.driver = driver
        self.gemini_model = gemini_model
        self.qa_dictionary = qa_dictionary
        self.vision_detector = vision_detector
        
        self.recording_file = Path('chatbot_recordings') / f'recording_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        self.recording_file.parent.mkdir(exist_ok=True)
        
        self.actions = []
    
    def learn_from_screenshot(self, question=None):
        """
        Automatically learn question from screenshot
        Saves screenshot and uses vision to extract question if not provided
        """
        try:
            # Save screenshot
            screenshot_dir = Path('chatbot_screenshots')
            screenshot_dir.mkdir(exist_ok=True)
            
            screenshot_path = screenshot_dir / f'chatbot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            self.driver.save_screenshot(str(screenshot_path))
            
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            
            # If question not provided, use vision to detect
            if not question and self.vision_detector:
                vision_result = self.vision_detector.detect_question_with_vision()
                if vision_result and vision_result.get('question'):
                    question = vision_result['question']
            
            if question:
                # Check if we have answer
                answer = self.qa_dictionary.get_fuzzy_answer(question)
                
                if not answer:
                    # Prompt user for answer (if interactive mode)
                    logger.warning(f"❓ NEW QUESTION: {question}")
                    logger.info(f"📸 Screenshot: {screenshot_path}")
                    
                    # Could integrate with UI or console for user input
                    # For now, just log it
                    self._log_unanswered_question(question, str(screenshot_path))
                
                return question, answer, str(screenshot_path)
            
        except Exception as e:
            logger.error(f"Learning from screenshot failed: {e}")
        
        return None, None, None
    
    def record_action(self, question, answer, selector_used, success):
        """Record a chatbot action for replay"""
        action = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'selector_used': selector_used,
            'success': success
        }
        
        self.actions.append(action)
    
    def save_recording(self):
        """Save recorded actions to file"""
        try:
            with open(self.recording_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_actions': len(self.actions),
                    'actions': self.actions
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📹 Recorded {len(self.actions)} actions to {self.recording_file}")
            
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
    
    def replay_recording(self, recording_file):
        """
        Replay a recorded chatbot flow
        Useful for testing and automation
        """
        try:
            with open(recording_file, 'r', encoding='utf-8') as f:
                recording = json.load(f)
            
            actions = recording.get('actions', [])
            
            logger.info(f"▶️ Replaying {len(actions)} actions from {recording_file}")
            
            for i, action in enumerate(actions):
                logger.info(f"Action {i+1}/{len(actions)}: {action['question'][:50]}...")
                # Implementation would depend on specific replay strategy
                # Could use recorded selectors or re-detect questions
            
            return True
            
        except Exception as e:
            logger.error(f"Replay failed: {e}")
            return False
    
    def _log_unanswered_question(self, question, screenshot_path):
        """Log questions that don't have answers"""
        unanswered_file = Path('unanswered_questions.json')
        
        try:
            # Load existing
            if unanswered_file.exists():
                with open(unanswered_file, 'r', encoding='utf-8') as f:
                    unanswered = json.load(f)
            else:
                unanswered = []
            
            # Add new question
            unanswered.append({
                'timestamp': datetime.now().isoformat(),
                'question': question,
                'screenshot': screenshot_path
            })
            
            # Save
            with open(unanswered_file, 'w', encoding='utf-8') as f:
                json.dump(unanswered, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Logged unanswered question to {unanswered_file}")
            
        except Exception as e:
            logger.debug(f"Could not log unanswered question: {e}")
    
    def analyze_success_rate(self):
        """Analyze success rate of recorded actions"""
        if not self.actions:
            return None
        
        total = len(self.actions)
        successful = sum(1 for action in self.actions if action['success'])
        success_rate = (successful / total) * 100
        
        return {
            'total_actions': total,
            'successful': successful,
            'failed': total - successful,
            'success_rate': success_rate
        }
    
    def suggest_improvements(self):
        """Suggest improvements based on recorded failures"""
        failed_actions = [a for a in self.actions if not a['success']]
        
        if not failed_actions:
            return []
        
        suggestions = []
        
        # Analyze failed questions
        failed_questions = [a['question'] for a in failed_actions]
        
        suggestions.append({
            'type': 'missing_answers',
            'message': f"Found {len(failed_questions)} questions without answers",
            'questions': failed_questions[:5]  # First 5
        })
        
        # Analyze failed selectors
        failed_selectors = [a['selector_used'] for a in failed_actions if a['selector_used']]
        
        if failed_selectors:
            suggestions.append({
                'type': 'selector_issues',
                'message': f"These selectors failed: {set(failed_selectors)}"
            })
        
        return suggestions