"""SQLite-based Run Store for persistent run metadata.

D-03, D-04: Persistence layer for run tracking, retry recording, artifact linkage.
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.config import settings
from src.models.campaign_models import CampaignRequest, RunID, RunMetadata


class RunStore:
    """SQLite persistence layer for run metadata.
    
    Provides CRUD operations for runs and artifacts with foreign key constraints.
    """
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize RunStore with database path.
        
        Args:
            db_path: Path to SQLite database. Defaults to output_dir/runs.db
        """
        self.db_path = db_path or settings.output_dir / "runs.db"
        self._conn: Optional[sqlite3.Connection] = None
        self.init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Lazy connection getter with row factory."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn
    
    def init_db(self) -> None:
        """Idempotent schema initialization.
        
        Creates runs and artifacts tables if they don't exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_count INTEGER NOT NULL DEFAULT 0,
                terminal_failure_reason TEXT,
                parent_run_id TEXT,
                config_snapshot TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (parent_run_id) REFERENCES runs(run_id)
            )
        """)
        
        # Create artifacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                saved_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id)")
        
        conn.commit()
    
    def create_run(
        self,
        run_id: RunID,
        request: CampaignRequest,
        parent_run_id: Optional[RunID] = None
    ) -> RunMetadata:
        """Create a new run record.
        
        Args:
            run_id: The run identifier
            request: The campaign request to snapshot
            parent_run_id: Optional parent run for rerun chains
        
        Returns:
            RunMetadata with status='pending'
        
        Raises:
            ValueError: If run already exists or parent doesn't exist
        """
        # Serialize request, excluding any API keys for security
        snapshot = request.model_dump()
        self._sanitize_config(snapshot)
        config_json = json.dumps(snapshot, default=str)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        parent_id = parent_run_id.value if parent_run_id else None
        
        try:
            cursor.execute("""
                INSERT INTO runs (run_id, start_time, status, retry_count, config_snapshot, parent_run_id)
                VALUES (?, ?, 'pending', 0, ?, ?)
            """, (run_id.value, datetime.utcnow().isoformat(), config_json, parent_id))
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Run already exists: {run_id.value}") from e
        
        conn.commit()
        
        return RunMetadata(
            run_id=run_id,
            start_time=datetime.utcnow(),
            status="pending",
            retry_count=0,
            config_snapshot=snapshot,
            parent_run_id=parent_run_id
        )
    
    def update_run_status(
        self,
        run_id: RunID,
        status: str,
        end_time: Optional[datetime] = None,
        terminal_failure_reason: Optional[str] = None,
        retry_count: Optional[int] = None
    ) -> RunMetadata:
        """Update run status.

        Args:
            run_id: The run identifier
            status: New status (pending, running, success, failed)
            end_time: Optional end time
            terminal_failure_reason: Optional failure reason
            retry_count: Optional retry count override
        
        Returns:
            Updated RunMetadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        end_iso = end_time.isoformat() if end_time else None
        
        # Get current retry_count if not provided
        if retry_count is None:
            cursor.execute("SELECT retry_count FROM runs WHERE run_id = ?", (run_id.value,))
            row = cursor.fetchone()
            retry_count = row["retry_count"] if row else 0
        
        cursor.execute("""
            UPDATE runs 
            SET status = ?, end_time = ?, terminal_failure_reason = ?, retry_count = ?
            WHERE run_id = ?
        """, (status, end_iso, terminal_failure_reason, retry_count, run_id.value))
        
        conn.commit()
        
        # Fetch updated metadata
        return self.get_run(run_id)
    
    def record_artifact(
        self,
        run_id: RunID,
        artifact_path: str,
        content_hash: str
    ) -> None:
        """Record an artifact linked to a run.
        
        Args:
            run_id: The run identifier
            artifact_path: Relative path to the artifact
            content_hash: SHA256 hash of file contents
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO artifacts (run_id, artifact_path, content_hash, saved_at)
            VALUES (?, ?, ?, ?)
        """, (run_id.value, artifact_path, content_hash, datetime.utcnow().isoformat()))
        
        conn.commit()
    
    def get_run(self, run_id: RunID) -> Optional[RunMetadata]:
        """Retrieve run metadata.
        
        Args:
            run_id: The run identifier
        
        Returns:
            RunMetadata if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Fetch run
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id.value,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Fetch artifacts
        cursor.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id.value,))
        artifact_rows = cursor.fetchall()
        
        artifacts = [
            {
                "path": ar["artifact_path"],
                "content_hash": ar["content_hash"],
                "saved_at": ar["saved_at"]
            }
            for ar in artifact_rows
        ]
        
        # Parse parent run_id if exists
        parent_run = None
        if row["parent_run_id"]:
            try:
                parent_run = RunID(value=row["parent_run_id"])
            except ValueError:
                pass
        
        # Parse config snapshot
        config_snapshot = json.loads(row["config_snapshot"])
        
        # Parse timestamps
        start_time = datetime.fromisoformat(row["start_time"])
        end_time = None
        if row["end_time"]:
            end_time = datetime.fromisoformat(row["end_time"])
        
        return RunMetadata(
            run_id=RunID(value=row["run_id"]),
            start_time=start_time,
            end_time=end_time,
            status=row["status"],
            retry_count=row["retry_count"],
            terminal_failure_reason=row["terminal_failure_reason"],
            parent_run_id=parent_run,
            config_snapshot=config_snapshot,
            artifacts=artifacts
        )
    
    def get_runs_by_parent(self, parent_run_id: RunID) -> List[RunMetadata]:
        """Get all runs that are children of a parent run.
        
        Args:
            parent_run_id: The parent run identifier
        
        Returns:
            List of child RunMetadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT run_id FROM runs WHERE parent_run_id = ?
            ORDER BY created_at ASC
        """, (parent_run_id.value,))
        
        results = []
        for row in cursor.fetchall():
            metadata = self.get_run(RunID(value=row["run_id"]))
            if metadata:
                results.append(metadata)
        
        return results
    
    def _sanitize_config(self, config: dict) -> None:
        """Remove API keys from config snapshot before storage.
        
        Security: Prevents API keys from being stored in SQLite.
        """
        keys_to_remove = {"groq_api_key", "serper_api_key", "api_key", "key", "secret"}
        
        def sanitize(obj: dict) -> None:
            for key in list(obj.keys()):
                if key.lower() in keys_to_remove:
                    obj[key] = "[REDACTED]"
                elif isinstance(obj[key], dict):
                    sanitize(obj[key])
        
        sanitize(config)
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __del__(self) -> None:
        """Cleanup connection on deletion."""
        self.close()