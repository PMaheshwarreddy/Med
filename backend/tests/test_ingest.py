import asyncio
import json

import pytest
from app.ingest import records
from app.ingest.articles import extract_article
from app.ingest.plan import Plan
from app.ingest.planner import make_plan
from app.ingest.sniff import sniff
from app.ingest.transform import apply_plan, check_name, clean_name, clean_text, fuzzy_key, normalize
from app.llm import LlmError

LINK_PLAN = {
    "content": "records",
    "verdict": "usable",
    "summary": "Diseases with their symptoms",
    "confidence": 0.95,
    "outputs": [
        {"kind": "link", "disease": {"sources": ["disease"]}, "symptom": {"sources": ["symptoms"], "split": ","}}
    ],
}


class ScriptedLlm:
    """Answers from a list, in order, and records what it was asked."""

    name = "scripted"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    async def json(self, system, user):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def run(coro):
    return asyncio.run(coro)


# --- reading files ----------------------------------------------------------


def test_csv_rows_are_repaired(tmp_path):
    path = tmp_path / "messy.csv"
    path.write_text(
        "disease,symptoms\n"
        '"Flu,""fever, cough"""\n'  # whole row quoted as one field
        "Cold,sneezing,runny nose\n"  # unquoted list spilled into extra fields
        'Acne,"pimples, blackheads"\n'
        "\n"
    )
    assert list(records.iter_csv(path)) == [
        {"disease": "Flu", "symptoms": "fever, cough"},
        {"disease": "Cold", "symptoms": "sneezing, runny nose"},
        {"disease": "Acne", "symptoms": "pimples, blackheads"},
    ]


def test_json_records_are_found_and_streamed(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"total": 2},
                "results": [
                    {"openfda": {"generic_name": ["IBUPROFEN"], "brand_name": ["Advil", "Motrin"]}, "purpose": ["Pain reliever"]},
                    {"openfda": {}, "purpose": ["Antacid"]},
                ],
            }
        )
    )
    sniffed = sniff(path)
    assert (sniffed.format, sniffed.record_path) == ("json", "results")
    assert "openfda.generic_name[]" in sniffed.columns
    first, second = records.iter_json(path, "results")
    assert records.get_values(first, "openfda.brand_name[]") == ["Advil", "Motrin"]
    assert records.get_values(first, "openfda.generic_name[0]") == ["IBUPROFEN"]
    assert records.get_values(second, "openfda.generic_name[]") == []
    assert records.json_prefix("graphs[].nodes") == "graphs.item.nodes.item"


def test_obo_terms(tmp_path):
    path = tmp_path / "hp.obo"
    path.write_text(
        "format-version: 1.2\n\n[Term]\nid: HP:1\nname: Headache\n"
        'def: "Pain in the head." [ref]\nsynonym: "Cephalgia" EXACT []\n\n'
        "[Term]\nid: HP:2\nname: Old term\nis_obsolete: true\n\n[Typedef]\nid: part_of\nname: part of\n"
    )
    assert sniff(path).format == "obo"
    assert list(records.iter_obo(path)) == [
        {"id": "HP:1", "name": "Headache", "definition": "Pain in the head.", "synonyms": ["Cephalgia"]}
    ]


def test_format_comes_from_content_not_name(tmp_path):
    code = tmp_path / "diseases_final.csv"
    code.write_text("import json\nfrom pathlib import Path\n\nprint('x')\n")
    article = tmp_path / "data.bin"
    article.write_text("Disease : Asthma\n\nAsthma is a long-term disease.\n\n== Causes ==\nUnknown.\n")
    assert sniff(code).format == "code"
    assert sniff(article).format == "text"
    assert sniff(article).headings == ["Causes"]


# --- cleaning and validation ------------------------------------------------


def test_names_are_cleaned_and_matched():
    assert clean_name("  skin_rash ") == "Skin rash"
    assert clean_name("dischromic _patches") == "Dischromic patches"
    assert clean_name("FLUTICASONE PROPIONATE") == "Fluticasone propionate"
    assert clean_name("HIV") == "HIV"
    assert clean_name("Crohn's disease.") == "Crohn's disease"
    assert normalize("Skin_Rash") == normalize("skin rash") == "skin rash"
    assert normalize("Sjögren syndrome") == "sjogren syndrome"
    assert clean_name("HIV/AIDS") == "HIV/AIDS"
    assert clean_name("COVID-19") == "COVID-19"
    assert clean_name("TUBERCULOSIS") == "Tuberculosis"
    assert normalize("Alzheimer\u0092s Disease") == normalize("Alzheimer's disease") == "alzheimers disease"
    assert normalize("Obsessive–compulsive disorder") == normalize("Obsessive-compulsive disorder")
    assert fuzzy_key("chicken pox") == fuzzy_key("chickenpox")
    assert fuzzy_key("headaches") == fuzzy_key("headache")
    assert fuzzy_key("diabetes mellitus") != fuzzy_key("diabetes insipidus")


