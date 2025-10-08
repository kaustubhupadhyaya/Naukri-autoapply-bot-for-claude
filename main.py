"""Main Entry Point for Naukri Bot"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'naukri_bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

from naukri_bot.core.naukri_bot import NaukriBot


def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║         NAUKRI AUTO-APPLY BOT (Modular Edition)      ║
    ║                                                      ║
    ║  Features:                                           ║
    ║  ✅ Smart Chatbot Handling (Tier 1 Complete)        ║
    ║  ✅ Q&A Dictionary Learning                         ║
    ║  ✅ Multiple Question Detection Strategies          ║
    ║  ✅ Radio Button & Dropdown Support                 ║
    ║  ✅ Gemini AI Integration                           ║
    ║  ✅ Modular Architecture                            ║
    ║                                                      ║
    ║  Author: Your Name                                   ║
    ║  Version: 2.0 (Modular)                             ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    try:
        bot = NaukriBot()
        success = bot.run()
        
        if success:
            print("\n✅ Bot completed successfully!")
            return 0
        else:
            print("\n❌ Bot encountered errors")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
