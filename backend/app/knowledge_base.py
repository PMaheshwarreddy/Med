"""Symptom evidence over the medical knowledge (one of the report's two searches;
the guideline passages are the other, app/kb/retrieve.py).

Given the symptoms a patient described, in whatever words, this finds the
matching symptom rows, follows the disease links, and scores each candidate
disease by the evidence for it. It is deterministic and needs no language
model, so the same evidence is available online and offline.

The data comes from the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL,
tables kb_entities, kb_disease_symptoms, kb_disease_drugs, kb_precautions,
kb_drugs) of the sources reports may use. A copy of what was read is kept on
disk (data/rag_cache/kb_index.json.gz), so the search works when that
database cannot be reached. The app database (Supabase) holds no knowledge.

  1. Symptom matching: exact name, alias or spelling variant first; then
     meaning, by embedding similarity ("my head is pounding" -> Headache).
  2. Evidence scoring: a candidate is scored by how much of the patient's
     presentation it explains, weighting rare symptoms above common ones.
  3. For the best candidates: description, linked drugs and precautions.
"""

import gzip
import hashlib
import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np

from .ingest.transform import fuzzy_key, normalize

log = logging.getLogger("medora.knowledge")

# A "disease" linked to more symptoms than this is not a disease: the source
# files contain reversed rows where a symptom ("Pain", "Fever") sits in the
# disease column with hundreds of conditions listed against it. Real diseases
# in the data have at most about 70 symptoms.
MAX_SYMPTOMS_PER_DISEASE = 90
# Cosine similarity a phrase needs to count as meaning a symptom.
MIN_SIMILARITY = 0.68
# The knowledge base often holds the same symptom under several names
# ("Dysuria", "Burning sensation during urination"), each linked to different
# diseases. Near-identical neighbours above this are all taken.
SYNONYM_SIMILARITY = 0.82
MAX_NEIGHBOURS = 3
MAX_CANDIDATES = 8
# How often the index asks the knowledge database whether anything changed,
# and how long it leaves an unreachable database alone.
CHECK_EVERY = 60.0
CONNECT_TIMEOUT = 5
# Listed as drugs in the sources, but in advice to a patient they are just
# words: "drink plenty of water" must not be mistaken for naming a medicine.
_EVERYDAY_SUBSTANCES = {
    "water", "oxygen", "alcohol", "ethanol", "caffeine", "nicotine", "calcium", "magnesium",
    "iodine", "fluoride", "sulfur", "glycerin", "menthol", "camphor",
}  # fmt: skip


class Embedder:
    """Sentence embeddings from the local Ollama server (works offline)."""

    def __init__(self, url: str, model: str):
        self._url = url.rstrip("/")
        self.model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        with httpx.Client(timeout=300) as client:
            for start in range(0, len(texts), 256):
                response = client.post(
                    f"{self._url}/api/embed",
                    json={"model": self.model, "input": texts[start : start + 256]},
                )
                response.raise_for_status()
                vectors += response.json()["embeddings"]
        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.where(norms == 0, 1, norms)


@dataclass
class SymptomMatch:
    phrase: str  # what the patient said
    symptom_id: int
    name: str  # the knowledge-base symptom it was matched to
    score: float  # 1.0 for a name match, the similarity otherwise
    how: str  # "name" | "meaning"
    # Which of the patient's symptoms this belongs to: several knowledge-base
    # rows matched for one complaint count as one piece of evidence.
    group: int = 0


@dataclass
class Candidate:
    disease_id: int
    name: str
    score: float  # 0..1 evidence score
    matched: list[str]  # the patient's symptoms this disease explains
    symptom_count: int  # how many symptoms the disease has in total
    description: str = ""
    causes: str = ""
    drugs: list[dict] = field(default_factory=list)  # {"name", "uses"}
    precautions: list[str] = field(default_factory=list)
    # Other names of the disease ("scabies" for Acariasis), normalized.
    aliases: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    matches: list[SymptomMatch] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def used(self) -> bool:
        return bool(self.candidates)

    def drug_names(self) -> dict[str, str]:
        """Normalized name -> display name of every drug linked to a candidate."""
        return {normalize(d["name"]): d["name"] for c in self.candidates for d in c.drugs}


