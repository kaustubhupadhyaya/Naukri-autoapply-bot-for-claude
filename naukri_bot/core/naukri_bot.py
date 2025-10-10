"""
Main Naukri Bot - Orchestrates all modules
"""

import logging
from datetime import datetime

from naukri_bot.core.webdriver_manager import WebDriverManager
from naukri_bot.modules.auth import AuthModule
from naukri_bot.modules.job_search import JobSearchModule
from naukri_bot.modules.application import ApplicationModule
from naukri_bot.utils.config_manager import ConfigManager
from naukri_bot.utils.database import DatabaseManager
from naukri_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


class NaukriBot:
    """
    Main Naukri Bot - Modular Architecture

    Orchestrates:
    - WebDriver management
    - Authentication
    - Job searching
    - Application submission
    - Session tracking
    """

    def __init__(self, config_file='config.json'):
        """Initialize bot with modular components"""
        logger.info("🤖 Initializing Naukri Bot (Modular Edition)...")

        # Load configuration
        self.config = ConfigManager.load_config(config_file)

        # Initialize database
        self.database = DatabaseManager()

        # Initialize WebDriver
        self.webdriver_manager = WebDriverManager(self.config)
        self.driver = self.webdriver_manager.create_driver()

        # Initialize modules
        self.auth = AuthModule(self.driver, self.config)
        self.job_search = JobSearchModule(self.driver, self.config, self.database)
        self.application = ApplicationModule(self.driver, self.config, self.database)

        # Initialize session manager
        self.session = SessionManager()

        logger.info("✅ Bot initialized successfully")

    def run(self):
        """
        Main execution flow
        Returns: True if successful, False otherwise
        """
        try:
            # Start session
            self.session.start_session()

            # Step 1: Login
            if not self.auth.login():
                logger.error("❌ Login failed, aborting")
                return False

            # Step 2: Search for jobs
            joblinks = self.job_search.search_jobs()

            if not joblinks:
                logger.warning("No jobs found")
                return False

            logger.info(f"\n🎯 Starting applications to {len(joblinks)} jobs...")

            # Step 3: Apply to jobs
            max_applications = self.config['job_search'].get('max_applications_per_session', 20)

            for index, job_url in enumerate(joblinks):
                if self.application.applied >= max_applications:
                    logger.info(f"✋ Reached application limit ({max_applications})")        
                    break

                logger.info(f"\n{'='*60}")
                logger.info(f"Job {index + 1}/{len(joblinks)}")
                logger.info(f"{'='*60}")

                # Apply to job
                success = self.application.apply_to_job(job_url)

                # Track in session
                status = 'applied' if success else 'failed'
                self.session.add_application(job_url, status)

            # Print summary
            self._print_summary()

            # Save session
            self.session.save_session()

            return True

        except KeyboardInterrupt:
            logger.info("\n⚠️ Bot interrupted by user")
            self._print_summary()
            self.session.save_session()
            return False

        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            return False

        finally:
            self.cleanup()

    def _print_summary(self):
        """Print session summary"""
        stats = self.application.get_statistics()

        total_processed = stats['applied'] + stats['failed']
        success_rate = (stats['applied'] / max(total_processed, 1)) * 100

        print("\n" + "=" * 60)
        print("🎉 SESSION COMPLETE")
        print("=" * 60)
        print(f"📊 Jobs Found: {len(self.job_search.joblinks)}")
        print(f"✅ Applications Sent: {stats['applied']}")
        print(f"❌ Applications Failed: {stats['failed']}")
        print(f"⭐ Jobs Skipped: {stats['skipped']}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        print("=" * 60)

    def cleanup(self):
        """Cleanup resources"""
        try:
            # Close database
            self.database.close()

            # Close browser
            if self.driver:
                try:
                    input("\nPress Enter to close browser...")
                except:
                    pass

                self.webdriver_manager.quit()

        except Exception as e:
            logger.debug(f"Cleanup error: {e}")


def main():
    """Entry point"""
    try:
        bot = NaukriBot()
        success = bot.run()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())