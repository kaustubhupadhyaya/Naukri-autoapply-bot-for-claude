#!/usr/bin/env python3
"""
Intelligent Job Processor with Gemini AI - Complete Fixed Version
Author: Fixed for Kaustubh Upadhyaya
Date: July 2025
"""

import google.generativeai as genai
import json
import time
import logging
import re
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentJobProcessor:
    """
    Gemini-powered job scoring and analysis system for Data Engineering roles.
    Fixed version with improved rate limiting and error handling.
    """
    
    def __init__(self, config_file: str = "enhanced_config.json"):
        """Initialize with enhanced configuration."""
        self.config = self._load_config(config_file)
        self._setup_gemini()
        self.user_profile = self.config['user_profile']
        
        # Enhanced rate limiting for free tier
        self.last_api_call = 0
        self.min_delay_between_calls = 15  # Increased from 4 to 15 seconds for stability
        
        # Cache for processed jobs (avoid re-processing same jobs)
        self.processed_jobs_cache = {}
        
        # API call tracking
        self.api_calls_made = 0
        self.successful_calls = 0
        self.failed_calls = 0
        
    def _load_config(self, config_file: str) -> Dict:
        """Load enhanced configuration with Gemini API key."""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                logger.info("Enhanced configuration loaded successfully")
                return config
        except FileNotFoundError:
            logger.info("Creating enhanced configuration...")
            return self._create_enhanced_config(config_file)
    
    def _create_enhanced_config(self, config_file: str) -> Dict:
        """Create enhanced configuration with your details."""
        enhanced_config = {
            "credentials": {
                "email": "kaustubh.upadhyaya1@gmail.com",
                "password": "9880380081@kK"
            },
            "gemini_api_key": "AIzaSyBGXNcTgcjYjY34fvXaAnmulRbiCIAvvXI",
            "personal_info": {
                "firstname": "Kaustubh",
                "lastname": "Upadhyaya",
                "phone": "9880380081",
                "current_ctc": "13 LPA",
                "expected_ctc": "18 LPA",
                "notice_period": "Immediate"
            },
            "user_profile": {
                "name": "Kaustubh Upadhyaya",
                "experience_years": 2,
                "current_role": "Data Engineer at Eli Lilly",
                "core_skills": [
                    # Programming & Querying
                    "Python", "SQL", "Bash",
                    
                    # Data Engineering Tools  
                    "Apache Airflow", "Jenkins", "Great Expectations",
                    
                    # Databases
                    "PostgreSQL", "MySQL", "Oracle DB", "RDBMS",
                    
                    # Cloud & Storage
                    "AWS S3", "AWS EC2", "AWS Lambda", "AWS CloudWatch", 
                    "AWS Secrets Manager", "GCP",
                    
                    # Data Integration & APIs
                    "REST APIs", "JSON", "XML",
                    
                    # DevOps & Automation
                    "CI/CD Pipelines", "Kubernetes", "Unit Testing", 
                    "Data Validation", "ETL Development",
                    
                    # Data Architecture
                    "Schema Design", "Data Lakes", "Monitoring & Alerting"
                ],
                "learning_skills": ["DBT", "Databricks", "Spark", "Kafka", "Snowflake"],
                "preferred_roles": ["Data Engineer", "ETL Developer", "Analytics Engineer", "Python Developer"],
                "location_preference": ["Bangalore", "Remote", "Hybrid"],
                "target_company_types": ["Product", "Startup", "Mid-size", "Healthcare", "Fintech"],
                "avoid_companies": ["TCS", "Infosys", "Wipro", "Accenture", "Cognizant"]
            },
            "job_search": {
                "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "Analytics Engineer"],
                "location": "bengaluru",
                "max_applications_per_session": 20,  # Reduced for testing
                "min_job_score": 60,  # Apply to jobs scoring 60+/100
                "pages_per_keyword": 2  # Reduced for testing
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 15,
                "page_load_timeout": 45,
                "headless": False
            },
            "bot_behavior": {
                "min_delay": 3,
                "max_delay": 7,
                "typing_delay": 0.15,
                "scroll_pause": 3,
                "smart_delays": True,
                "random_scrolling": True
            },
            "gemini_settings": {
                "model": "gemini-1.5-flash",
                "temperature": 0.1,
                "max_tokens": 1000,
                "rate_limit_delay": 15  # Increased delay
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(enhanced_config, f, indent=4)
        
        logger.info(f"Enhanced config created at {config_file}")
        return enhanced_config
    
    def _setup_gemini(self):
        """Initialize Gemini API with enhanced error handling."""
        try:
            api_key = self.config.get('gemini_api_key')
            if not api_key:
                raise ValueError("Gemini API key not found in configuration")
            
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini API initialized successfully")
            
            # Test API connection
            self._test_api_connection()
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            raise
    
    def _test_api_connection(self):
        """Test Gemini API connection"""
        try:
            test_prompt = "Say 'API connected' if you receive this message."
            response = self.gemini_model.generate_content(test_prompt)
            if response and response.text:
                logger.info("✅ Gemini API connection test successful")
            else:
                logger.warning("⚠️ Gemini API test returned empty response")
        except Exception as e:
            logger.warning(f"⚠️ Gemini API test failed: {e}")
    
    def _rate_limit(self):
        """Enhanced rate limiting for Gemini free tier."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        # Free tier: 15 requests per minute = 4 seconds minimum
        # But for stability, use 15 seconds minimum delay
        if time_since_last_call < self.min_delay_between_calls:
            sleep_time = self.min_delay_between_calls - time_since_last_call
            logger.info(f"⏱️  Rate limiting: waiting {sleep_time:.1f}s for API stability...")
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()
    
    def process_job(self, job_title: str, job_description: str, company_name: str = "", job_url: str = "") -> Dict:
        """
        Main method: Process a job with both scoring and analysis.
        Returns comprehensive job evaluation with enhanced error handling.
        """
        # Check cache first
        job_key = f"{job_title}_{company_name}".lower().replace(" ", "_")
        if job_key in self.processed_jobs_cache:
            logger.debug(f"Using cached result for {job_title}")
            return self.processed_jobs_cache[job_key]
        
        # Rate limiting
        self._rate_limit()
        
        try:
            # Track API call
            self.api_calls_made += 1
            
            # Create comprehensive prompt for scoring and analysis
            prompt = self._create_comprehensive_prompt(job_title, job_description, company_name)
            
            # Get Gemini response with timeout
            logger.debug(f"Sending job analysis request for: {job_title}")
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.config['gemini_settings']['max_tokens'],
                    temperature=self.config['gemini_settings']['temperature']
                )
            )
            
            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")
            
            # Parse response
            result = self._parse_gemini_response(response.text, job_title, company_name, job_url)
            
            # Cache the result
            self.processed_jobs_cache[job_key] = result
            self.successful_calls += 1
            
            logger.debug(f"AI analysis completed for {job_title}: Score {result['total_score']}/100")
            
            return result
            
        except Exception as e:
            self.failed_calls += 1
            logger.error(f"Gemini API error for {job_title}: {e}")
            return self._create_fallback_result(job_title, company_name, job_url)
    
    def _create_comprehensive_prompt(self, job_title: str, job_description: str, company_name: str) -> str:
        """Create a comprehensive prompt for Gemini that handles both scoring and analysis."""
        
        user_skills_str = ", ".join(self.user_profile['core_skills'])
        learning_skills_str = ", ".join(self.user_profile['learning_skills'])
        
        prompt = f"""
You are an expert Data Engineering career advisor. Analyze this job opportunity for Kaustubh Upadhyaya, a Data Engineer with 2 years of experience.

**CANDIDATE PROFILE:**
- Name: {self.user_profile['name']}
- Experience: {self.user_profile['experience_years']} years
- Current Role: {self.user_profile['current_role']}
- Core Skills: {user_skills_str}
- Learning Skills: {learning_skills_str}
- Preferred Roles: {', '.join(self.user_profile['preferred_roles'])}
- Location Preference: {', '.join(self.user_profile['location_preference'])}

**JOB DETAILS:**
- Title: {job_title}
- Company: {company_name}
- Description: {job_description[:2000]}...

**ANALYSIS REQUIRED:**
Please provide a detailed analysis and return ONLY a valid JSON response with these exact fields:

{{
    "total_score": <integer 0-100>,
    "technology_score": <integer 0-30>,
    "experience_score": <integer 0-25>,
    "company_score": <integer 0-20>,
    "role_score": <integer 0-25>,
    "match_level": "<excellent|good|fair|poor>",
    "reasoning": "<brief explanation of scoring>",
    "key_matches": ["<list of matching skills/requirements>"],
    "concerns": ["<list of potential concerns>"],
    "application_recommendation": "<apply|consider|avoid>"
}}

**SCORING GUIDELINES:**
- Technology Score (0-30): Match between required tech stack and candidate's skills
- Experience Score (0-25): Alignment with 2-year experience level
- Company Score (0-20): Company quality and culture fit
- Role Score (0-25): Relevance to Data Engineering career path

**EXPERIENCE LEVEL MATCHING:**
- Perfect match: 2-5 years experience requirements
- Good match: 1-4 years or 3-6 years
- Poor match: 0-1 years (too junior) or 5+ years (too senior)

**TECHNOLOGY STACK PRIORITY:**
High Priority: Python, SQL, Airflow, AWS, ETL, Data Pipelines
Medium Priority: Spark, Kafka, Snowflake, DBT, PostgreSQL
Low Priority: Java, .NET, Manual Testing, Frontend technologies

**COMPANY TYPE PREFERENCES:**
Preferred: Product companies, Startups, Healthcare, Fintech
Avoid: Large service companies (TCS, Infosys, Wipro, Accenture)

For a 2-year experienced Data Engineer, perfect matches should score 75-90, good matches 60-75, average 45-60, poor matches below 45.

Return ONLY the JSON response, no additional text.
        """
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str, job_title: str, company_name: str, job_url: str) -> Dict:
        """Parse Gemini's JSON response into structured data with enhanced error handling."""
        try:
            # Clean response text
            response_text = response_text.strip()
            
            # Extract JSON from response (handle cases where there's extra text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                
                # Clean up common JSON issues
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)  # Remove control characters
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
                
                parsed_data = json.loads(json_str)
                
                # Validate and clean parsed data
                parsed_data = self._validate_and_clean_response(parsed_data)
                
                # Add metadata
                parsed_data.update({
                    'job_title': job_title,
                    'company_name': company_name,
                    'job_url': job_url,
                    'processed_at': time.time(),
                    'should_apply': parsed_data.get('total_score', 0) >= self.config['job_search']['min_job_score'],
                    'ai_processed': True
                })
                
                return parsed_data
            else:
                logger.warning(f"No JSON found in Gemini response for {job_title}")
                raise ValueError("No valid JSON in response")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {job_title}: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"Error processing Gemini response for {job_title}: {e}")
            raise
    
    def _validate_and_clean_response(self, data: Dict) -> Dict:
        """Validate and clean the parsed response data"""
        # Set defaults for required fields
        defaults = {
            'total_score': 0,
            'technology_score': 0,
            'experience_score': 0,
            'company_score': 0,
            'role_score': 0,
            'match_level': 'poor',
            'reasoning': 'AI analysis completed',
            'key_matches': [],
            'concerns': [],
            'application_recommendation': 'avoid'
        }
        
        # Apply defaults for missing fields
        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value
        
        # Validate score ranges
        score_fields = ['total_score', 'technology_score', 'experience_score', 'company_score', 'role_score']
        for field in score_fields:
            try:
                score = int(data[field])
                data[field] = max(0, min(100, score))  # Clamp to 0-100 range
            except (ValueError, TypeError):
                data[field] = 0
        
        # Validate match_level
        valid_levels = ['excellent', 'good', 'fair', 'poor']
        if data['match_level'] not in valid_levels:
            data['match_level'] = 'poor'
        
        # Validate application_recommendation
        valid_recommendations = ['apply', 'consider', 'avoid']
        if data['application_recommendation'] not in valid_recommendations:
            data['application_recommendation'] = 'avoid'
        
        # Ensure lists are actually lists
        list_fields = ['key_matches', 'concerns']
        for field in list_fields:
            if not isinstance(data[field], list):
                data[field] = []
        
        return data
    
    def _create_fallback_result(self, job_title: str, company_name: str, job_url: str) -> Dict:
        """Create a fallback result when Gemini processing fails."""
        # Simple keyword-based scoring as fallback
        fallback_score = self._simple_keyword_scoring(f"{job_title} {company_name}")
        
        return {
            'total_score': fallback_score,
            'technology_score': int(fallback_score * 0.4),
            'experience_score': 10,  # Neutral
            'company_score': 5,      # Neutral
            'role_score': int(fallback_score * 0.3),
            'match_level': 'fair' if fallback_score >= 50 else 'poor',
            'job_title': job_title,
            'company_name': company_name,
            'job_url': job_url,
            'should_apply': fallback_score >= self.config['job_search']['min_job_score'],
            'reasoning': f'Fallback scoring used due to AI processing failure. Score: {fallback_score}/100',
            'key_matches': ['Keyword-based analysis'],
            'concerns': ['AI analysis not available'],
            'application_recommendation': 'consider' if fallback_score >= 60 else 'avoid',
            'processed_at': time.time(),
            'fallback_used': True,
            'ai_processed': False
        }
    
    def _simple_keyword_scoring(self, job_text: str) -> int:
        """Enhanced keyword-based fallback scoring."""
        text_lower = job_text.lower()
        score = 0
        
        # Core role keywords
        core_roles = {
            'data engineer': 40,
            'etl developer': 35,
            'python developer': 30,
            'sql developer': 25,
            'analytics engineer': 35
        }
        
        for role, points in core_roles.items():
            if role in text_lower:
                score += points
                break
        
        # Technology keywords
        tech_keywords = {
            'python': 8,
            'sql': 6,
            'airflow': 10,
            'aws': 8,
            'spark': 8,
            'kafka': 6,
            'etl': 10,
            'data pipeline': 8
        }
        
        for tech, points in tech_keywords.items():
            if tech in text_lower:
                score += points
        
        # Location bonus
        if any(loc in text_lower for loc in ['bangalore', 'bengaluru', 'remote', 'hybrid']):
            score += 10
        
        # Company penalty for service companies
        service_companies = ['tcs', 'infosys', 'wipro', 'accenture', 'cognizant']
        if any(company in text_lower for company in service_companies):
            score -= 20
        
        return max(0, min(100, score))
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics"""
        return {
            'total_api_calls': self.api_calls_made,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'success_rate': f"{(self.successful_calls / max(self.api_calls_made, 1) * 100):.1f}%",
            'cached_results': len(self.processed_jobs_cache)
        }

# Test function
def test_job_processor():
    """Test the job processor with a sample job"""
    try:
        processor = IntelligentJobProcessor()
        
        # Test with sample job
        test_job = {
            'title': 'Data Engineer',
            'company': 'Test Company',
            'description': 'Looking for Data Engineer with Python, SQL, Airflow experience. 2-4 years experience required. Work with AWS, build ETL pipelines.'
        }
        
        print("🧪 Testing Intelligent Job Processor...")
        result = processor.process_job(
            test_job['title'],
            test_job['description'], 
            test_job['company']
        )
        
        print(f"✅ Test successful!")
        print(f"Score: {result['total_score']}/100")
        print(f"Recommendation: {result['application_recommendation']}")
        print(f"AI Processed: {result.get('ai_processed', False)}")
        
        # Print stats
        stats = processor.get_processing_stats()
        print(f"\n📊 Processing Stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_job_processor()