def _allowed_sql() -> str:
    return (
        "s.status = 'loaded' and (s.production_allowed"
        " or (%(testing)s and s.tier <= 4) or (%(community)s and s.tier = 5))"
    )


# What the index reads, per allowed source (see `KnowledgeIndex.read_rows`).
_QUERIES = {
    "entities": """select e.kind, e.name, e.aliases, e.description, e.causes, e.uses, e.enrich
                   from kb_entities e join kb_sources s on s.id = e.source_id where {allowed}
                   order by s.tier, s.id, e.id""",
    "pairs": """select x.disease, x.symptom from kb_disease_symptoms x
                join kb_sources s on s.id = x.source_id where {allowed} order by s.tier, s.id, x.id""",
    "disease_drugs": """select x.disease, x.drug from kb_disease_drugs x
                        join kb_sources s on s.id = x.source_id where {allowed} order by s.tier, s.id, x.id""",
    "precautions": """select x.disease, x.symptom, x.precaution from kb_precautions x
                      join kb_sources s on s.id = x.source_id where {allowed} order by s.tier, s.id, x.id""",
    # Every medicine name any source holds: only used to keep medicine names
    # out of patient advice, so the wider the better.
    "drug_names": "select name from kb_drugs",
}


class KnowledgeIndex:
    """Search structures over the knowledge database, built on first use and
    rebuilt when a source is loaded, changed or removed."""

    def __init__(
        self,
        url: str,
        embedder: Embedder | None,
        cache_dir: Path,
        testing_sources: bool = False,
        community_sources: bool = False,
    ):
        self._url = url.replace("postgresql+psycopg://", "postgresql://") if url else ""
        self._embedder = embedder
        self._cache_dir = cache_dir
        self._switches = {"testing": testing_sources, "community": community_sources}
        self._lock = threading.Lock()
        self._signature: list | None = None
        self._checked = 0.0  # when the database was last asked (monotonic)
        self.last_error = ""
        self.source = "none"  # database | disk copy | given rows | none
        self._reset()

    @classmethod
    def from_rows(cls, rows: dict, embedder: Embedder | None, cache_dir: Path) -> "KnowledgeIndex":
        """An index over rows given directly (tests, tools): no database."""
        index = cls("", embedder, cache_dir)
        index._build(rows)
        index.source = "given rows"
        return index

    def _reset(self) -> None:
        self._by_key: dict[str, int] = {}
        self._by_fuzzy: dict[str, int] = {}
        self._names: dict[int, str] = {}
        self._symptom_diseases: dict[int, list[int]] = {}
        self._disease_size: dict[int, int] = {}
        self._vectors: np.ndarray | None = None
        self._vector_ids: list[int] = []
        self._drug_keys: set[str] = set()
        # Disease details, medicines and precautions, held in memory so the
        # search answers without the database.
        self._diseases: dict[int, tuple[str, str, str]] = {}  # id -> name, description, causes
        self._disease_by_key: dict[str, int] = {}  # name or unambiguous other name -> id
        self._disease_aliases: dict[int, list[str]] = {}
        self._drugs: dict[int, list[dict]] = {}
        self._precautions: dict[int, list[str]] = {}

    # --- building -----------------------------------------------------------

    def available(self) -> bool:
        """Whether there is knowledge to search. Never waits on a database."""
        return bool(self._symptom_diseases)

    def warm(self) -> None:
        """Builds the index ahead of the first request (from the database, or
        from the copy on disk when it cannot be reached). Never raises."""
        try:
            self._ensure(force=True)
        except Exception:
            log.exception("Could not build the knowledge index")

    def refresh_soon(self) -> None:
        """Asks the database again at the next search (after a load)."""
        self._checked = 0.0

    @property
    def _cache_file(self) -> Path:
        return self._cache_dir / "kb_index.json.gz"

    def _ensure(self, force: bool = False) -> bool:
        """Loads or refreshes the index. False when there is no knowledge.
        The database is asked at most every CHECK_EVERY seconds; when it
        cannot be reached, the loaded index (or the disk copy) keeps serving."""
        if not self._url:
            return bool(self._symptom_diseases)
        if not force and time.monotonic() - self._checked < CHECK_EVERY:
            return bool(self._symptom_diseases)
        with self._lock:
            if not force and time.monotonic() - self._checked < CHECK_EVERY:
                return bool(self._symptom_diseases)
            self._checked = time.monotonic()
            try:
                self._refresh()
                self.last_error = ""
            except Exception as e:  # noqa: BLE001 - unreachable, or tables not created yet
                self.last_error = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
                if not self._symptom_diseases:
                    self._load_disk_copy()
                log.info("Knowledge database not readable (%s); %s", self.last_error,
                         "using the loaded index" if self._symptom_diseases else "no knowledge loaded")
        return bool(self._symptom_diseases)

    def _connect(self):
        import psycopg

        return psycopg.connect(self._url, connect_timeout=CONNECT_TIMEOUT, prepare_threshold=None)

    def _refresh(self) -> None:
        with self._connect() as conn:
            signature = [
                *conn.execute(
                    f"""select count(*), coalesce(md5(string_agg(s.key || ':' || coalesce(s.loaded_at::text, ''),
                        ',' order by s.key)), '') from kb_sources s where {_allowed_sql()}""",
                    self._switches,
                ).fetchone(),
                self._switches["testing"], self._switches["community"],
            ]
            if signature == self._signature and self._symptom_diseases:
                return
            rows = self.read_rows(conn, self._switches)
        self._build(rows)
        self._signature = signature
        self.source = "database"
        self._save_disk_copy(rows, signature)

    @staticmethod
    def read_rows(conn, switches: dict) -> dict:
        allowed = _allowed_sql()
        return {
            name: [list(r) for r in conn.execute(sql.format(allowed=allowed), switches).fetchall()]
            for name, sql in _QUERIES.items()
        }

    def _save_disk_copy(self, rows: dict, signature: list) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            part = self._cache_file.with_suffix(".part")
            with gzip.open(part, "wt", encoding="utf-8") as f:
                json.dump({"signature": signature, "saved": time.time(), "rows": rows}, f, ensure_ascii=False)
            part.replace(self._cache_file)
        except OSError as e:
            log.warning("Could not save the knowledge index copy: %s", e)

    def _load_disk_copy(self) -> None:
        if not self._cache_file.exists():
            return
        try:
            with gzip.open(self._cache_file, "rt", encoding="utf-8") as f:
                saved = json.load(f)
            self._build(saved["rows"])
        except (OSError, ValueError, KeyError) as e:
            log.warning("The knowledge index copy could not be read: %s", e)
            return
        self.source = "disk copy"
        log.info("Knowledge index loaded from the copy on disk (the knowledge database is not reachable)")

    def _build(self, rows: dict) -> None:
        """Builds every structure from rows of the knowledge database. Rows of
        the same disease, symptom or medicine from several sources are merged
        by name; an `enrich` row only adds other names and text to a row that
        exists without it."""
        self._reset()
        disease_ids: dict[str, int] = {}
        symptom_ids: dict[str, int] = {}
        disease_info: dict[int, dict] = {}
        symptom_info: dict[int, dict] = {}

        def disease(name: str) -> int | None:
            key = normalize(name or "")
            if not key:
                return None
            if key not in disease_ids:
                disease_ids[key] = len(disease_ids) + 1
                disease_info[disease_ids[key]] = {"name": name.strip(), "description": "", "causes": "", "aliases": {}}
            return disease_ids[key]

        def symptom(name: str) -> int | None:
            key = normalize(name or "")
            if not key:
                return None
            if key not in symptom_ids:
                symptom_ids[key] = len(symptom_ids) + 1
                symptom_info[symptom_ids[key]] = {"name": name.strip(), "aliases": {}}
            return symptom_ids[key]

        entities = rows.get("entities", [])
        # Rows that stand on their own first, then the ones that only enrich.
        for kind, name, aliases, description, causes, _uses, enrich in sorted(entities, key=lambda r: bool(r[6])):
            key = normalize(name or "")
            if not key:
                continue
            if kind == "disease":
                if enrich and key not in disease_ids:
                    continue
                info = disease_info[disease(name)]
                info["description"] = info["description"] or (description or "")
                info["causes"] = info["causes"] or (causes or "")
                for alias in aliases or []:
                    info["aliases"].setdefault(normalize(str(alias)), str(alias))
            elif kind == "symptom":
                if enrich and key not in symptom_ids:
                    continue
                info = symptom_info[symptom(name)]
                for alias in aliases or []:
                    info["aliases"].setdefault(normalize(str(alias)), str(alias))

        pairs: set[tuple[int, int]] = set()
        for d_name, s_name in rows.get("pairs", []):
            d, s = disease(d_name), symptom(s_name)
            if d and s:
                pairs.add((d, s))

        sizes: dict[int, int] = {}
        for disease_id, _ in pairs:
            sizes[disease_id] = sizes.get(disease_id, 0) + 1
        self._disease_size = {d: n for d, n in sizes.items() if n <= MAX_SYMPTOMS_PER_DISEASE}
        symptom_diseases: dict[int, list[int]] = {}
        for disease_id, symptom_id in sorted(pairs):
            if disease_id in self._disease_size:
                symptom_diseases.setdefault(symptom_id, []).append(disease_id)
        self._symptom_diseases = symptom_diseases

        # Only symptoms that lead to a disease are worth matching.
        texts: list[str] = []
        ids: list[int] = []
        for symptom_id, info in symptom_info.items():
            if symptom_id not in symptom_diseases:
                continue
            name, key = info["name"], normalize(info["name"])
            self._names[symptom_id] = name
            self._by_key.setdefault(key, symptom_id)
            self._by_fuzzy.setdefault(fuzzy_key(key), symptom_id)
            texts.append(name)
            ids.append(symptom_id)
            for alias_key, alias in info["aliases"].items():
                if not alias_key:
                    continue
                self._by_key.setdefault(alias_key, symptom_id)
                self._by_fuzzy.setdefault(fuzzy_key(alias_key), symptom_id)
                texts.append(alias)
                ids.append(symptom_id)
        self._vector_ids = ids
        self._vectors = self._embed_cached(texts)

        alias_owners: dict[str, set[int]] = {}
        for disease_id, info in disease_info.items():
            key = normalize(info["name"])
            self._diseases[disease_id] = (info["name"], info["description"], info["causes"])
            self._disease_by_key[key] = disease_id
            for akey in info["aliases"]:
                if len(akey) >= 4 and akey != key:
                    alias_owners.setdefault(akey, set()).add(disease_id)
        # Another name finds its disease ("scabies" -> Acariasis), unless two
        # diseases share it or it is some disease's own name.
        for akey, owners in alias_owners.items():
            if len(owners) == 1 and akey not in self._disease_by_key:
                (owner,) = owners
                self._disease_by_key[akey] = owner
                self._disease_aliases.setdefault(owner, []).append(akey)

        uses = {normalize(r[1] or ""): (r[5] or "") for r in entities if r[0] == "drug"}
        seen_links: set[tuple[int, str]] = set()
        for d_name, drug in sorted(rows.get("disease_drugs", []), key=lambda r: (normalize(r[0] or ""), r[1] or "")):
            disease_id = self._disease_by_key.get(normalize(d_name or ""))
            key = normalize(drug or "")
            if disease_id is None or not key or (disease_id, key) in seen_links:
                continue
            seen_links.add((disease_id, key))
            found = self._drugs.setdefault(disease_id, [])
            if len(found) < 12:
                found.append({"name": drug.strip(), "uses": uses.get(key, "")[:240]})
        for d_name, _symptom, line in rows.get("precautions", []):
            disease_id = self._disease_by_key.get(normalize(d_name or ""))
            if disease_id is None or not line:
                continue
            found = self._precautions.setdefault(disease_id, [])
            if len(found) < 8 and line not in found:
                found.append(line)

        # Names of five letters or more: shorter ones ("iron", "zinc") are
        # also everyday words.
        drug_names = [r[1] for r in entities if r[0] == "drug"]
        drug_names += [r[1] for r in rows.get("disease_drugs", [])]
        drug_names += [r[0] for r in rows.get("drug_names", [])]
        self._drug_keys = {
            key for key in (normalize(n or "") for n in drug_names)
            if len(key) >= 5 and key not in _EVERYDAY_SUBSTANCES
        }
        log.info(
            "Knowledge index: %d symptoms, %d diseases, vectors %s",
            len(self._names), len(self._disease_size), "on" if self._vectors is not None else "off",
        )  # fmt: skip

    def _embed_cached(self, texts: list[str]) -> np.ndarray | None:
        """Symptom vectors, computed once per data version and kept on disk."""
        if self._embedder is None or not texts:
            return None
        digest = hashlib.sha256(
            (self._embedder.model + "\n" + "\n".join(texts)).encode()
        ).hexdigest()[:24]
        path = self._cache_dir / f"symptoms-{digest}.npy"
        if path.exists():
            return np.load(path)
        try:
            vectors = self._embedder.embed(texts)
        except (httpx.HTTPError, KeyError) as e:
            log.warning("Symptom embeddings unavailable, matching by name only: %s", e)
            return None
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(path, vectors)
        return vectors

    # --- searching ----------------------------------------------------------

    def match_symptoms(
        self, groups: list[list[str]]
    ) -> tuple[list[SymptomMatch], list[str]]:
        """Matches each of the patient's symptoms, given as a group of
        wordings for it (clinical term, their own words). Returns the matches
        and the symptoms nothing was found for."""
        matches: dict[int, SymptomMatch] = {}
        pending: list[tuple[int, str]] = []
        for group, phrases in enumerate(groups):
            for phrase in dict.fromkeys(p.strip() for p in phrases if p and p.strip()):
                key = normalize(phrase)
                symptom_id = self._by_key.get(key, self._by_fuzzy.get(fuzzy_key(key)))
                if symptom_id is not None:
                    matches.setdefault(
                        symptom_id,
                        SymptomMatch(phrase, symptom_id, self._names[symptom_id], 1.0, "name", group),
                    )
                # Even a named symptom is searched by meaning, to pick up the
                # other names the knowledge base files it under.
                pending.append((group, phrase))

        if pending and self._vectors is not None:
            try:
                queries = self._embedder.embed([phrase for _, phrase in pending])
            except (httpx.HTTPError, KeyError):
                queries = None
            if queries is not None:
                similarity = queries @ self._vectors.T
                for (group, phrase), row in zip(pending, similarity):
                    order = np.argsort(row)[::-1][: MAX_NEIGHBOURS * 4]
                    taken = 0
                    for position, index in enumerate(order):
                        score = float(row[index])
                        # The best neighbour needs MIN_SIMILARITY; further
                        # ones must be near-synonyms.
                        if score < (MIN_SIMILARITY if position == 0 else SYNONYM_SIMILARITY):
                            break
                        symptom_id = self._vector_ids[index]
                        if symptom_id not in matches:
                            matches[symptom_id] = SymptomMatch(
                                phrase, symptom_id, self._names[symptom_id], score, "meaning", group
                            )
                            taken += 1
                        if taken >= MAX_NEIGHBOURS:
                            break

        found = {m.group for m in matches.values()}
        unmatched = [phrases[0] for group, phrases in enumerate(groups) if group not in found and phrases]
        return list(matches.values()), unmatched

    def find_in_text(self, text: str) -> list[str]:
        """Symptom names that literally occur in free text, longest first.
        A safety net for when the language model's phrase list misses one."""
        words = normalize(text).split()
        found: list[str] = []
        i = 0
        while i < len(words):
            for size in range(min(5, len(words) - i), 0, -1):
                key = " ".join(words[i : i + size])
                # Single short words ("pain", "back") are too ambiguous alone.
                if (size > 1 or len(key) > 5) and key in self._by_key:
                    found.append(self._names[self._by_key[key]])
                    i += size - 1
                    break
            i += 1
        return found

    def retrieve(self, groups: list[list[str]], free_text: str = "") -> Evidence:
        """Evidence for a patient. `groups` holds one list of wordings per
        symptom; `free_text` is the raw description they came from."""
        if not self._ensure():
            return Evidence(unmatched=[g[0] for g in groups if g])
        groups = [list(g) for g in groups if g]
        matches, unmatched = self.match_symptoms(groups)
        # Symptom names that occur literally in the text but were not picked
        # up above each become a symptom of their own.
        known = {m.symptom_id for m in matches}
        for name in self.find_in_text(free_text):
            symptom_id = self._by_key[normalize(name)]
            if symptom_id not in known:
                known.add(symptom_id)
                matches.append(SymptomMatch(name, symptom_id, name, 1.0, "name", len(groups)))
                groups.append([name])
        if not matches:
            return Evidence(unmatched=unmatched)

        total_diseases = len(self._disease_size)
        weight: dict[int, float] = {}
        for m in matches:
            frequency = len(self._symptom_diseases[m.symptom_id])
            # Rare symptoms say more about which disease it is than common ones.
            weight[m.symptom_id] = math.log(1 + total_diseases / frequency) * m.score
        group_of = {m.symptom_id: m.group for m in matches}
        # One complaint counts once, however many rows matched it.
        group_weight: dict[int, float] = {}
        for symptom_id, w in weight.items():
            group = group_of[symptom_id]
            group_weight[group] = max(group_weight.get(group, 0.0), w)
        presentation = sum(group_weight.values())

        explained: dict[int, list[int]] = {}
        for m in matches:
            for disease_id in self._symptom_diseases[m.symptom_id]:
                explained.setdefault(disease_id, []).append(m.symptom_id)

        scored: list[tuple[float, int]] = []
        for disease_id, symptom_ids in explained.items():
            best: dict[int, float] = {}
            for symptom_id in symptom_ids:
                group = group_of[symptom_id]
                best[group] = max(best.get(group, 0.0), weight[symptom_id])
            # With several symptoms reported, one shared symptom is no evidence.
            if len(group_weight) >= 3 and len(best) < 2:
                continue
            coverage = sum(best.values()) / presentation
            # Of two diseases explaining the same symptoms, prefer the one for
            # which those symptoms are a larger part of its picture.
            focus = len(best) / math.sqrt(self._disease_size[disease_id])
            scored.append((coverage * (0.6 + 0.4 * min(1.0, focus)), disease_id))
        scored.sort(reverse=True)
        top = scored[:MAX_CANDIDATES]

        names = {m.symptom_id: m.name for m in matches}
        candidates = [
            self._candidate(disease_id, score, [names[s] for s in explained[disease_id]])
            for score, disease_id in top
        ]
        return Evidence(matches=matches, unmatched=unmatched, candidates=candidates)

    def disease_names(self) -> list[str]:
        """Every disease name held in memory (for the doctor's type-ahead)."""
        return [name for name, _, _ in self._diseases.values() if name]

    def mentions_drug(self, text: str) -> bool:
        """True when the text names a medicine from the knowledge base."""
        words = normalize(text).split()
        return any(
            " ".join(words[i : i + size]) in self._drug_keys
            for size in (1, 2, 3)
            for i in range(len(words) - size + 1)
        )

    def lookup(self, condition: str) -> Candidate | None:
        """The knowledge-base disease a condition name refers to, when the
        search did not surface it: same name or alias, or a disease whose
        name is contained in the condition ("acute bacterial cystitis")."""
        if not self._ensure():
            return None
        key = normalize(condition)
        disease_id = self._disease_by_key.get(key)
        if disease_id is None:
            words = key.split()
            # Longest contained name first; one-word names are too loose.
            for span in sorted(
                {" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 2, len(words) + 1)},
                key=len,
                reverse=True,
            ):
                found = self._disease_by_key.get(span)
                if found is not None and (found in self._disease_size or self._diseases[found][1]):
                    disease_id = found
                    break
        if disease_id is None:
            return None
        self._disease_size.setdefault(disease_id, 0)
        return self._candidate(disease_id, 0.0, [])

    def _candidate(self, disease_id: int, score: float, matched: list[str]) -> Candidate:
        name, description, causes = self._diseases[disease_id]
        return Candidate(
            disease_id=disease_id,
            name=name,
            score=round(score, 3),
            matched=sorted(matched),
            symptom_count=self._disease_size[disease_id],
            description=description,
            causes=causes,
            drugs=list(self._drugs.get(disease_id, [])),
            precautions=list(self._precautions.get(disease_id, [])),
            aliases=list(self._disease_aliases.get(disease_id, [])),
        )
