"""Rows for the knowledge database from data files of no known layout.

The back office takes any CSV, JSON, OBO/OWL or XML file and any article: the
AI plans how it maps (app/ingest: sniff, planner, transform, articles) and
code applies the plan to every record into a `Staged` result. Here that
result becomes a `Bundle` (app/kb/load.py), loaded as a source of its own like
every other source: diseases, symptoms and medicines as `kb_entities`,
disease -> symptom pairs as `kb_disease_symptoms`, disease -> medicine as
`kb_disease_drugs`, advice as `kb_precautions`.

Medora's earlier knowledge tables (exported from the app database on
2026-10-30, source `medora-legacy`) are turned into the same rows.
"""

from collections import Counter

from ..ingest.transform import Staged, normalize
from .load import Bundle

_KIND = {"diseases": "disease", "symptoms": "symptom", "drugs": "drug"}


def _entity(bundle: Bundle, kind: str, name: str, aliases: list[str], enrich: bool = False, **text) -> None:
    bundle.add(
        "kb_entities", kind=kind, name=name, normalized=normalize(name), aliases=[a for a in aliases if a],
        description=text.get("description") or "", causes=text.get("causes") or "",
        dosage=text.get("dosage") or "", uses=text.get("uses") or "",
        side_effects=text.get("side_effects") or "", enrich=enrich,
    )


def _summarise(bundle: Bundle) -> None:
    rows = bundle.rows
    kinds = Counter(r["kind"] for r in rows.get("kb_entities", []) if not r["enrich"])
    bundle.stats = Counter({
        "diseases": kinds["disease"],
        "symptoms": kinds["symptom"],
        "drugs": kinds["drug"],
        "enriched names": sum(1 for r in rows.get("kb_entities", []) if r["enrich"]),
        "symptom links": len(rows.get("kb_disease_symptoms", [])),
        "drug links": len(rows.get("kb_disease_drugs", [])),
        "precautions": len(rows.get("kb_precautions", [])),
    })


def bundle_from_staged(staged: Staged) -> Bundle:
    bundle = Bundle()
    names: dict[str, dict[str, str]] = {}
    for table, drafts in staged.entities.items():
        names[table] = {key: draft.name for key, draft in drafts.items()}
        for draft in drafts.values():
            _entity(
                bundle, _KIND[table], draft.name, list(draft.aliases.values()), enrich=not draft.create,
                **{column: draft.text(column) for column in ("description", "causes", "dosage", "uses", "side_effects")},
            )
    for disease_key, table, other_key in sorted(staged.links):
        disease = names["diseases"].get(disease_key)
        other = names[table].get(other_key)
        if not disease or not other:
            continue
        if table == "symptoms":
            bundle.add("kb_disease_symptoms", disease=disease, normalized=disease_key, symptom=other,
                       symptom_normalized=other_key)
        else:
            bundle.add("kb_disease_drugs", disease=disease, normalized=disease_key, drug=other, drug_normalized=other_key)
    for disease_key, symptom_key, text in sorted(staged.precautions):
        bundle.add(
            "kb_precautions", disease=names["diseases"].get(disease_key, ""), normalized=disease_key,
            symptom=names["symptoms"].get(symptom_key, ""), symptom_normalized=symptom_key, precaution=text,
        )
    for reason, value in staged.reject_samples:
        bundle.refuse({"value": value}, reason)
    _summarise(bundle)
    return bundle


def bundle_from_legacy(data: dict) -> Bundle:
    """The export of the old knowledge tables (diseases, symptoms, drugs,
    links, precautions; ids are the old table ids)."""
    bundle = Bundle()
    diseases = {d["id"]: d["name"] for d in data["diseases"]}
    symptoms = {s["id"]: s["name"] for s in data["symptoms"]}
    drugs = {d["id"]: d["name"] for d in data["drugs"]}
    for d in data["diseases"]:
        _entity(bundle, "disease", d["name"], d.get("aliases") or [], description=d.get("description"),
                causes=d.get("causes"))
    for s in data["symptoms"]:
        _entity(bundle, "symptom", s["name"], s.get("aliases") or [], description=s.get("description"))
    for d in data["drugs"]:
        _entity(bundle, "drug", d["name"], d.get("aliases") or [], dosage=d.get("dosage"), uses=d.get("uses"),
                side_effects=d.get("side_effects"))
    for link in data["links"]:
        disease = diseases.get(link["disease_id"])
        if not disease:
            continue
        if link.get("symptom_id") in symptoms:
            symptom = symptoms[link["symptom_id"]]
            bundle.add("kb_disease_symptoms", disease=disease, normalized=normalize(disease), symptom=symptom,
                       symptom_normalized=normalize(symptom))
        elif link.get("drug_id") in drugs:
            drug = drugs[link["drug_id"]]
            bundle.add("kb_disease_drugs", disease=disease, normalized=normalize(disease), drug=drug,
                       drug_normalized=normalize(drug))
    for p in data["precautions"]:
        disease = diseases.get(p.get("disease_id"), "")
        symptom = symptoms.get(p.get("symptom_id"), "")
        if (disease or symptom) and p.get("precaution"):
            bundle.add("kb_precautions", disease=disease, normalized=normalize(disease), symptom=symptom,
                       symptom_normalized=normalize(symptom), precaution=p["precaution"])
    _summarise(bundle)
    return bundle
