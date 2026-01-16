import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

from flask import current_app


def _parse_run_file(filepath: str) -> Optional[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def get_runs_status(limit: int = 10) -> Dict[str, Any]:
    run_logs_path = current_app.config.get("STORAGE_RUN_LOGS_PATH")
    if not run_logs_path or not os.path.exists(run_logs_path):
        return {
            "last_scraper_run": None,
            "last_indexer_run": None,
            "recent_runs": []
        }

    files = []
    try:
        for entry in os.scandir(run_logs_path):
            if entry.is_file() and entry.name.endswith(".json"):
                files.append(entry)
    except OSError:
        pass

    files.sort(key=lambda x: x.name, reverse=True)

    recent_runs = []
    last_scraper = None
    last_indexer = None

    for entry in files:
        data = _parse_run_file(entry.path)
        if not data:
            continue
        
        comp = data.get("component")
        
        if comp == "scraper" and last_scraper is None:
            last_scraper = data
        elif comp == "indexer" and last_indexer is None:
            last_indexer = data
            
        if len(recent_runs) < limit:
            recent_runs.append(data)
            
        if len(recent_runs) >= limit and last_scraper and last_indexer:
            break

    return {
        "last_scraper_run": last_scraper,
        "last_indexer_run": last_indexer,
        "recent_runs": recent_runs
    }
