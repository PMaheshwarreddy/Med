"""Knowledge in the knowledge database only: data files and the old tables
become kb_* rows, the symptom index reads those rows (or its disk copy), and
the back office's Database tab works from the knowledge database."""

import gzip
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ingest.plan import Plan
from app.ingest.transform import apply_plan
from app.kb.stats import KnowledgeStats, used_in_reports
from app.kb.staged import bundle_from_legacy, bundle_from_staged
from app.kb.uploads import UploadError, clean_meta, excel_to_csv, kind_of
from app.knowledge_base import KnowledgeIndex
from app.main import create_app
from app.settings import Settings

LINK_PLAN = Plan.model_validate({
    "content": "records", "verdict": "usable", "confidence": 0.95, "outputs": [
        {"kind": "link", "disease": {"sources": ["disease"]}, "symptom": {"sources": ["symptoms"], "split": ","}},
        {"kind": "link", "disease": {"sources": ["disease"]}, "drug": {"sources": ["drug"]}},
        {"kind": "precaution", "disease": {"sources": ["disease"]}, "text": {"sources": ["advice"]}},
    ]})  # fmt: skip


def index_rows(*bundles) -> dict:
    """What KnowledgeIndex.read_rows returns for these bundles' rows."""
    rows = {"entities": [], "pairs": [], "disease_drugs": [], "precautions": [], "drug_names": []}
    for b in bundles:
        for e in b.rows.get("kb_entities", []):
            rows["entities"].append([e["kind"], e["name"], e["aliases"], e["description"], e["causes"], e["uses"], e["enrich"]])
        rows["pairs"] += [[x["disease"], x["symptom"]] for x in b.rows.get("kb_disease_symptoms", [])]
        rows["disease_drugs"] += [[x["disease"], x["drug"]] for x in b.rows.get("kb_disease_drugs", [])]
        rows["precautions"] += [[x["disease"], x["symptom"], x["precaution"]] for x in b.rows.get("kb_precautions", [])]
    return rows


def test_a_planned_data_file_becomes_knowledge_rows_that_the_index_searches(tmp_path):
    staged = apply_plan(LINK_PLAN, [
        {"disease": "Influenza (Grippe)", "symptoms": "fever, cough, body aches", "drug": "Oseltamivir", "advice": "Rest at home."},
        {"disease": "Common cold", "symptoms": "cough, sneezing", "drug": "", "advice": ""},
    ])  # fmt: skip
    bundle = bundle_from_staged(staged)
    assert {k: v for k, v in bundle.stats.items() if v} == {
        "diseases": 2, "symptoms": 4, "drugs": 1, "symptom links": 5, "drug links": 1, "precautions": 1}
    flu = next(e for e in bundle.rows["kb_entities"] if e["name"] == "Influenza")
    assert flu["aliases"] == ["Grippe"] and flu["kind"] == "disease" and not flu["enrich"]

    kb = KnowledgeIndex.from_rows(index_rows(bundle), None, tmp_path)
    evidence = kb.retrieve([["fever"], ["body aches"], ["cough"]])
    top = evidence.candidates[0]
    assert top.name == "Influenza" and top.drugs == [{"name": "Oseltamivir", "uses": ""}]
    assert top.precautions == ["Rest at home."]
    assert kb.lookup("grippe").name == "Influenza"  # by its other name
    assert kb.mentions_drug("take oseltamivir now") and kb.disease_names()


def test_enrich_rows_only_add_to_what_another_source_has(tmp_path):
    base = bundle_from_staged(apply_plan(LINK_PLAN, [{"disease": "Scabies", "symptoms": "itching, rash"}]))
    catalogue = apply_plan(Plan.model_validate({
        "content": "records", "verdict": "usable", "confidence": 1, "outputs": [
            {"kind": "entity", "table": "diseases", "mode": "enrich_only", "name": {"sources": ["n"]},
             "aliases": {"sources": ["a"]}, "fields": {"description": {"sources": ["d"]}}}]}),  # fmt: skip
        [{"n": "Scabies", "a": "Acariasis", "d": "A mite infestation of the skin."},
         {"n": "Gout", "a": "Podagra", "d": "Crystal arthritis."}],
    )
    enrich = bundle_from_staged(catalogue)
    assert all(e["enrich"] for e in enrich.rows["kb_entities"])
    kb = KnowledgeIndex.from_rows(index_rows(base, enrich), None, tmp_path)
    assert kb.lookup("acariasis").description == "A mite infestation of the skin."
    assert kb.lookup("gout") is None  # an enrich row never stands alone


def test_the_old_knowledge_tables_become_the_same_rows(tmp_path):
    export = {
        "diseases": [{"id": 1, "name": "Malaria", "aliases": ["Marsh fever"], "description": "Parasites.", "causes": "Mosquito."}],
        "symptoms": [{"id": 7, "name": "Fever", "aliases": ["Pyrexia"], "description": ""},
                     {"id": 8, "name": "Chills", "aliases": [], "description": ""}],
        "drugs": [{"id": 3, "name": "Artesunate", "aliases": [], "dosage": "", "uses": "Malaria", "side_effects": ""}],
        "links": [{"disease_id": 1, "symptom_id": 7, "drug_id": None}, {"disease_id": 1, "symptom_id": 8, "drug_id": None},
                  {"disease_id": 1, "symptom_id": None, "drug_id": 3}],
        "precautions": [{"disease_id": 1, "symptom_id": None, "precaution": "Sleep under a mosquito net."}],
    }  # fmt: skip
    bundle = bundle_from_legacy(export)
    assert {k: v for k, v in bundle.stats.items() if v} == {
        "diseases": 1, "symptoms": 2, "drugs": 1, "symptom links": 2, "drug links": 1, "precautions": 1}
    kb = KnowledgeIndex.from_rows(index_rows(bundle), None, tmp_path)
    top = kb.retrieve([["pyrexia"], ["chills"]]).candidates[0]
    assert (top.name, top.precautions, top.drugs[0]["uses"]) == ("Malaria", ["Sleep under a mosquito net."], "Malaria")


