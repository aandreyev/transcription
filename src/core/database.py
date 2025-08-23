import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from src.utils import ConfigManager, log_error, log_info

class Database:
    def __init__(self):
        self.config = ConfigManager()
        self.db_path = self.config.get("DATABASE_URL", "sqlite:///data/audio_processor.db").replace("sqlite:///", "")
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    transcript_length INTEGER,
                    output_file TEXT,
                    original_filename TEXT,
                    suggested_filename TEXT,
                    final_filename TEXT,
                    naming_confidence REAL,
                    manual_override BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            ''')
            
            # Configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            log_info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            log_error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def create_job(self, filename: str, file_path: str) -> int:
        """Create a new job record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO jobs (filename, file_path, original_filename)
                VALUES (?, ?, ?)
            ''', (filename, file_path, filename))
            job_id = cursor.lastrowid
            conn.commit()
            log_info(f"Created job {job_id} for file: {filename}")
            return job_id
    
    def update_job_status(self, job_id: int, status: str, error_message: Optional[str] = None):
        """Update job status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            update_fields = ["status = ?"]
            params = [status]
            
            if status == 'processing':
                update_fields.append("started_at = ?")
                params.append(datetime.now())
            elif status in ['completed', 'failed']:
                update_fields.append("completed_at = ?")
                params.append(datetime.now())
            
            if error_message:
                update_fields.append("error_message = ?")
                params.append(error_message)
            
            params.append(job_id)
            
            cursor.execute(f'''
                UPDATE jobs SET {", ".join(update_fields)}
                WHERE id = ?
            ''', params)
            conn.commit()
            log_info(f"Updated job {job_id} status to: {status}", job_id)
    
    def update_job_transcript(self, job_id: int, transcript_length: int):
        """Update job with transcript information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs SET transcript_length = ?
                WHERE id = ?
            ''', (transcript_length, job_id))
            conn.commit()
    
    def update_job_output(self, job_id: int, output_file: str):
        """Update job with output file information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs SET output_file = ?
                WHERE id = ?
            ''', (output_file, job_id))
            conn.commit()
    
    def update_job_naming(self, job_id: int, suggested_filename: str, 
                         final_filename: str, confidence: float, manual_override: bool = False):
        """Update job with naming information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs SET 
                    suggested_filename = ?,
                    final_filename = ?,
                    naming_confidence = ?,
                    manual_override = ?
                WHERE id = ?
            ''', (suggested_filename, final_filename, confidence, manual_override, job_id))
            conn.commit()
    
    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_jobs(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get jobs with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM jobs'
            params = []
            
            if status:
                query += ' WHERE status = ?'
                params.append(status)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent jobs"""
        return self.get_jobs(limit=limit)
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get job statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total jobs
            cursor.execute('SELECT COUNT(*) as total FROM jobs')
            total = cursor.fetchone()['total']
            
            # Jobs by status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM jobs 
                GROUP BY status
            ''')
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Jobs today
            cursor.execute('''
                SELECT COUNT(*) as today 
                FROM jobs 
                WHERE DATE(created_at) = DATE('now')
            ''')
            today = cursor.fetchone()['today']
            
            # Success rate
            completed = status_counts.get('completed', 0)
            failed = status_counts.get('failed', 0)
            success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
            
            return {
                'total': total,
                'status_counts': status_counts,
                'today': today,
                'success_rate': round(success_rate, 1)
            }
    
    def log_message(self, job_id: Optional[int], level: str, message: str):
        """Log a message to the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO logs (job_id, level, message)
                VALUES (?, ?, ?)
            ''', (job_id, level, message))
            conn.commit()
    
    def get_logs(self, job_id: Optional[int] = None, level: Optional[str] = None, 
                limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get logs with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM logs'
            params = []
            conditions = []
            
            if job_id:
                conditions.append('job_id = ?')
                params.append(job_id)
            
            if level:
                conditions.append('level = ?')
                params.append(level)
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_jobs(self, days: int = 90):
        """Clean up old job records"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM jobs 
                WHERE created_at < datetime('now', '-{} days')
            '''.format(days))
            deleted = cursor.rowcount
            conn.commit()
            log_info(f"Cleaned up {deleted} old job records")
            return deleted
