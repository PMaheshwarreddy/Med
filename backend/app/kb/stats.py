"""What the knowledge database holds, for the back office's Database tab.

Counted live from the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL) and
kept for a few seconds, so a page that refreshes itself does not count again
on every request. When the database cannot be reached the last numbers that
were read are returned (also after a restart: they are saved to disk), marked
as not current.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

log = logging.getLogger("medora.kb.stats")

FRESH_FOR = 10.0  # seconds a count is reused
RETRY_AFTER = 30.0  # seconds an unreachable database is left alone

_TOTALS = """select
  (select count(*) from kb_sources where status = 'loaded'),
  (select count(*) from kb_chunks),
  (select count(*) from kb_chunks where embedding is not null),
  (select count(*) from kb_conditions),
  (select count(*) from kb_terms),
  (select count(*) from kb_drugs),
  (select count(*) from kb_drug_products),
  (select count(*) from kb_doses),
  (select count(*) from kb_drug_safety),
  (select count(*) from kb_red_flags),
  (select count(*) from kb_disease_symptoms),
  (select count(*) from kb_disease_drugs),
  (select count(*) from kb_precautions),
  (select count(*) from kb_entities where not enrich),
  (select count(*) from kb_patient_topics),
  (select count(*) from kb_quarantine),
  (select max(loaded_at) from kb_sources),
  pg_size_pretty(pg_database_size(current_database())),
  (select count(*) from (select normalized from kb_terms where kind = 'symptom'
     union select normalized from kb_entities where kind = 'symptom' and not enrich
     union select symptom_normalized from kb_disease_symptoms) x),
  (select count(*) from (select normalized from kb_conditions
     union select normalized from kb_entities where kind = 'disease' and not enrich
     union select normalized from kb_disease_symptoms) x),
  (select count(*) from (select normalized from kb_drugs
     union select normalized from kb_entities where kind = 'drug' and not enrich
     union select drug_normalized from kb_disease_drugs) x)"""
_TOTAL_KEYS = ("sources", "passages", "searchablePassages", "conditions", "names", "medicines", "brands", "doses",
               "safetyNotes", "redFlags", "symptomLinks", "drugLinks", "precautions", "listedEntries",
               "patientTopics", "quarantined", "lastLoadedAt", "databaseSize",
               # The four numbers the Database tab shows: each name counted once
               # across every source.
               "symptoms", "diseases", "medications")

_SOURCES = """select s.key, s.title, s.publisher, s.kind, s.tier, s.status, s.production_allowed,
  s.loaded_at, s.stats,
  (select count(*) from kb_chunks k where k.source_id = s.id),
  (select count(*) from kb_quarantine q where q.source_id = s.id)
  from kb_sources s order by s.tier, s.key"""


def used_in_reports(tier: int, production_allowed: bool, testing: bool, community: bool) -> str:
    """'yes' (allowed), 'testing' (only because a testing switch is on) or
    'no': the same rule as the guideline search (retrieve.py) and the symptom
    index (knowledge_base.py)."""
    if production_allowed:
        return "yes"
    if tier <= 4 and testing:
        return "testing"
    if tier == 5 and community:
        return "testing"
    return "no"


class KnowledgeStats:
    def __init__(self, url: str, cache_file: Path, snapshot_dir: Path | None = None,
                 testing: bool = False, community: bool = False):
        self.url = url.replace("postgresql+psycopg://", "postgresql://") if url else ""
        self.cache_file = cache_file
        self.snapshot_dir = snapshot_dir
        self.testing = testing
        self.community = community
        self._lock = threading.Lock()
        self._last: dict | None = None
        self._at = 0.0
        self._failed_at = 0.0
        self._error = ""
        self._snapshot_count: tuple[float, int] | None = None

    def forget(self) -> None:
        """Count again at the next request (after a load)."""
        self._at = 0.0
        self._failed_at = 0.0

    def summary(self) -> dict:
        if not self.url:
            return {"configured": False, "reachable": False, "error": "MEDORA_KNOWLEDGE_DATABASE_URL is not set",
                    "totals": None, "sources": [], "offline": self._offline()}
        with self._lock:
            now = time.monotonic()
            fresh = self._last is not None and now - self._at < FRESH_FOR
            resting = now - self._failed_at < RETRY_AFTER
            if not fresh and not resting:
                try:
                    self._last = self._count()
                    self._at, self._error = now, ""
                    self._save()
                except Exception as e:  # noqa: BLE001 - unreachable, or the tables are missing
                    self._failed_at = now
                    self._error = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
                    log.info("Knowledge database not readable: %s", self._error)
            reachable = not self._error
            last = self._last or self._read_saved()
        out = {"configured": True, "reachable": reachable, "error": self._error,
               "totals": None, "sources": [], "countedAt": "", "offline": self._offline()}
        if last:
            out |= {"totals": last["totals"], "sources": last["sources"], "countedAt": last["countedAt"]}
        return out

    def _count(self) -> dict:
        with psycopg.connect(self.url, connect_timeout=5, prepare_threshold=None) as conn:
            conn.execute("set statement_timeout = '20s'")
            totals = dict(zip(_TOTAL_KEYS, conn.execute(_TOTALS).fetchone()))
            totals["lastLoadedAt"] = totals["lastLoadedAt"].isoformat() if totals["lastLoadedAt"] else ""
            sources = []
            for key, title, publisher, kind, tier, status, allowed, loaded_at, stats, passages, quarantined in (
                conn.execute(_SOURCES).fetchall()
            ):
                sources.append({
                    "key": key, "title": title, "publisher": publisher, "kind": kind, "tier": tier,
                    "status": status, "productionAllowed": allowed,
                    "loadedAt": loaded_at.isoformat() if loaded_at else None,
                    "passages": passages, "quarantined": quarantined, "uploaded": key.startswith("upload-"),
                    "inReports": used_in_reports(tier, allowed, self.testing, self.community),
                    "error": (stats or {}).get("error", "") if status == "failed" else "",
                })
        return {"totals": totals, "sources": sources, "countedAt": datetime.now(timezone.utc).isoformat()}

    def _save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(self._last, ensure_ascii=False))
        except OSError:
            pass

    def _read_saved(self) -> dict | None:
        try:
            return json.loads(self.cache_file.read_text())
        except (OSError, ValueError):
            return None

    def _offline(self) -> dict:
        """The offline copy of the guideline search (passages and when saved)."""
        if self.snapshot_dir is None:
            return {"passages": 0, "savedAt": ""}
        meta = self.snapshot_dir / "kb_passages.json"
        if not meta.exists():
            return {"passages": 0, "savedAt": ""}
        mtime = meta.stat().st_mtime
        if self._snapshot_count is None or self._snapshot_count[0] != mtime:
            try:
                count = len(json.loads(meta.read_text()))
            except (OSError, ValueError):
                count = 0
            self._snapshot_count = (mtime, count)
        return {"passages": self._snapshot_count[1],
                "savedAt": datetime.fromtimestamp(mtime, timezone.utc).isoformat()}
