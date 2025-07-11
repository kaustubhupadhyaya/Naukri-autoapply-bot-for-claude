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
    Combines scoring and analysis in one efficient class.
    """
    
    def __init__(self, config_file: str = "enhanced_config.json"):
        """Initialize with enhanced configuration."""
        self.config = self._load_config(config_file)
        self._setup_gemini()
        self.user_profile = self.config['user_profile']
        
        # Rate limiting
        self.last_api_call = 0
        self.min_delay_between_calls = 4  # 4 seconds between calls (safe for free tier)
        
        # Cache for processed jobs (avoid re-processing same jobs)
        self.processed_jobs_cache = {}
        
    def _load_config(self, config_file: str) -> Dict:
        """Load enhanced configuration with Gemini API key."""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
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
                "max_applications_per_session": 50,
                "min_job_score": 50,  # Apply to jobs scoring 50+/100
                "pages_per_keyword": 3
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
                "model": "gemini-pro",
                "temperature": 0.1,
                "max_tokens": 1000,
                "rate_limit_delay": 4
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(enhanced_config, f, indent=4)
        
        logger.info(f"Enhanced config created at {config_file}")
        return enhanced_config
    
    def _setup_gemini(self):
        """Initialize Gemini API."""
        try:
            genai.configure(api_key=self.config['gemini_api_key'])
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')  # Updated model name
            logger.info("Gemini API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            raise
    
    def _rate_limit(self):
        """Ensure we don't exceed API rate limits."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.min_delay_between_calls:
            sleep_time = self.min_delay_between_calls - time_since_last_call
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()
    
    def process_job(self, job_title: str, job_description: str, company_name: str = "", job_url: str = "") -> Dict:
        """
        Main method: Process a job with both scoring and analysis.
        Returns comprehensive job evaluation.
        """
        # Check cache first
        job_key = f"{job_title}_{company_name}".lower().replace(" ", "_")
        if job_key in self.processed_jobs_cache:
            logger.debug(f"Using cached result for {job_title}")
            return self.processed_jobs_cache[job_key]
        
        # Rate limiting
        self._rate_limit()
        
        try:
            # Create comprehensive prompt for scoring and analysis
            prompt = self._create_comprehensive_prompt(job_title, job_description, company_name)
            
            # Get Gemini response
            response = self.gemini_model.generate_content(prompt)
            result = self._parse_gemini_response(response.text, job_title, company_name, job_url)
            
            # Cache the result
            self.processed_jobs_cache[job_key] = result
            
            logger.info(f"Processed: {job_title} | Score: {result['total_score']}/100 | Match: {result['match_level']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing job {job_title}: {e}")
            return self._create_fallback_result(job_title, company_name, job_url)
    
    def _create_comprehensive_prompt(self, job_title: str, job_description: str, company_name: str) -> str:
        """Create a comprehensive prompt for Gemini that handles both scoring and analysis."""
        
        user_skills_str = ", ".join(self.user_profile['core_skills'])
        learning_skills_str = ", ".join(self.user_profile['learning_skills'])
        
        prompt = f"""
        You are an expert Data Engineering career advisor. Analyze this job opportunity for Kaustubh Upadhyaya, a Data Engineer with 2 years of experience.

        JOB DETAILS:
        Title: {job_title}
        Company: {company_name}
        Description: {job_description}

        CANDIDATE PROFILE:
        • Experience: 2 years as Data Engineer at Eli Lilly & Company
        • Core Skills: {user_skills_str}
        • Learning Skills: {learning_skills_str}
        • Location: Bangalore (prefers Bangalore/Remote/Hybrid)
        • Target: Mid-level Data Engineering roles

        SCORING CRITERIA (Total: 100 points):

        1. TECHNOLOGY STACK MATCH (40 points max):
           - Big Data & Streaming Tools: Apache Spark, Kafka, Airflow, Hadoop (+15 each)
           - Cloud Platforms: AWS (S3, Lambda, etc.), Azure, GCP, Databricks (+12 each)
           - Databases: PostgreSQL, MySQL, Oracle, MongoDB, Redis (+10 each)
           - ETL/ELT Tools: DBT, Great Expectations, Informatica, Talend (+12 each)
           - Programming: Python, SQL, Bash, Java, Scala (+12 each)
           - DevOps: Jenkins, CI/CD, Kubernetes, Docker (+10 each)

        2. EXPERIENCE LEVEL FIT (30 points max):
           - Perfect Match: "2-5 years", "3-5 years", "Mid-level", "Associate" (+20)
           - Good Match: "1-3 years", "1-4 years", "2+ years" (+10)
           - Acceptable: "1-5 years", "0-3 years" (+5)
           - Avoid: "Senior", "Lead", "5+ years required" (-15)
           - Strongly Avoid: "Fresher only", "0-1 years", "Intern" (-25)

        3. COMPANY & ROLE QUALITY (20 points max):
           - Remote-Friendly: "Remote", "Hybrid", "WFH" (+10)
           - Product Companies: Better than service companies (+8)
           - Good Location: Bangalore, flexible location (+5)
           - Startup/Growth companies: Extra points (+5)

        4. ROLE RELEVANCE (10 points max):
           - Data Engineer roles: Perfect match (+10)
           - ETL/Analytics Engineer: Excellent (+8)
           - Python Developer with data: Good (+6)
           - Generic developer roles: Lower (+3)

        ANALYSIS REQUIREMENTS:
        Provide a detailed JSON response with:
        {{
            "total_score": [0-100],
            "technology_score": [0-40],
            "experience_score": [0-30], 
            "company_score": [0-20],
            "role_score": [0-10],
            "match_level": "excellent/good/fair/poor",
            "required_skills": ["skill1", "skill2"],
            "preferred_skills": ["skill1", "skill2"],
            "technologies_mentioned": ["tech1", "tech2"],
            "experience_requirement": "X-Y years",
            "location": "location",
            "remote_friendly": true/false,
            "company_type": "startup/product/service/enterprise",
            "application_recommendation": "strongly_recommend/recommend/consider/avoid",
            "reasoning": "Detailed explanation of score and recommendation",
            "skill_gaps": ["missing_skill1", "missing_skill2"],
            "growth_potential": "high/medium/low"
        }}

        Be precise with scoring. For a 2-year experienced Data Engineer, perfect matches should score 75-90, good matches 60-75, average 45-60, poor matches below 45.
        """
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str, job_title: str, company_name: str, job_url: str) -> Dict:
        """Parse Gemini's JSON response into structured data."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                
                # Add metadata
                parsed_data.update({
                    'job_title': job_title,
                    'company_name': company_name,
                    'job_url': job_url,
                    'processed_at': time.time(),
                    'should_apply': parsed_data.get('total_score', 0) >= self.config['job_search']['min_job_score']
                })
                
                return parsed_data
            else:
                logger.warning(f"No JSON found in Gemini response for {job_title}")
                return self._create_fallback_result(job_title, company_name, job_url)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {job_title}: {e}")
            return self._create_fallback_result(job_title, company_name, job_url)
    
    def _create_fallback_result(self, job_title: str, company_name: str, job_url: str) -> Dict:
        """Create a fallback result when Gemini processing fails."""
        # Simple keyword-based scoring as fallback
        fallback_score = self._simple_keyword_scoring(job_title)
        
        return {
            'total_score': fallback_score,
            'technology_score': fallback_score * 0.4,
            'experience_score': 10,  # Neutral
            'company_score': 5,      # Neutral
            'role_score': fallback_score * 0.1,
            'match_level': 'fair' if fallback_score >= 50 else 'poor',
            'job_title': job_title,
            'company_name': company_name,
            'job_url': job_url,
            'should_apply': fallback_score >= self.config['job_search']['min_job_score'],
            'reasoning': 'Fallback scoring due to API error',
            'application_recommendation': 'consider' if fallback_score >= 50 else 'avoid',
            'processed_at': time.time(),
            'fallback_used': True
        }
    
    def _simple_keyword_scoring(self, job_text: str) -> int:
        """Simple keyword-based fallback scoring."""
        job_text_lower = job_text.lower()
        score = 0
        
        # Data Engineering keywords
        if any(word in job_text_lower for word in ['data engineer', 'etl', 'pipeline']):
            score += 30
        
        # Technology keywords
        tech_keywords = ['python', 'sql', 'airflow', 'aws', 'postgresql', 'spark', 'kafka']
        for keyword in tech_keywords:
            if keyword in job_text_lower:
                score += 5
        
        # Experience level
        if any(word in job_text_lower for word in ['2-5', '3-5', 'mid', 'associate']):
            score += 20
        elif any(word in job_text_lower for word in ['senior', 'lead', '5+']):
            score -= 10
        
        return min(score, 100)
    
    def should_apply_to_job(self, job_result: Dict) -> bool:
        """Determine if we should apply to this job based on score and criteria."""
        return job_result.get('should_apply', False)
    
    def get_application_priority(self, job_result: Dict) -> str:
        """Get application priority level."""
        score = job_result.get('total_score', 0)
        
        if score >= 80:
            return 'high'
        elif score >= 65:
            return 'medium'
        elif score >= 50:
            return 'low'
        else:
            return 'skip'
    
    def log_job_analysis(self, job_result: Dict):
        """Log detailed job analysis for debugging and tracking."""
        logger.info(f"""
        ╔═══ JOB ANALYSIS ═══
        ║ Title: {job_result.get('job_title', 'N/A')}
        ║ Company: {job_result.get('company_name', 'N/A')}
        ║ Total Score: {job_result.get('total_score', 0)}/100
        ║ Tech Score: {job_result.get('technology_score', 0)}/40
        ║ Experience Score: {job_result.get('experience_score', 0)}/30
        ║ Company Score: {job_result.get('company_score', 0)}/20
        ║ Role Score: {job_result.get('role_score', 0)}/10
        ║ Match Level: {job_result.get('match_level', 'N/A')}
        ║ Should Apply: {job_result.get('should_apply', False)}
        ║ Priority: {self.get_application_priority(job_result)}
        ║ Reasoning: {job_result.get('reasoning', 'N/A')[:100]}...
        ╚═══════════════════
        """)


# Example usage and testing
if __name__ == "__main__":
    # Initialize processor
    processor = IntelligentJobProcessor()
    
    # Test with sample job data
    sample_job = {
        'title': 'Data Engineer - Python & AWS',
        'description': '''
        We are looking for a Data Engineer with 2-4 years of experience to join our team.
        
        Requirements:
        - Strong experience with Python and SQL
        - Experience with Apache Airflow for pipeline orchestration
        - Knowledge of AWS services (S3, Lambda, Glue)
        - Experience with PostgreSQL and data warehousing
        - Great Expectations for data validation
        
        Preferred:
        - Experience with Apache Spark
        - Knowledge of Kubernetes
        - DBT experience
        
        This is a hybrid role based in Bangalore.
        ''',
        'company': 'TechCorp Solutions'
    }
    
    # Process the job
    result = processor.process_job(
        sample_job['title'], 
        sample_job['description'], 
        sample_job['company']
    )
    
    # Log analysis
    processor.log_job_analysis(result)
    
    # Check if we should apply
    if processor.should_apply_to_job(result):
        print(f"✅ APPLY: {result['application_recommendation']}")
    else:
        print(f"❌ SKIP: Score too low ({result['total_score']}/100)")