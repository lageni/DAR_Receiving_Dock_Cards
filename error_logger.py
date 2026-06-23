#!/usr/bin/env python
"""
Error logging for CodePuppyDAR
"""
from pathlib import Path
from datetime import datetime
import json

LOG_FILE = Path(__file__).parent / "error_logs.jsonl"

def log_error(error_type: str, message: str, details: str = "", context: dict = None):
    """Log an error to the error log file
    
    Args:
        error_type: Type of error (e.g., "API_ERROR", "DATABASE_ERROR")
        message: Short error message
        details: Detailed error information
        context: Additional context dict
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "message": message,
            "details": details,
            "context": context or {}
        }
        
        # Append to JSONL file (one JSON object per line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        print(f"[LOG] {error_type}: {message}")
    
    except Exception as e:
        print(f"[WARN] Failed to log error: {e}")

def get_error_logs(limit: int = 100) -> list:
    """Get recent error logs
    
    Args:
        limit: Maximum number of log entries to return
    
    Returns:
        List of log entries (dicts)
    """
    if not LOG_FILE.exists():
        return []
    
    try:
        logs = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except:
                    pass
        
        # Return most recent first, limited
        return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    except Exception as e:
        print(f"[WARN] Failed to read error logs: {e}")
        return []

def clear_error_logs():
    """Clear all error logs"""
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
        print("[LOG] Error logs cleared")
    except Exception as e:
        print(f"[WARN] Failed to clear error logs: {e}")
