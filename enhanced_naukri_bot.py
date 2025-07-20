import sys
import os
import time
import logging
from typing import List, Dict
import pandas as pd
from datetime import datetime

# Import the original NaukriBot
from Naukri_Edge import IntelligentNaukriBot
from intelligent_job_processor import IntelligentJobProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedNaukriBot(IntelligentNaukriBot):
    """
    Enhanced NaukriBot with Gemini-powered intelligent job processing.
    Inherits all functionality from original NaukriBot and adds AI intelligence.
    """
    
    def __init__(self, config_file="enhanced_config.json"):
        """Initialize enhanced bot with intelligent processor."""
        logger.info("🚀 Initializing Enhanced Naukri Bot with AI Intelligence...")
        
        # Initialize parent class (original NaukriBot)
        super().__init__(config_file)
        
        # Initialize intelligent job processor
        self.job_processor = IntelligentJobProcessor(config_file)
        
        # Enhanced tracking
        self.intelligent_stats = {
            'total_jobs_analyzed': 0,
            'high_score_jobs': 0,
            'applied_jobs': 0,
            'skipped_low_score': 0,
            'gemini_api_calls': 0,
            'fallback_scores': 0
        }
        
        # Job analysis results storage
        self.job_analysis_results = []
        
        logger.info("✅ Enhanced Naukri Bot initialized successfully!")
    
    def analyze_job_quality(self, job_card_text):
        """
        Override parent method with Gemini-powered intelligent analysis.
        This method is called by the parent class for each job card.
        """
        try:
            # Extract job details from card text
            job_title = self.extract_job_title_from_card(job_card_text)
            company_name = self.extract_company_name_from_card(job_card_text)
            
            # Use Gemini for intelligent analysis
            job_result = self.job_processor.process_job(
                job_title=job_title,
                job_description=job_card_text,
                company_name=company_name
            )
            
            # Update stats
            self._update_analysis_stats(job_result)
            
            # Store detailed results for later analysis
            self.job_analysis_results.append(job_result)
            
            # Return score for parent class compatibility
            total_score = job_result.get('total_score', 0)
            
            # Log intelligent analysis
            self._log_job_decision(job_result)
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error in intelligent job analysis: {e}")
            # Fallback to parent class method
            return super().analyze_job_quality(job_card_text)
    
    def extract_job_title_from_card(self, job_card_text):
        """Extract job title from job card text."""
        try:
            lines = job_card_text.split('\n')
            # Usually the first few lines contain the job title
            for line in lines[:3]:
                line = line.strip()
                if line and not any(skip_word in line.lower() for skip_word in ['company', 'location', 'experience', 'salary']):
                    return line
            return "Unknown Job Title"
        except:
            return "Unknown Job Title"
    
    def extract_company_name_from_card(self, job_card_text):
        """Extract company name from job card text."""
        try:
            lines = job_card_text.split('\n')
            # Look for company name in the card
            for line in lines:
                if any(indicator in line.lower() for indicator in ['company', 'pvt', 'ltd', 'inc', 'corp']):
                    return line.strip()
            # If not found, return second line as company name
            if len(lines) > 1:
                return lines[1].strip()
            return "Unknown Company"
        except:
            return "Unknown Company"
    
    def prioritize_jobs_intelligently(self, all_jobs):
        """
        Intelligently prioritize jobs based on Gemini analysis.
        This method can be called before applying to jobs.
        """
        logger.info("🧠 Prioritizing jobs with AI intelligence...")
        
        # Separate jobs by type and score
        data_engineering_jobs = []
        other_relevant_jobs = []
        
        for job in all_jobs:
            job_title = job.get('title', '').lower()
            job_score = job.get('quality_score', 0)
            
            # Categorize jobs
            if any(term in job_title for term in ['data engineer', 'etl', 'analytics engineer']):
                if job_score >= self.config['job_search']['min_job_score']:
                    data_engineering_jobs.append(job)
            else:
                if job_score >= self.config['job_search']['min_job_score']:
                    other_relevant_jobs.append(job)
        
        # Sort by score within each category
        data_engineering_jobs.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        other_relevant_jobs.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        # Allocate applications: 70% to data engineering, 30% to others
        max_applications = self.config['job_search']['max_applications_per_session']
        de_limit = int(max_applications * 0.7)
        other_limit = max_applications - de_limit
        
        prioritized_jobs = (
            data_engineering_jobs[:de_limit] + 
            other_relevant_jobs[:other_limit]
        )
        
        logger.info(f"📊 Prioritized {len(prioritized_jobs)} jobs: {len(data_engineering_jobs[:de_limit])} Data Engineering + {len(other_relevant_jobs[:other_limit])} Others")
        
        return prioritized_jobs
    
    def apply_to_jobs_intelligently(self):
        """
        Enhanced job application process with intelligent retry and error handling.
        """
        logger.info("🎯 Starting intelligent job application process...")
        
        # Filter jobs that meet our intelligent criteria
        qualified_jobs = [
            job for job in self.joblinks 
            if self._should_apply_to_job_url(job)
        ]
        
        logger.info(f"🔍 Found {len(qualified_jobs)} qualified jobs to apply to")
        
        max_applications = self.config['job_search']['max_applications_per_session']
        successful_applications = 0
        failed_applications = 0
        
        for i, job_url in enumerate(qualified_jobs[:max_applications], 1):
            if successful_applications >= max_applications:
                logger.info(f"✅ Reached application limit: {max_applications}")
                break
            
            try:
                logger.info(f"🎯 Applying to job {i}: {job_url}")
                
                # Enhanced application with retry logic
                success = self._apply_with_intelligence(job_url, i)
                
                if success:
                    successful_applications += 1
                    self.applied_list['passed'].append(job_url)
                    self.intelligent_stats['applied_jobs'] += 1
                    logger.info(f"✅ SUCCESS: {successful_applications}/{max_applications} applications sent")
                else:
                    failed_applications += 1
                    self.applied_list['failed'].append(job_url)
                    logger.info(f"❌ FAILED: {failed_applications} failures")
                
                # Smart delay between applications
                self.smart_delay(5, 10)
                
            except Exception as e:
                logger.error(f"💥 Unexpected error with job {i}: {e}")
                failed_applications += 1
                self.applied_list['failed'].append(job_url)
                
                # Browser recovery if needed
                if "target window already closed" in str(e):
                    logger.info("🔄 Attempting browser recovery...")
                    try:
                        self._recover_browser_session()
                    except:
                        logger.error("❌ Browser recovery failed")
                        break
                
                continue
        
        logger.info(f"🏁 Application session completed: {successful_applications} successful, {failed_applications} failed")
        self._save_intelligent_results()
    
    def _should_apply_to_job_url(self, job_url):
        """Check if we should apply to this job URL based on previous analysis."""
        # Find the job analysis result for this URL
        for result in self.job_analysis_results:
            if result.get('job_url') == job_url:
                return result.get('should_apply', False)
        
        # If not found in analysis, default to True (fallback)
        return True
    
    def _apply_with_intelligence(self, job_url, job_number):
        """Apply to job with enhanced error handling and retries."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                success = self.apply_to_job(job_url, job_number)
                if success:
                    return True
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️  Attempt {attempt + 1} failed: {error_msg}")
                
                if "target window already closed" in error_msg:
                    self._recover_browser_session()
                elif "element not found" in error_msg.lower():
                    time.sleep(5)  # Wait for page to load
                
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))  # Progressive delay
                else:
                    logger.error(f"❌ All {max_retries} attempts failed for {job_url}")
                    return False
        
        return False
    
    def _recover_browser_session(self):
        """Attempt to recover from browser errors."""
        try:
            logger.info("🔄 Recovering browser session...")
            
            # Close current browser
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            # Reinitialize browser
            self.setup_driver()
            self.login()
            
            logger.info("✅ Browser session recovered successfully")
            
        except Exception as e:
            logger.error(f"❌ Browser recovery failed: {e}")
            raise
    
    def _update_analysis_stats(self, job_result):
        """Update intelligent analysis statistics."""
        self.intelligent_stats['total_jobs_analyzed'] += 1
        self.intelligent_stats['gemini_api_calls'] += 1
        
        if job_result.get('fallback_used', False):
            self.intelligent_stats['fallback_scores'] += 1
        
        score = job_result.get('total_score', 0)
        if score >= 70:
            self.intelligent_stats['high_score_jobs'] += 1
        
        if not job_result.get('should_apply', False):
            self.intelligent_stats['skipped_low_score'] += 1
    
    def _log_job_decision(self, job_result):
        """Log the intelligent job decision."""
        score = job_result.get('total_score', 0)
        should_apply = job_result.get('should_apply', False)
        title = job_result.get('job_title', 'Unknown')
        
        if should_apply:
            logger.info(f"✅ WILL APPLY: {title} | Score: {score}/100")
        else:
            logger.info(f"❌ WILL SKIP: {title} | Score: {score}/100 (Below threshold)")
    
    def _save_intelligent_results(self):
        """Save detailed intelligent analysis results."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save detailed job analysis
            if self.job_analysis_results:
                df_analysis = pd.DataFrame(self.job_analysis_results)
                df_analysis.to_csv(f"intelligent_job_analysis_{timestamp}.csv", index=False)
                logger.info(f"📊 Detailed analysis saved to intelligent_job_analysis_{timestamp}.csv")
            
            # Save enhanced statistics
            stats_file = f"intelligent_stats_{timestamp}.json"
            import json
            with open(stats_file, 'w') as f:
                json.dump(self.intelligent_stats, f, indent=4)
            
            # Log final statistics
            self._log_final_statistics()
            
        except Exception as e:
            logger.error(f"Error saving intelligent results: {e}")
    
    def _log_final_statistics(self):
        """Log comprehensive session statistics."""
        stats = self.intelligent_stats
        
        logger.info(f"""
        ╔═══ ENHANCED NAUKRI BOT SESSION SUMMARY ═══
        ║ 🔍 Total Jobs Analyzed: {stats['total_jobs_analyzed']}
        ║ 🧠 Gemini API Calls: {stats['gemini_api_calls']}
        ║ ⭐ High Score Jobs (70+): {stats['high_score_jobs']}
        ║ ✅ Applications Sent: {stats['applied_jobs']}
        ║ ❌ Skipped (Low Score): {stats['skipped_low_score']}
        ║ 🔄 Fallback Scores Used: {stats['fallback_scores']}
        ║ 📈 Success Rate: {(stats['applied_jobs'] / max(stats['total_jobs_analyzed'], 1)) * 100:.1f}%
        ╚═══════════════════════════════════════════
        """)
        
    def scrape_job_links(self):
        """
        Enhanced method to scrape job links with intelligent analysis.
        Overrides the parent class method to add AI-powered job analysis.
        """
        logger.info("🔍 Starting enhanced job scraping with AI analysis...")
        
        try:
            # Use parent class method to get base job links
            super().scrape_job_links()
            
            if not self.joblinks:
                logger.warning("⚠️ No jobs found in initial scrape!")
                return
            
            logger.info(f"📊 Found {len(self.joblinks)} jobs for analysis")
            
            # Create a list to store analyzed jobs
            analyzed_jobs = []
            
            # Process each job with AI analysis
            for index, job_url in enumerate(self.joblinks, 1):
                try:
                    logger.info(f"🔍 Analyzing job {index}/{len(self.joblinks)}: {job_url}")
                    
                    # Open job in new tab
                    self.driver.execute_script("window.open('');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.driver.get(job_url)
                    time.sleep(2)  # Wait for page load
                    
                    # Extract job details
                    job_title = self.driver.find_element("css selector", ".jd-header-title").text.strip()
                    job_description = self.driver.find_element("css selector", ".job-desc").text.strip()
                    company_name = self.driver.find_element("css selector", ".jd-header-comp-name").text.strip()
                    
                    # Use AI to analyze job
                    job_result = self.job_processor.process_job(
                        job_title=job_title,
                        job_description=job_description,
                        company_name=company_name
                    )
                    
                    # Add URL to result
                    job_result['job_url'] = job_url
                    
                    # Store analysis results
                    self.job_analysis_results.append(job_result)
                    
                    # Update stats
                    self._update_analysis_stats(job_result)
                    
                    # Log decision
                    self._log_job_decision(job_result)
                    
                    # Close tab and switch back
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    
                    # Smart delay between jobs
                    self.smart_delay(1, 3)
                    
                except Exception as e:
                    logger.error(f"Error analyzing job {job_url}: {e}")
                    continue
            
            # Update joblinks with analyzed jobs that meet criteria
            self.joblinks = [
                job['job_url'] for job in self.job_analysis_results
                if job.get('should_apply', False)
            ]
            
            logger.info(f"✅ Job analysis complete. {len(self.joblinks)} jobs qualified for application")
            
        except Exception as e:
            logger.error(f"💥 Error in job scraping: {e}")
            raise

# Main execution
def main():
    """Main function to run the enhanced Naukri bot."""
    bot = None
    try:
        logger.info("🚀 Starting Enhanced Naukri Bot with AI Intelligence...")
        
        # Initialize enhanced bot
        bot = EnhancedNaukriBot()
        
        # CRITICAL: Use the original bot's proven workflow
        logger.info("📡 Phase 1: Setting up browser and logging in...")
        bot.setup_driver()  # ← This was missing!
        
        logger.info("🔐 Phase 2: Logging into Naukri...")  
        bot.login()         # ← This was missing!
        
        logger.info("📡 Phase 3: Scraping jobs with AI analysis...")
        bot.scrape_job_links()  # Now this will work with AI analysis
        
        if len(bot.joblinks) == 0:
            logger.warning("⚠️ No jobs found! Check if login was successful.")
            return
        
        logger.info("🎯 Phase 4: Applying to qualified jobs...")
        bot.apply_to_jobs()  # Use original method for now
        
        logger.info("💾 Phase 5: Saving results...")
        bot.save_results()
        bot._save_intelligent_results()
        
        logger.info("🎉 Enhanced Naukri Bot session completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            if bot and hasattr(bot, 'driver') and bot.driver:
                input("Press Enter to close browser...")
                bot.driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()