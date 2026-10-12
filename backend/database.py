"""NoSQL store: MongoDB when MONGO_URI is set, else file-system JSON cache.

Both paths expose the same get/set interface so API logic never branches.
File cache mimics a NoSQL document store: one JSON document per cache_key.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def make_cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class DocumentStore:
    def __init__(self) -> None:
        self.mongo_uri = os.getenv("MONGO_URI", "").strip()
        self.mongo_db = os.getenv("MONGO_DB", "climate_hazards")
        self.cache_dir = Path(os.getenv("CACHE_DIR", "./cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = float(os.getenv("CACHE_TTL_DAYS", "30"))
        self._col = None
        if self.mongo_uri:
            try:
                from pymongo import MongoClient  # lazy import

                client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=4000)
                client.server_info()  # fail fast
                self._col = client[self.mongo_db]["analyses"]
                try:
                    self._col.create_index("cache_key", unique=True)
                except Exception:
                    pass
            except Exception:
                self._col = None  # graceful fallback to file cache

    @property
    def backend(self) -> str:
        return "mongodb" if self._col is not None else "file"

    def get(self, cache_key: str) -> Optional[dict]:
        # Mongo first
        if self._col is not None:
            try:
                doc = self._col.find_one({"cache_key": cache_key})
                if doc:
                    doc.pop("_id", None)
                    return doc
            except Exception:
                pass
        # File fallback with TTL
        path = self.cache_dir / f"{cache_key}.json"
        if not path.exists():
            return None
        try:
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if age_days > self.ttl_days:
                path.unlink(missing_ok=True)
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, cache_key: str, doc: dict) -> None:
        payload = {"cache_key": cache_key, **doc}
        if self._col is not None:
            try:
                self._col.update_one(
                    {"cache_key": cache_key}, {"$set": payload}, upsert=True
                )
            except Exception:
                pass
        try:
            (self.cache_dir / f"{cache_key}.json").write_text(
                json.dumps(payload, default=str), encoding="utf-8"
            )
        except Exception:
            pass


store = DocumentStore()