def test_the_index_serves_its_disk_copy_when_the_database_is_unreachable(tmp_path):
    bundle = bundle_from_staged(apply_plan(LINK_PLAN, [{"disease": "Dengue", "symptoms": "fever, rash, joint pain"}]))
    unreachable = "postgresql://nobody@127.0.0.1:9/none"
    first = KnowledgeIndex(unreachable, None, tmp_path)
    first.warm()
    assert not first.available() and first.last_error
    first._save_disk_copy(index_rows(bundle), ["sig"])
    assert gzip.open(tmp_path / "kb_index.json.gz", "rt").read().startswith("{")

    later = KnowledgeIndex(unreachable, None, tmp_path)
    later.warm()
    assert later.available() and later.source == "disk copy"
    assert later.retrieve([["fever"], ["rash"]]).candidates[0].name == "Dengue"


def test_upload_kinds_and_what_the_uploader_must_say(tmp_path):
    def file(name: str, data: bytes) -> Path:
        (tmp_path / name).write_bytes(data)
        return tmp_path / name

    assert kind_of(file("a.pdf", b"%PDF-1.7\n...")) == ("pdf", "pdf")
    assert kind_of(file("weird-name.bin", b"%PDF-1.4\n")) == ("pdf", "pdf")  # content, not the name
    assert kind_of(file("d.csv", b"disease,symptoms\nFlu,fever\nCold,cough\n"))[0] == "records"
    article = "Typhoid fever is an infection caused by Salmonella Typhi. " * 20
    assert kind_of(file("t.txt", article.encode())) == ("article", "text")
    assert kind_of(file("x.dat", bytes(range(256)) * 4))[0] == "other"

    from openpyxl import Workbook

    book = Workbook()
    book.active.append(["disease", "symptoms"])
    book.active.append(["Flu", "fever, cough"])
    book.save(tmp_path / "sheet.xlsx")
    assert kind_of(tmp_path / "sheet.xlsx") == ("records", "xlsx")
    assert excel_to_csv(tmp_path / "sheet.xlsx").read_text().splitlines() == ["disease,symptoms", 'Flu,"fever, cough"']

    meta = clean_meta({"tier": "1", "kind": "guideline", "reports": "true", "publisher": "NCDC"}, "pdf", "dengue_2023.pdf")
    assert meta == {"title": "dengue 2023", "publisher": "NCDC", "edition": "", "licence": "Not stated", "tier": 1,
                    "kind": "guideline", "production_allowed": True}
    assert clean_meta({}, "records", "x.csv")["kind"] == "data" and clean_meta({}, "records", "x.csv")["tier"] == 5
    with pytest.raises(UploadError):
        clean_meta({"tier": "4"}, "pdf", "x.pdf")  # vocabularies are not uploaded here
    with pytest.raises(UploadError):
        clean_meta({"kind": "poster"}, "pdf", "x.pdf")


def test_which_sources_reports_use():
    assert used_in_reports(1, True, False, False) == "yes"
    assert used_in_reports(5, True, False, False) == "yes"  # medora-legacy
    assert used_in_reports(2, False, True, False) == "testing"  # MSF while testing sources are on
    assert used_in_reports(2, False, False, False) == "no"
    assert used_in_reports(5, False, False, True) == "testing"


def test_the_numbers_stay_visible_while_the_database_is_down(tmp_path):
    saved = tmp_path / "kb_summary.json"
    saved.write_text(json.dumps({"totals": {"passages": 44400}, "sources": [], "countedAt": "2026-10-29T10:00:00+00:00"}))
    stats = KnowledgeStats("postgresql://nobody@127.0.0.1:9/none", saved)
    out = stats.summary()
    assert (out["configured"], out["reachable"], out["totals"]["passages"]) == (True, False, 44400)
    assert out["countedAt"].startswith("2026-10-29") and out["error"]
    assert KnowledgeStats("", saved).summary()["configured"] is False


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'app.db'}", data_dir=tmp_path / "data",
                        background_tasks=False, knowledge_database_url="")
    with TestClient(create_app(settings)) as c:
        from tests.test_api import _seed_admin

        _seed_admin(c)
        yield c


def test_the_database_tab_reads_only_the_knowledge_database(client):
    headers = {"X-Admin-Key": "test-key"}
    assert client.get("/api/admin/knowledge/summary").status_code == 401
    summary = client.get("/api/admin/knowledge/summary", headers=headers).json()
    assert summary["configured"] is False and summary["totals"] is None
    assert summary["choices"]["tiers"]["1"] == "Indian government"
    up = client.post("/api/admin/knowledge/uploads", files={"file": ("x.csv", b"a,b\n1,2\n")}, headers=headers)
    assert up.status_code == 503 and "not set up" in up.json()["detail"]
    assert client.get("/api/admin/knowledge/uploads", headers=headers).status_code == 503
    assert client.get("/api/admin/knowledge/browse/passages", headers=headers).status_code == 404
    # The old Supabase endpoints are gone.
    assert client.get("/api/admin/knowledge/diseases", headers=headers).status_code == 404
    assert client.post("/api/admin/knowledge/init", headers=headers).status_code in (404, 405)
