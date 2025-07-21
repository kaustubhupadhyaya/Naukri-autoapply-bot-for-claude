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
    def __init__(self, config_file="enhanced_config.json"):
        super().__init__(config_file)
        self.job_processor = IntelligentJobProcessor(config_file)
        self.applied_count = 0
        self.analyzed_count = 0
        self.max_applications = self.config['job_search']['max_applications_per_session']
        
    def process_jobs_with_streaming_application(self):
        """Process jobs one by one and apply immediately to good ones"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        logger.info(f"🎯 Starting streaming job processing (max {self.max_applications} applications)")
        
        for keyword_index, keyword in enumerate(keywords):
            if self.applied_count >= self.max_applications:
                logger.info(f"✅ Reached application limit: {self.max_applications}")
                break
                
            logger.info(f"🔍 Processing keyword {keyword_index + 1}/{len(keywords)}: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                if self.applied_count >= self.max_applications:
                    break
                    
                try:
                    # Build URL and navigate
                    clean_keyword = keyword.lower().replace(' ', '-')
                    clean_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_location}-{page}"
                    
                    logger.info(f"📄 Processing page {page}/{pages_per_keyword}: {url}")
                    self.driver.get(url)
                    self.smart_delay(4, 7)
                    
                    # Process jobs on this page immediately
                    jobs_processed = self._process_jobs_on_current_page()
                    
                    if jobs_processed == 0:
                        logger.warning(f"No jobs found on page {page}, might be end of results")
                        break
                        
                    logger.info(f"📊 Page {page} complete: {jobs_processed} jobs processed, {self.applied_count} total applications")
                    
                except Exception as e:
                    logger.error(f"Error processing page {page} for '{keyword}': {e}")
                    continue
                    
                self.smart_delay(3, 6)
            
            self.smart_delay(5, 8)  # Delay between keywords
        
        logger.info(f"🏁 Streaming processing complete: {self.applied_count} applications sent, {self.analyzed_count} jobs analyzed")
        return self.applied_count > 0

    def _process_jobs_on_current_page(self):
        """Process each job on current page and apply immediately if good score"""
        jobs_processed = 0
        
        try:
            # Wait for job listings to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector))
            )
            
            # Scroll to load content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            self.smart_delay(2, 3)
            
            # Get all job cards on current page
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, self.job_card_selector)
            logger.info(f"📋 Found {len(job_cards)} job cards on page")
            
            for i, card in enumerate(job_cards):
                if self.applied_count >= self.max_applications:
                    logger.info(f"🛑 Reached application limit during page processing")
                    break
                    
                try:
                    # Extract basic job info
                    job_id = card.get_attribute('data-job-id')
                    if job_id in self.processed_jobs or self.is_job_already_applied(job_id):
                        continue
                    
                    title_element = card.find_element(By.CSS_SELECTOR, self.job_title_selector)
                    job_url = title_element.get_attribute('href')
                    job_title = title_element.get_attribute('title') or title_element.text
                    
                    if not job_url or not job_id:
                        continue
                    
                    # IMMEDIATE AI ANALYSIS
                    logger.info(f"🧠 Analyzing job {i+1}: {job_title}")
                    job_score = self.analyze_job_quality(card.text)
                    self.analyzed_count += 1
                    
                    # IMMEDIATE APPLICATION if good score
                    if job_score >= self.config['job_search']['min_job_score']:
                        logger.info(f"🎯 APPLYING IMMEDIATELY: {job_title} | Score: {job_score}/100")
                        
                        success = self._apply_to_job_immediately(job_url, job_title, job_score)
                        
                        if success:
                            self.applied_count += 1
                            self.applied_list['passed'].append(job_url)
                            logger.info(f"✅ SUCCESS: {self.applied_count}/{self.max_applications} applications sent")
                        else:
                            self.failed += 1
                            self.applied_list['failed'].append(job_url)
                            logger.info(f"❌ FAILED: {self.failed} failures")
                        
                        # Add to processed jobs
                        self.processed_jobs.add(job_id)
                        jobs_processed += 1
                        
                        # Smart delay between applications
                        self.smart_delay(8, 12)
                        
                    else:
                        logger.info(f"⏭️  SKIP: {job_title} | Score: {job_score}/100 (Below {self.config['job_search']['min_job_score']})")
                        self.skipped += 1
                        
                    # Small delay between job analyses
                    self.smart_delay(1, 2)
                    
                except Exception as e:
                    logger.warning(f"Error processing job {i+1}: {e}")
                    continue
            
            return jobs_processed
            
        except Exception as e:
            logger.error(f"Error processing jobs on page: {e}")
            return 0

    def _apply_to_job_immediately(self, job_url, job_title, job_score):
        """Apply to a single job immediately with enhanced error handling"""
        try:
            logger.info(f"📝 Applying to: {job_title}")
            
            # Navigate to job page
            self.driver.get(job_url)
            self.smart_delay(3, 5)
            
            # Check if already applied
            page_source = self.driver.page_source.lower()
            if any(indicator in page_source for indicator in ['already applied', 'application sent']):
                logger.info("ℹ️  Already applied to this job")
                return True  # Count as success since we would have applied
            
            # Find and click apply button
            for selector in self.apply_button_selectors:
                try:
                    apply_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Scroll to button and click
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                    self.smart_delay(1, 2)
                    
                    try:
                        apply_button.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", apply_button)
                    
                    logger.info(f"✅ Apply button clicked using: {selector}")
                    
                    # Handle any forms
                    self.smart_delay(2, 4)
                    self.handle_application_form()
                    
                    logger.info("✅ Application completed successfully")
                    return True
                    
                except Exception:
                    continue
            
            logger.warning("❌ Could not find apply button")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error applying to job: {e}")
            return False

    def analyze_job_quality(self, job_card_text):
        """Enhanced analyze with rate limit handling"""
        try:
            # Extract job details
            job_title = self.extract_job_title_from_card(job_card_text)
            company_name = self.extract_company_name_from_card(job_card_text)
            
            # Try AI analysis with rate limit handling
            try:
                job_result = self.job_processor.process_job(
                    job_title=job_title,
                    job_description=job_card_text,
                    company_name=company_name
                )
                
                score = job_result.get('total_score', 0)
                logger.info(f"🤖 AI Score: {score}/100 | {job_result.get('match_level', 'unknown')}")
                return score
                
            except Exception as ai_error:
                # Graceful fallback to simple scoring
                if "quota" in str(ai_error).lower() or "429" in str(ai_error):
                    logger.warning(f"🚫 API quota exceeded, using fallback scoring")
                else:
                    logger.warning(f"🚫 AI analysis failed: {ai_error}")
                
                # Use simple keyword scoring as fallback
                fallback_score = self._simple_keyword_scoring(job_card_text)
                logger.info(f"📊 Fallback Score: {fallback_score}/100")
                return fallback_score
                
        except Exception as e:
            logger.error(f"Error in job analysis: {e}")
            return 0

    def _simple_keyword_scoring(self, job_text):
        """Simple fallback scoring when AI fails"""
        job_text_lower = job_text.lower()
        score = 0
        
        # Data Engineering keywords
        if any(word in job_text_lower for word in ['data engineer', 'etl', 'pipeline']):
            score += 40
        
        # Technology keywords  
        tech_keywords = ['python', 'sql', 'airflow', 'aws', 'spark', 'kafka']
        for keyword in tech_keywords:
            if keyword in job_text_lower:
                score += 8
        
        # Experience level (prefer 2-5 years)
        if any(word in job_text_lower for word in ['2-5', '3-5', 'mid', 'associate']):
            score += 25
        elif any(word in job_text_lower for word in ['senior', 'lead', '5+', '7+']):
            score -= 20
        
        return min(score, 100)
# Main execution
def main():
    """Main function with proper initialization sequence - FIXED VERSION"""
    bot = None
    try:
        logger.info("🚀 Starting Enhanced Naukri Bot with AI Intelligence...")
        
        # Initialize bot
        bot = EnhancedNaukriBot()
        logger.info("✅ Enhanced Naukri Bot initialized successfully!")
        
        # CRITICAL FIX: Add missing setup and login sequence
        logger.info("📡 Phase 1: Setting up browser and logging in...")
        
        # Setup browser (was missing!)
        logger.info("Setting up browser...")
        if not bot.setup_driver():
            logger.error("❌ Failed to setup browser")
            return False
        
        # Login to Naukri (was missing!)  
        logger.info("🔐 Phase 2: Logging into Naukri...")
        if not bot.login():
            logger.error("❌ Failed to login to Naukri")
            return False
            
        # Add verification that we're logged in
        try:
            bot.driver.find_element(By.CLASS_NAME, "nI-gNb-drawer__icon")
            logger.info("✅ Login verification successful")
        except:
            logger.error("❌ Login verification failed")
            return False
        
        # Now we can safely process jobs
        logger.info("📡 Phase 3: Scraping jobs with AI analysis...")
        success = bot.process_jobs_with_streaming_application()
        
        if not success:
            logger.warning("⚠️ No applications were sent")
        
        # Save results
        logger.info("💾 Phase 4: Saving results...")
        bot.save_results()
        
        logger.info("🎉 Enhanced Naukri Bot session completed successfully!")
        return True
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
        return False
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if bot and hasattr(bot, 'driver') and bot.driver:
            input("Press Enter to close browser...")
            bot.driver.quit()

if __name__ == "__main__":
    main()