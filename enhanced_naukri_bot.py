"""
Enhanced Naukri Bot with AI Intelligence - FIXED SELECTORS VERSION
Author: Fixed for Kaustubh Upadhyaya
Date: July 2025
"""

import sys
import os
import time
import logging
import json
import platform
from typing import List, Dict
import pandas as pd
from datetime import datetime

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import the fixed base bot
from Naukri_Edge import IntelligentNaukriBot
from intelligent_job_processor import IntelligentJobProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedNaukriBot(IntelligentNaukriBot):
    """Enhanced Naukri Bot with AI-powered job analysis - FIXED SELECTORS"""
    
    def __init__(self, config_file="enhanced_config.json"):
        # Initialize parent class
        super().__init__(config_file)
        
        # Initialize AI processor
        try:
            self.job_processor = IntelligentJobProcessor(config_file)
            logger.info("AI processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI processor: {e}")
            self.job_processor = None
        
        # Enhanced tracking
        self.applied_count = 0
        self.analyzed_count = 0
        self.max_applications = self.config['job_search']['max_applications_per_session']
        
        # Session statistics
        self.session_stats = {
            'ai_calls': 0,
            'fallback_scores': 0,
            'high_score_jobs': 0,
            'applications_sent': 0,
            'jobs_skipped': 0,
            'ai_failures': 0,
            'extraction_failures': 0
        }
        
        logger.info("Enhanced Naukri Bot initialized successfully!")
    
    def process_jobs_with_streaming_application(self):
        """Process jobs with AI analysis and immediate application"""
        
        # Verify authentication first
        if not self._verify_authentication():
            logger.error("❌ Not authenticated to Naukri!")
            return False
        
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        logger.info(f"🎯 Starting AI-powered job processing (max {self.max_applications} applications)")
        
        for keyword_index, keyword in enumerate(keywords):
            if self.applied_count >= self.max_applications:
                logger.info(f"✅ Reached application limit: {self.max_applications}")
                break
            
            logger.info(f"🔍 Processing keyword {keyword_index + 1}/{len(keywords)}: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                if self.applied_count >= self.max_applications:
                    break
                
                try:
                    # Navigate to search page
                    search_keyword = keyword.lower().replace(' ', '-')
                    search_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"
                    
                    logger.info(f"Page {page}/{pages_per_keyword}: {url}")
                    self.driver.get(url)
                    
                    # Wait for job cards to load
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector))
                        )
                    except TimeoutException:
                        logger.warning("Job cards did not load, trying anyway...")
                    
                    self.smart_delay(3, 5)
                    
                    # Get job cards
                    job_cards = self._get_job_cards_fixed()
                    logger.info(f"Found {len(job_cards)} job cards on page")
                    
                    if not job_cards:
                        logger.warning("No job cards found on page")
                        continue
                    
                    # Process each job card with timeout
                    for card_index, job_card in enumerate(job_cards):
                        if self.applied_count >= self.max_applications:
                            break
                        
                        try:
                            logger.info(f"🔍 Processing job card {card_index + 1}/{len(job_cards)}")
                            
                            # Extract job data with timeout and better error handling
                            job_data = self._extract_job_data_fixed(job_card, timeout=10)
                            if not job_data:
                                logger.warning(f"❌ Failed to extract data from card {card_index + 1}")
                                self.session_stats['extraction_failures'] += 1
                                continue
                            
                            self.analyzed_count += 1
                            logger.info(f"✅ Extracted: {job_data['title']} at {job_data['company']}")
                            
                            # AI Analysis with error handling
                            ai_result = self._analyze_job_with_ai(
                                job_data['description'],
                                job_data['title'],
                                job_data['company']
                            )
                            
                            self.session_stats['ai_calls'] += 1
                            if ai_result.get('fallback_used', False):
                                self.session_stats['fallback_scores'] += 1
                            
                            score = ai_result.get('total_score', 0)
                            should_apply = ai_result.get('should_apply', False)
                            
                            logger.info(f"🤖 AI Analysis: {job_data['title']} scored {score}/100")
                            
                            # Apply if score meets threshold
                            if should_apply and score >= 70:
                                logger.info(f"⭐ HIGH SCORE JOB: {job_data['title']} | Score: {score}/100")
                                self.session_stats['high_score_jobs'] += 1
                                
                                # Navigate to job and apply
                                if job_data.get('url') and self._apply_to_job_enhanced(job_data):
                                    self.applied_count += 1
                                    self.session_stats['applications_sent'] += 1
                                    logger.info(f"✅ Application #{self.applied_count} sent successfully!")
                                else:
                                    logger.error(f"❌ Application failed: {job_data['title']}")
                            else:
                                logger.info(f"⏭️  SKIPPED: {job_data['title']} | Score: {score}/100")
                                self.session_stats['jobs_skipped'] += 1
                            
                            # Rate limiting between jobs
                            self.smart_delay(2, 4)
                            
                        except Exception as card_error:
                            logger.error(f"Error processing job card {card_index + 1}: {card_error}")
                            self.session_stats['extraction_failures'] += 1
                            continue
                    
                except Exception as page_error:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {page_error}")
                    continue
        
        logger.info(f"🏁 AI session completed: {self.applied_count} applications sent, {self.analyzed_count} jobs analyzed")
        self._print_ai_session_summary()
        return self.applied_count > 0
    
    def _verify_authentication(self):
        """Verify if we're authenticated to Naukri"""
        try:
            # Check multiple authentication indicators
            auth_indicators = [
                ('.nI-gNb-drawer__icon', 'Profile menu icon'),
                ('.view-profile-wrapper', 'Profile wrapper'),
                ('[data-automation="profileDropdown"]', 'Profile dropdown'),
                ('.user-name', 'User name display')
            ]
            
            for selector, description in auth_indicators:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        logger.info(f"✅ Authentication verified using: {description}")
                        return True
                except NoSuchElementException:
                    continue
            
            # Check URL - if we're on login page, we're not authenticated
            current_url = self.driver.current_url.lower()
            if 'login' in current_url or 'nlogin' in current_url:
                logger.warning("❌ Currently on login page - not authenticated")
                return False
            
            # If no clear indicators, assume authenticated
            logger.info("✅ Authentication status unclear, proceeding...")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying authentication: {e}")
            return False
    
    def _get_job_cards_fixed(self):
        """FIXED: Get job cards using current Naukri selectors"""
        selectors_to_try = [
            '.srp-jobtuple-wrapper',  # Main selector
            '.jobTuple',              # Alternative
            '[data-job-id]',          # Data attribute
            '.job-tuple',             # Fallback
            '.result'                 # Generic
        ]
        
        for selector in selectors_to_try:
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if job_cards:
                    logger.debug(f"✅ Found {len(job_cards)} job cards using selector: {selector}")
                    return job_cards
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        logger.warning("❌ No job cards found with any selector")
        return []
    
    def _extract_job_data_fixed(self, job_card, timeout=10):
        """FIXED: Extract job data with current Naukri selectors and timeout"""
        start_time = time.time()
        
        try:
            job_data = {'title': '', 'company': '', 'url': '', 'description': ''}
            
            # UPDATED SELECTORS - Based on current Naukri structure
            
            # Title extraction - Multiple approaches
            title_found = False
            title_selectors = [
                # Try direct text first
                '.title',
                '.jobTuple-title', 
                '.job-title',
                'h3',
                '[data-automation="jobTitle"]',
                # Then try with links
                '.title a',
                '.jobTuple-title a',
                'h3 a'
            ]
            
            for selector in title_selectors:
                try:
                    if time.time() - start_time > timeout:
                        logger.warning("⏰ Title extraction timeout")
                        break
                        
                    elements = job_card.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 5:  # Valid title should be longer than 5 chars
                            job_data['title'] = text
                            
                            # Try to get URL if element is a link or contains a link
                            try:
                                if element.tag_name == 'a':
                                    job_data['url'] = element.get_attribute('href')
                                else:
                                    # Look for link within the element
                                    link = element.find_element(By.TAG_NAME, 'a')
                                    job_data['url'] = link.get_attribute('href')
                            except:
                                pass  # URL is optional
                            
                            title_found = True
                            logger.debug(f"✅ Title found with {selector}: {text}")
                            break
                    
                    if title_found:
                        break
                        
                except Exception as e:
                    logger.debug(f"Title selector {selector} failed: {e}")
                    continue
            
            # Company extraction
            company_found = False
            company_selectors = [
                '.subTitle',
                '.companyName', 
                '.company-name',
                '.employer',
                '.jobTuple-company',
                '[data-automation="companyName"]'
            ]
            
            for selector in company_selectors:
                try:
                    if time.time() - start_time > timeout:
                        logger.warning("⏰ Company extraction timeout")
                        break
                        
                    elements = job_card.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 2:  # Valid company should be longer than 2 chars
                            job_data['company'] = text
                            company_found = True
                            logger.debug(f"✅ Company found with {selector}: {text}")
                            break
                    
                    if company_found:
                        break
                        
                except Exception as e:
                    logger.debug(f"Company selector {selector} failed: {e}")
                    continue
            
            # Get full card text for AI analysis (this should always work)
            try:
                job_data['description'] = job_card.text.strip()
            except:
                job_data['description'] = f"Job at {job_data.get('company', 'Company')} for {job_data.get('title', 'Position')}"
            
            # Alternative approach if direct selectors fail
            if not title_found or not company_found:
                logger.warning("🔍 Direct selectors failed, trying alternative approach...")
                
                # Get all text from job card and try to parse it
                full_text = job_card.text
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                
                if lines:
                    # First non-empty line is often the title
                    if not title_found and lines:
                        potential_title = lines[0]
                        if len(potential_title) > 5 and len(potential_title) < 100:
                            job_data['title'] = potential_title
                            title_found = True
                            logger.debug(f"✅ Title from text parsing: {potential_title}")
                    
                    # Look for company in subsequent lines
                    if not company_found:
                        for line in lines[1:4]:  # Check next few lines
                            if any(indicator in line.lower() for indicator in ['pvt', 'ltd', 'inc', 'corp', 'technologies', 'systems', 'solutions']):
                                job_data['company'] = line
                                company_found = True
                                logger.debug(f"✅ Company from text parsing: {line}")
                                break
            
            # Final fallback - extract from URL or use generic names
            if not job_data['url']:
                try:
                    # Look for any link in the job card
                    links = job_card.find_elements(By.TAG_NAME, 'a')
                    for link in links:
                        href = link.get_attribute('href')
                        if href and 'job-listings' in href:
                            job_data['url'] = href
                            break
                except:
                    pass
            
            # Validate we have minimum required data
            if not job_data['title'] or len(job_data['title']) < 3:
                if job_data['description']:
                    # Use first meaningful line from description
                    lines = [line.strip() for line in job_data['description'].split('\n') if line.strip() and len(line) > 5]
                    if lines:
                        job_data['title'] = lines[0][:50]  # Limit length
                
            if not job_data['company'] or len(job_data['company']) < 2:
                job_data['company'] = "Company Name"
            
            # Final validation
            if job_data['title'] and job_data['company']:
                processing_time = time.time() - start_time
                logger.debug(f"✅ Data extraction completed in {processing_time:.1f}s")
                return job_data
            else:
                logger.warning(f"❌ Missing required fields - Title: '{job_data['title']}', Company: '{job_data['company']}'")
                return None
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Job data extraction failed after {processing_time:.1f}s: {e}")
            return None
    
    def _analyze_job_with_ai(self, job_description, job_title, company_name):
        """Analyze job with AI and fallback handling"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                if self.job_processor:
                    # Try AI analysis
                    ai_result = self.job_processor.process_job(
                        job_title=job_title,
                        job_description=job_description,
                        company_name=company_name
                    )
                    
                    if attempt > 0:
                        logger.info(f"✅ AI analysis succeeded on attempt {attempt + 1}")
                    
                    return ai_result
                else:
                    # No AI processor available
                    break
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                if "quota" in error_msg or "429" in error_msg:
                    logger.warning(f"🚫 AI quota exceeded on attempt {attempt + 1}")
                    self.session_stats['ai_failures'] += 1
                    
                    if attempt < max_retries - 1:
                        logger.info("⏱️  Waiting 30s for quota reset...")
                        time.sleep(30)
                        continue
                    else:
                        break
                elif "timeout" in error_msg or "connection" in error_msg:
                    logger.warning(f"🌐 Network error on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    else:
                        break
                else:
                    logger.error(f"❌ AI analysis error: {e}")
                    self.session_stats['ai_failures'] += 1
                    break
        
        # Fallback to keyword-based scoring
        logger.info(f"🔄 Using fallback scoring for {job_title}")
        fallback_score = self._enhanced_keyword_scoring(job_description)
        
        return {
            'total_score': fallback_score,
            'should_apply': fallback_score >= self.config['job_search']['min_job_score'],
            'match_level': 'fallback',
            'fallback_used': True,
            'reasoning': f'Fallback scoring due to AI failure. Score: {fallback_score}/100'
        }
    
    def _enhanced_keyword_scoring(self, job_text):
        """Enhanced fallback scoring system"""
        text_lower = job_text.lower()
        score = 0
        
        # Primary role keywords (high weight)
        primary_roles = [
            ('data engineer', 35),
            ('data engineering', 35),
            ('etl developer', 30),
            ('python developer', 25),
            ('analytics engineer', 30),
            ('sql developer', 20)
        ]
        
        for role, points in primary_roles:
            if role in text_lower:
                score += points
                break  # Only count highest match
        
        # Technology stack (medium weight)
        tech_stack = {
            'python': 8,
            'sql': 6,
            'airflow': 10,
            'aws': 8,
            'spark': 10,
            'kafka': 8,
            'snowflake': 8,
            'dbt': 10,
            'databricks': 8,
            'pandas': 6,
            'numpy': 5,
            'etl': 8
        }
        
        for tech, points in tech_stack.items():
            if tech in text_lower:
                score += points
        
        # Experience level matching (prefer 2-5 years)
        experience_matches = [
            (['2-5 years', '2-4 years', '3-5 years'], 20),
            (['1-3 years', '2-6 years', '1-4 years'], 15),
            (['0-2 years', '1-2 years', 'fresher'], 10),
            (['senior', 'lead', '5+ years', '6+ years'], -15)  # Penalty for senior roles
        ]
        
        for patterns, points in experience_matches:
            if any(pattern in text_lower for pattern in patterns):
                score += points
                break
        
        # Location preferences
        location_bonus = [
            ('bangalore', 10),
            ('bengaluru', 10),
            ('remote', 15),
            ('work from home', 15),
            ('wfh', 12),
            ('hybrid', 8)
        ]
        
        for location, points in location_bonus:
            if location in text_lower:
                score += points
        
        # Company type bonus
        if any(company in text_lower for company in ['product', 'startup', 'saas']):
            score += 5
        
        # Avoid certain patterns
        avoid_patterns = ['intern', 'trainee', 'associate consultant', 'manual testing']
        if any(pattern in text_lower for pattern in avoid_patterns):
            score -= 20
        
        return min(max(score, 0), 100)
    
    def _apply_to_job_enhanced(self, job_data):
        """Apply to job with enhanced error handling"""
        try:
            if not job_data.get('url'):
                logger.error("No job URL provided")
                return False
            
            # Navigate to job page
            logger.debug(f"Navigating to: {job_data['url']}")
            self.driver.get(job_data['url'])
            self.smart_delay(3, 5)
            
            # Use parent class application method
            success = self._apply_to_single_job(job_data['url'])
            
            if success:
                logger.info(f"✅ Successfully applied to: {job_data['title']}")
                return True
            else:
                logger.warning(f"❌ Failed to apply to: {job_data['title']}")
                return False
                
        except Exception as e:
            logger.error(f"Enhanced application error: {e}")
            return False
    
    def _print_ai_session_summary(self):
        """Print detailed AI session summary"""
        ai_success_rate = ((self.session_stats['ai_calls'] - self.session_stats['fallback_scores']) / max(self.session_stats['ai_calls'], 1)) * 100
        application_rate = (self.session_stats['applications_sent'] / max(self.analyzed_count, 1)) * 100
        
        summary = f"""
        ╔═══ ENHANCED NAUKRI BOT SESSION SUMMARY ═══
        ║ 🔍 Total Jobs Analyzed: {self.analyzed_count}
        ║ 🧠 AI Analysis Success: {self.session_stats['ai_calls'] - self.session_stats['fallback_scores']}/{self.session_stats['ai_calls']} ({ai_success_rate:.1f}%)
        ║ ⭐ High Score Jobs (70+): {self.session_stats['high_score_jobs']}
        ║ ✅ Applications Sent: {self.session_stats['applications_sent']}
        ║ ❌ Skipped (Low Score): {self.session_stats['jobs_skipped']}
        ║ 🔄 Fallback Scores Used: {self.session_stats['fallback_scores']}
        ║ 🚫 AI Failures: {self.session_stats['ai_failures']}
        ║ 📊 Extraction Failures: {self.session_stats['extraction_failures']}
        ║ 📈 Application Rate: {application_rate:.1f}%
        ╚═══════════════════════════════════════════
        """
        
        logger.info(summary)
    
    def enhanced_run(self):
        """Enhanced run method with AI processing"""
        try:
            print("🚀 Starting Enhanced Naukri Bot with AI Intelligence...")
            print("=" * 60)
            
            # Step 1: Setup WebDriver
            logger.info("📡 Phase 1: Setting up browser...")
            if not self.setup_driver():
                logger.error("❌ Failed to setup browser")
                return False
            
            # Step 2: Login to Naukri
            logger.info("🔐 Phase 2: Logging into Naukri...")
            if not self.login():
                logger.error("❌ Failed to login to Naukri")
                return False
            
            # Verify authentication
            if not self._verify_authentication():
                logger.error("❌ Authentication verification failed")
                return False
            
            logger.info("✅ Authentication successful!")
            
            # Step 3: AI-powered job processing
            logger.info("🧠 Phase 3: Starting AI-powered job processing...")
            success = self.process_jobs_with_streaming_application()
            
            if not success:
                logger.warning("⚠️ No applications were sent")
            
            # Step 4: Save enhanced results
            logger.info("💾 Phase 4: Saving enhanced results...")
            self.save_enhanced_results()
            
            print("\n" + "=" * 60)
            print("🎉 ENHANCED NAUKRI BOT SESSION COMPLETE")
            print("=" * 60)
            print(f"🔍 Jobs Analyzed: {self.analyzed_count}")
            print(f"🧠 AI Success Rate: {((self.session_stats['ai_calls'] - self.session_stats['fallback_scores']) / max(self.session_stats['ai_calls'], 1) * 100):.1f}%")
            print(f"✅ Applications Sent: {self.applied_count}")
            print(f"📈 Application Rate: {(self.applied_count / max(self.analyzed_count, 1) * 100):.1f}%")
            print("=" * 60)
            
            logger.info("🎉 Enhanced Naukri Bot session completed successfully!")
            return True
            
        except KeyboardInterrupt:
            logger.info("⏹️ Bot stopped by user")
            return False
        except Exception as e:
            logger.error(f"💥 Enhanced bot execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if hasattr(self, 'db_conn') and self.db_conn:
                self.db_conn.close()
            if self.driver:
                input("\nPress Enter to close browser...")
                self.driver.quit()
    
    def save_enhanced_results(self):
        """Save enhanced session results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Enhanced results with AI metrics
            enhanced_results = {
                'session_info': {
                    'timestamp': datetime.now().isoformat(),
                    'session_type': 'AI-Enhanced',
                    'config_file': 'enhanced_config.json'
                },
                'job_analysis': {
                    'total_jobs_analyzed': self.analyzed_count,
                    'ai_analysis_attempts': self.session_stats['ai_calls'],
                    'ai_analysis_success': self.session_stats['ai_calls'] - self.session_stats['fallback_scores'],
                    'fallback_scores_used': self.session_stats['fallback_scores'],
                    'ai_failures': self.session_stats['ai_failures'],
                    'extraction_failures': self.session_stats['extraction_failures']
                },
                'application_results': {
                    'high_score_jobs': self.session_stats['high_score_jobs'],
                    'applications_sent': self.session_stats['applications_sent'],
                    'jobs_skipped': self.session_stats['jobs_skipped'],
                    'success_rate': f"{(self.applied_count / max(self.analyzed_count, 1) * 100):.1f}%"
                },
                'ai_performance': {
                    'ai_success_rate': f"{((self.session_stats['ai_calls'] - self.session_stats['fallback_scores']) / max(self.session_stats['ai_calls'], 1) * 100):.1f}%",
                    'application_rate': f"{(self.applied_count / max(self.analyzed_count, 1) * 100):.1f}%"
                }
            }
            
            # Save enhanced results
            with open(f"enhanced_naukri_session_{timestamp}.json", 'w') as f:
                json.dump(enhanced_results, f, indent=2)
            
            logger.info(f"Enhanced results saved with timestamp: {timestamp}")
            
        except Exception as e:
            logger.error(f"Error saving enhanced results: {e}")

# Main execution
def main():
    """Main function with proper initialization sequence"""
    bot = None
    try:
        logger.info("🚀 Starting Enhanced Naukri Bot with AI Intelligence...")
        
        # Initialize enhanced bot
        bot = EnhancedNaukriBot()
        
        # Run enhanced workflow
        success = bot.enhanced_run()
        
        if success:
            print("\n✅ Enhanced Naukri Bot completed successfully!")
        else:
            print("\n❌ Enhanced Naukri Bot failed. Check logs for details.")
        
        return success
        
    except Exception as e:
        logger.error(f"💥 Fatal error in main: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()