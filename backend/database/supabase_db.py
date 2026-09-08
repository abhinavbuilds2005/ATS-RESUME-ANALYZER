import logging
import httpx
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict

logger = logging.getLogger('ats_resume_scorer')

from backend.core.config import SUPABASE_URL, SUPABASE_KEY

def _get_headers():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

async def save_analysis(filename: str, analysis_result: Dict, user_id: Optional[str] = None) -> Optional[str]:
    headers = _get_headers()
    if not headers:
        return None

    def _json_default(o):
        if hasattr(o, 'model_dump'):
            return o.model_dump()
        return str(o)
    serializable_result = json.loads(json.dumps(analysis_result, default=_json_default))

    doc = {
        "filename": filename,
        "ats_score": serializable_result.get("ats_score", 0),
        "keyword_match": serializable_result.get("keyword_match", 0),
        "missing_keywords": serializable_result.get("missing_keywords", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "analysis_result": serializable_result,
    }
    if user_id:
        doc["user_id"] = user_id

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/analyses"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=doc)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                inserted_id = str(data[0].get("id"))
                logger.info(f"Saved analysis: {inserted_id}")
                return inserted_id
            return None
    except Exception as exc:
        logger.error(f"Failed to save analysis to Supabase: {exc}")
        return None

async def get_user_history(user_id: str) -> List[Dict]:
    """Fetch past analyses strictly isolated to the authenticated user."""
    if not user_id:
        logger.warning("get_user_history called without user_id; returning empty list for security.")
        return []

    headers = _get_headers()
    if not headers:
        return []

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/analyses"
    params = {
        "user_id": f"eq.{user_id}",
        "order": "created_at.desc"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url, 
                headers=headers, 
                params=params
            )
            response.raise_for_status()
            docs = response.json()
            
            results = []
            for doc in docs:
                results.append({
                    "id": str(doc.get("id")),
                    "filename": doc.get("filename", "resume"),
                    "resume_name": doc.get("filename", "resume"),
                    "job_title": "Software Engineer",
                    "ats_score": doc.get("ats_score", 0),
                    "keyword_match": doc.get("keyword_match", 0),
                    "missing_keywords": doc.get("missing_keywords", []),
                    "date": doc.get("created_at", ""),
                    "created_at": doc.get("created_at", ""),
                    "analysis_result": doc.get("analysis_result", {}),
                })
            return results
    except Exception as exc:
        logger.error(f"Failed to fetch history from Supabase: {exc}")
        return []

async def get_analysis_by_id(analysis_id: str, user_id: str) -> Optional[Dict]:
    """Retrieve an analysis record strictly verifying user ownership to prevent IDOR."""
    if not analysis_id or not user_id:
        return None

    headers = _get_headers()
    if not headers:
        return None

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/analyses"
    params = {
        "id": f"eq.{analysis_id}",
        "user_id": f"eq.{user_id}",
        "limit": "1"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            docs = response.json()
            if docs and len(docs) > 0:
                return docs[0]
            return None
    except Exception as exc:
        logger.error(f"Failed to fetch analysis {analysis_id} for user {user_id}: {exc}")
        return None

async def delete_analysis(analysis_id: str, user_id: str) -> bool:
    """Delete an analysis record strictly verifying user ownership to prevent IDOR."""
    if not analysis_id or not user_id:
        logger.warning("delete_analysis called without analysis_id or user_id.")
        return False

    headers = _get_headers()
    if not headers:
        return False

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/analyses"
    params = {
        "id": f"eq.{analysis_id}",
        "user_id": f"eq.{user_id}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                url, 
                headers=headers, 
                params=params
            )
            response.raise_for_status()
            try:
                deleted_rows = response.json()
                if isinstance(deleted_rows, list):
                    return len(deleted_rows) > 0
            except Exception:
                pass
            return response.status_code in (200, 204)
    except Exception as exc:
        logger.error(f"Failed to delete analysis {analysis_id} for user {user_id}: {exc}")
        return False

