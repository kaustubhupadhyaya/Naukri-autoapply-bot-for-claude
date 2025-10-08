"""
Session Manager - Handles session save/restore
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session data and reports"""
    
    def __init__(self):
        self.session_file = None
        self.session_data = {}
    
    def start_session(self):
        """Start new session"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_file = Path('sessions') / f'naukri_session_{timestamp}.json'
        self.session_file.parent.mkdir(exist_ok=True)
        
        self.session_data = {
            'start_time': datetime.now().isoformat(),
            'applied': [],
            'failed': [],
            'skipped': []
        }
        
        logger.info(f"📝 Session started: {self.session_file}")
    
    def add_application(self, job_url, status, details=None):
        """
        Add application to session
        status: 'applied', 'failed', 'skipped'
        """
        entry = {
            'url': job_url,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        
        if status in self.session_data:
            self.session_data[status].append(entry)
    
    def save_session(self):
        """Save session to file"""
        if not self.session_file:
            return
        
        try:
            self.session_data['end_time'] = datetime.now().isoformat()
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Session saved: {self.session_file}")
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def load_session(self, session_file):
        """Load previous session"""
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                self.session_data = json.load(f)
            
            logger.info(f"✅ Session loaded: {session_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
    
    def generate_report(self):
        """Generate session report"""
        total_applied = len(self.session_data.get('applied', []))
        total_failed = len(self.session_data.get('failed', []))
        total_skipped = len(self.session_data.get('skipped', []))
        total_processed = total_applied + total_failed
        
        success_rate = (total_applied / max(total_processed, 1)) * 100
        
        report = f"""
╔══════════════════════════════════════════════════════╗
║           NAUKRI BOT - SESSION REPORT                ║
╠══════════════════════════════════════════════════════╣
║ Start Time:       {self.session_data.get('start_time', 'N/A')[:19]}      ║
║ End Time:         {self.session_data.get('end_time', 'N/A')[:19]}      ║
╠══════════════════════════════════════════════════════╣
║ ✅ Applications Sent:     {total_applied:4d}                    ║
║ ❌ Applications Failed:   {total_failed:4d}                    ║
║ ⏭️  Jobs Skipped:          {total_skipped:4d}                    ║
║ 📈 Success Rate:          {success_rate:5.1f}%                  ║
╚══════════════════════════════════════════════════════╝
        """
        
        return report