def test_name_validation():
    assert check_name("symptoms", "Fever") is None
    assert check_name("symptoms", "x") == "name_too_short"
    assert check_name("symptoms", "12345") == "name_has_no_letters"
    assert check_name("diseases", "Unknown") == "name_is_placeholder"
    assert check_name("drugs", "Inhaled corticosteroids") == "name_is_a_drug_class"
    assert check_name("drugs", "Long-acting beta agonists") == "name_is_a_drug_class"
    assert check_name("drugs", "Hydrocortisone") is None
    assert check_name("drugs", "Oral rehydration salts") is None
    sentence = "There is a popular misconception that tuberculosis is purely a disease of the lungs"
    assert check_name("symptoms", sentence) == "name_is_a_sentence"


def test_text_is_capped_at_a_sentence_and_headings_dropped():
    long = "First sentence. " * 200
    assert clean_text(long).endswith(".") and len(clean_text(long)) <= 2000
    assert clean_text("1 INDICATIONS AND USAGE Drug X is indicated for asthma.") == "Drug X is indicated for asthma."
    assert clean_text("ADVERSE REACTIONS The most frequent reactions are mild.") == "The most frequent reactions are mild."
    assert clean_text("DOSAGE AND ADMINISTRATION (See also WARNINGS) Take one.") == "(See also WARNINGS) Take one."
    assert clean_text("ISONIAZID tablets are white.") == "ISONIAZID tablets are white."


def test_apply_plan_stages_and_rejects():
    plan = Plan.model_validate(LINK_PLAN)
    staged = apply_plan(
        plan,
        [
            {"disease": "Flu", "symptoms": "fever, cough_dry, "},
            {"disease": "flu", "symptoms": "Fever, 123"},
            {"disease": "", "symptoms": "fever"},
        ],
    )
    assert set(staged.entities["diseases"]) == {"flu"}
    assert set(staged.entities["symptoms"]) == {"fever", "cough dry"}
    assert staged.links == {("flu", "symptoms", "fever"), ("flu", "symptoms", "cough dry")}
    assert staged.rejected == {"symptoms:name_has_no_letters": 1}


# --- planning ---------------------------------------------------------------


def test_plan_validation():
    with pytest.raises(ValueError, match="exactly one"):
        Plan.model_validate({**LINK_PLAN, "outputs": [{"kind": "link", "disease": {"sources": ["d"]}}]})
    with pytest.raises(ValueError, match="no column"):
        Plan.model_validate(
            {**LINK_PLAN, "outputs": [{"kind": "entity", "table": "symptoms", "name": {"sources": ["n"]}, "fields": {"dosage": {"sources": ["d"]}}}]}
        )
    junk = Plan.model_validate({**LINK_PLAN, "verdict": "junk"})
    assert junk.outputs == []


