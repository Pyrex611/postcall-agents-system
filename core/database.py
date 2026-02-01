import sqlite3
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

# Database Connection Manager
class DatabaseManager:
    def __init__(self, db_name="salesops_enterprise.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        # Multi-tenant Organization Table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_key TEXT UNIQUE,
                crm_type TEXT DEFAULT 'sheets', -- 'salesforce', 'hubspot', 'sheets'
                crm_config JSON,
                methodology TEXT DEFAULT 'GENERIC' -- 'MEDDIC', 'SPIN', 'BANT'
            )
        ''')
        
        # Job/Call History Table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_jobs (
                id TEXT PRIMARY KEY,
                org_id INTEGER,
                rep_name TEXT,
                status TEXT, -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
                upload_time TIMESTAMP,
                transcript TEXT,
                analysis_result JSON,
                crm_sync_status TEXT,
                FOREIGN KEY(org_id) REFERENCES organizations(id)
            )
        ''')
        self.conn.commit()

    def create_org(self, name: str, crm_type: str, crm_config: dict, methodology: str):
        config_json = json.dumps(crm_config)
        self.cursor.execute(
            "INSERT INTO organizations (name, crm_type, crm_config, methodology) VALUES (?, ?, ?, ?)",
            (name, crm_type, config_json, methodology)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_org(self, org_id: int):
        self.cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return self.cursor.fetchone()

    def create_job(self, job_id: str, org_id: int, rep_name: str, transcript: str):
        self.cursor.execute(
            "INSERT INTO call_jobs (id, org_id, rep_name, status, upload_time, transcript) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, org_id, rep_name, "PENDING", datetime.now(), transcript)
        )
        self.conn.commit()

    def update_job(self, job_id: str, status: str, result: dict = None, crm_status: str = None):
        result_json = json.dumps(result) if result else None
        self.cursor.execute(
            "UPDATE call_jobs SET status = ?, analysis_result = ?, crm_sync_status = ? WHERE id = ?",
            (status, result_json, crm_status, job_id)
        )
        self.conn.commit()

    def get_org_jobs(self, org_id: int):
        self.cursor.execute("SELECT * FROM call_jobs WHERE org_id = ? ORDER BY upload_time DESC", (org_id,))
        return self.cursor.fetchall()

# Initialize Singleton
db = DatabaseManager()