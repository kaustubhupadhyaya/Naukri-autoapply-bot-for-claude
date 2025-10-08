"""
Configuration Manager - Loads and validates configuration
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and validation"""
    
    @staticmethod
    def load_config(config_file='config.json'):
        """Load configuration from file"""
        if not Path(config_file).exists():
            logger.warning(f"Config file not found: {config_file}")
            return ConfigManager._create_default_config(config_file)
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            logger.info(f"✅ Configuration loaded from {config_file}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return ConfigManager._create_default_config(config_file)
    
    @staticmethod
    def _create_default_config(config_file):
        """Create default configuration file"""
        default_config = {
            "credentials": {
                "email": "YOUR_EMAIL_HERE",
                "password": "YOUR_PASSWORD_HERE"
            },
            "personal_info": {
                "firstname": "YOUR_FIRSTNAME",
                "lastname": "YOUR_LASTNAME",
                "phone": "YOUR_PHONE",
                "current_ctc": "12 LPA",
                "expected_ctc": "18 LPA",
                "notice_period": "30 days"
            },
            "job_search": {
                "keywords": ["Python Developer", "Data Engineer"],
                "location": "Bangalore",
                "experience": "2",
                "max_applications_per_session": 20,
                "pages_per_keyword": 3
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 10,
                "page_load_timeout": 30,
                "headless": False
            },
            "bot_behavior": {
                "min_delay": 0.5,
                "max_delay": 1.0,
                "typing_delay": 0.05
            },
            "chatbot_answers": {
                "experience": "5",
                "notice_period": "30",
                "current_ctc": "15",
                "expected_ctc": "20",
                "default_answer": "Yes"
            },
            "gemini_api_key": ""
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        
        logger.warning("❗ Created default config.json - Please update credentials!")
        return default_config