def test_planner_retries_an_unexecutable_plan(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("disease,symptoms\nFlu,fever\nCold,sneezing\n")
    wrong = json.loads(json.dumps(LINK_PLAN))
    wrong["outputs"][0]["disease"]["sources"] = ["Disease Name"]
    llm = ScriptedLlm(wrong, LINK_PLAN)
    plan = run(make_plan(llm, path.name, sniff(path)))
    assert plan.outputs[0].disease.sources == ["disease"]
    assert "'Disease Name' is not one of the available fields" in llm.prompts[1]

    llm = ScriptedLlm(wrong, wrong, wrong)
    with pytest.raises(LlmError, match="valid plan"):
        run(make_plan(llm, path.name, sniff(path)))


def test_article_extraction_drops_names_not_in_the_text():
    text = "Asthma is a long-term disease of the airways. Symptoms include wheezing and coughing. Salbutamol relieves attacks."
    llm = ScriptedLlm(
        {
            "disease": "Asthma",
            "aliases": ["Bronchial hyperreactivity syndrome"],
            "description": "A long-term airway disease.",
            "causes": "",
            "symptoms": ["wheezing", "coughing", "blue lips"],
            "drugs": ["salbutamol", "montelukast"],
            "precautions": ["Avoid smoke."],
        }
    )
    record, dropped = run(extract_article(llm, text))
    assert record["symptoms"] == ["wheezing", "coughing"]
    assert record["drugs"] == ["salbutamol"]
    assert set(dropped) == {"alias: Bronchial hyperreactivity syndrome", "symptom: blue lips", "drug: montelukast"}

    with pytest.raises(LlmError, match="not an article"):
        run(extract_article(ScriptedLlm({"disease": ""}), text))
    with pytest.raises(LlmError, match="does not occur"):
        run(extract_article(ScriptedLlm({"disease": "Malaria"}), text))


# --- the whole pipeline -----------------------------------------------------


def test_nested_json_records_are_located(tmp_path):
    path = tmp_path / "onto.json"
    path.write_text(
        json.dumps({"graphs": [{"id": "x", "nodes": [{"lbl": "Headache", "tags": [{"a": 1}, {"a": 2}, {"a": 3}]}, {"lbl": "Fever"}], "edges": [{"s": 1}, {"s": 2}]}]})
    )
    assert records.find_json_records(path) == "graphs[].nodes"
    assert [r["lbl"] for r in records.iter_json(path, "graphs[].nodes")] == ["Headache", "Fever"]
    flat = tmp_path / "flat.json"
    flat.write_text(json.dumps([{"a": 1, "parts": [{"p": 1}, {"p": 2}]}, {"a": 2}]))
    assert records.find_json_records(flat) == ""
    assert len(list(records.iter_json(flat, ""))) == 2


def test_obo_keeps_exact_synonyms_only(tmp_path):
    path = tmp_path / "t.obo"
    path.write_text(
        "format-version: 1.2\n\n[Term]\nid: X:1\nname: Night sweats\n"
        'synonym: "Nocturnal hyperhidrosis" EXACT layperson []\n'
        'synonym: "Sweating" BROAD []\nsynonym: "Hot flush" RELATED []\n'
    )
    assert next(records.iter_obo(path))["synonyms"] == ["Nocturnal hyperhidrosis"]


def test_bracketed_names_and_reversed_rows(monkeypatch):
    monkeypatch.setattr("app.ingest.transform.MAX_SYMPTOMS_PER_DISEASE", 3)
    plan = Plan.model_validate(LINK_PLAN)
    staged = apply_plan(
        plan,
        [
            {"disease": "Urinary tract infection (UTI)", "symptoms": "dysuria, fever"},
            {"disease": "urinary tract infection", "symptoms": "Fever"},
            # A symptom in the disease column, with conditions listed against it.
            {"disease": "Pain", "symptoms": "gout, sciatica, migraine, appendicitis"},
        ],
    )
    diseases = staged.entities["diseases"]
    assert set(diseases) == {"urinary tract infection"}
    assert list(diseases["urinary tract infection"].aliases.values()) == ["UTI"]
    assert set(staged.entities["symptoms"]) == {"dysuria", "fever"}
    assert staged.links == {
        ("urinary tract infection", "symptoms", "dysuria"),
        ("urinary tract infection", "symptoms", "fever"),
    }
    assert staged.rejected == {"diseases:too_many_symptoms_to_be_a_disease": 1}


OWL = """<?xml version="1.0"?>
<rdf:RDF xmlns="http://purl.obolibrary.org/obo/symp.owl#"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:obo="http://purl.obolibrary.org/obo/"
     xmlns:oboInOwl="http://www.geneontology.org/formats/oboInOwl#">
    <owl:Ontology rdf:about="http://purl.obolibrary.org/obo/symp.owl"/>
    <owl:Class rdf:about="http://purl.obolibrary.org/obo/SYMP_0000001">
        <oboInOwl:hasExactSynonym>stomach cramp</oboInOwl:hasExactSynonym>
        <oboInOwl:hasRelatedSynonym>bellyache</oboInOwl:hasRelatedSynonym>
        <oboInOwl:id>SYMP:0000001</oboInOwl:id>
        <obo:IAO_0000115>A cramp felt in the abdomen.</obo:IAO_0000115>
        <rdfs:label>abdominal cramp</rdfs:label>
    </owl:Class>
    <owl:Class rdf:about="http://purl.obolibrary.org/obo/SYMP_0000002">
        <owl:deprecated rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</owl:deprecated>
        <rdfs:label>obsolete thing</rdfs:label>
    </owl:Class>
</rdf:RDF>
"""

MESH = """<?xml version="1.0"?>
<DescriptorRecordSet LanguageCode="eng">
<DescriptorRecord DescriptorClass="1">
  <DescriptorUI>D007251</DescriptorUI>
  <DescriptorName><String>Influenza, Human</String></DescriptorName>
  <ConceptList>
    <Concept PreferredConceptYN="Y">
      <ConceptName><String>Influenza, Human</String></ConceptName>
      <ScopeNote>An acute viral infection in humans involving the respiratory tract.</ScopeNote>
      <TermList>
        <Term><String>Influenza, Human</String></Term>
        <Term><String>Influenza</String></Term>
        <Term><String>Grippe</String></Term>
      </TermList>
    </Concept>
  </ConceptList>
  <TreeNumberList><TreeNumber>C01.925.256.466.382</TreeNumber></TreeNumberList>
</DescriptorRecord>
<DescriptorRecord DescriptorClass="1">
  <DescriptorUI>D005334</DescriptorUI>
  <DescriptorName><String>Fever</String></DescriptorName>
  <ConceptList>
    <Concept PreferredConceptYN="Y">
      <ConceptName><String>Fever</String></ConceptName>
      <ScopeNote>An abnormal elevation of body temperature.</ScopeNote>
      <TermList><Term><String>Pyrexia</String></Term></TermList>
    </Concept>
    <Concept PreferredConceptYN="N">
      <ConceptName><String>Fever of Unknown Origin</String></ConceptName>
    </Concept>
  </ConceptList>
  <TreeNumberList><TreeNumber>C23.888.119.344</TreeNumber><TreeNumber>G07.345</TreeNumber></TreeNumberList>
</DescriptorRecord>
</DescriptorRecordSet>
"""


def test_owl_classes_are_read_like_obo_terms(tmp_path):
    path = tmp_path / "symptoms_ontology"  # no extension: format comes from content
    path.write_text(OWL)
    sniffed = sniff(path)
    assert sniffed.format == "owl" and sniffed.columns == list(records.OBO_KEYS)
    terms = list(records.iter_owl(path))
    # Deprecated classes are skipped; only EXACT synonyms count.
    assert terms == [
        {"id": "SYMP:0000001", "name": "abdominal cramp", "definition": "A cramp felt in the abdomen.", "synonyms": ["stomach cramp"]}
    ]


def test_xml_records_are_streamed_as_json_like_data(tmp_path):
    path = tmp_path / "descriptors.dat"
    path.write_text(MESH)
    sniffed = sniff(path)
    assert (sniffed.format, sniffed.record_path) == ("xml", "DescriptorRecord")
    assert "ConceptList.Concept.TermList.Term[].String" in sniffed.columns
    flu, fever = records.iter_xml(path, "DescriptorRecord")
    assert records.get_values(flu, "ConceptList.Concept[].TermList.Term[].String") == ["Influenza, Human", "Influenza", "Grippe"]
    # One child or several: an indexed path reads both the same way.
    assert records.get_values(flu, "ConceptList.Concept[0].ScopeNote") == ["An acute viral infection in humans involving the respiratory tract."]
    assert records.get_values(fever, "ConceptList.Concept[0].ScopeNote") == ["An abnormal elevation of body temperature."]
    assert records.get_values(fever, "TreeNumberList.TreeNumber[]") == ["C23.888.119.344", "G07.345"]
    assert records.get_values(fever, "@DescriptorClass") == ["1"]


def test_a_plan_may_pick_the_first_of_a_listed_field(tmp_path):
    path = tmp_path / "descriptors.dat"
    path.write_text(MESH)
    sniffed = sniff(path)
    plan = Plan.model_validate({
        "content": "records", "verdict": "usable", "confidence": 1,
        "outputs": [{"kind": "entity", "table": "symptoms", "mode": "enrich_only",
                     "name": {"sources": ["DescriptorName.String"]},
                     "aliases": {"sources": ["ConceptList.Concept[0].TermList.Term[].String"]},
                     "fields": {"description": {"sources": ["ConceptList.Concept[0].ScopeNote"]}}}],
    })  # fmt: skip
    assert plan.check_against(sniffed) == []
    bad = plan.model_copy(deep=True)
    bad.outputs[0].fields["description"].sources = ["ConceptList.Concept[0].NoSuchThing"]
    assert bad.check_against(sniffed)
    # Only the preferred concept's terms: "Fever of Unknown Origin" is not fever.
    fever = list(records.iter_xml(path, "DescriptorRecord"))[1]
    assert records.get_values(fever, "ConceptList.Concept[0].TermList.Term[].String") == ["Pyrexia"]
