"""
Database Manager - SQLite operations for job tracking
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for job tracking"""
    
    def __init__(self, db_file='naukri_jobs.db'):
        self.db_file = db_file
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database and create tables"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            cursor = self.conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT,
                    company TEXT,
                    title TEXT,
                    applied_date TEXT,
                    status TEXT
                )
            ''')
            
            self.conn.commit()
            logger.info(f"✅ Database initialized: {self.db_file}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def is_job_applied(self, job_id):
        """Check if job already applied"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT job_id FROM applied_jobs WHERE job_id = ?', (job_id,))
            return cursor.fetchone() is not None
        except:
            return False
    
    def add_applied_job(self, job_id, job_url='', company='', title='', status='applied'):
        """Add job to applied list"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO applied_jobs 
                (job_id, job_url, company, title, applied_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_id, job_url, company, title, datetime.now().isoformat(), status))
            
            self.conn.commit()
            logger.debug(f"Added job to database: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job: {e}")
            return False
    
    def get_applied_count(self):
        """Get total applied jobs count"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM applied_jobs')
            count = cursor.fetchone()[0]
            return count
        except:
            return 0
    
    def close(self):
        """Close database connection"""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Database connection closed")
            except:
                pass