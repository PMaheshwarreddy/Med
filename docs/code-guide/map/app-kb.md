# `app/kb`

## `backend/app/kb/__main__.py` (177 lines)

Knowledge base pipeline: python -m app.kb <command>

init                 create the tables (safe to repeat)
load <key>... | all  read, check and load sources (see app/kb/sources.py)
link                 connect rows across sources (conditions, drugs)
embed [n]            compute MedCPT vectors for passages that lack one (trusted first; resumable)
snapshot             save the allowed passages and vectors for offline search (data/rag_cache)
rebuild              everything, in order, into an empty or existing database:
                     init, load all, link, embed, snapshot
quantize             int8 copy of the MedCPT Cross-Encoder (run as: uv run --with onnx python -m app.kb quantize)
search <question>    try the guideline search (pass 1 style) and print the passages
status               what is loaded, quarantined and rejected

Uses (inside the app): `embed`, `retrieve`, `settings`, `sources`, `text`

Settings and constants:
- **L26** `ROOT`
- **L45** `HF_DIR`

Functions and classes:
- **L29–42** `def _order`
- **L48–66** `def _path`  
  A local file, or 'hf:<owner>/<name>/<file>' downloaded once into data/hf/.
- **L69–97** `def cmd_load`
- **L100–112** `def cmd_status`
- **L115–120** `def _retriever`
- **L123–172** `def main`

## `backend/app/kb/checks.py` (64 lines)

Checks in code that stand in for a person reviewing each page.

A page or row that fails goes to `kb_quarantine` with the reason; it is
never loaded silently and never dropped silently.

Uses (inside the app): `text`

Settings and constants:
- **L12** `MIN_COVERAGE`
- **L15** `MAX_REJECT_RATE`
- **L17** `_UNIT`
- **L23** `_NOT_A_DRUG`

Functions and classes:
- **L29–31** `def unknown_numbers`  
  Numbers in the extraction that the source page does not contain.
- **L34–40** `def coverage`  
  Share of the source's distinct words (3+ letters) found in the extraction.
- **L43–58** `def dose_problem`  
  Why a dose row cannot be stored, or '' when it can.
- **L61–63** `def too_many_rejects`

## `backend/app/kb/drugnames.py` (96 lines)

One key per medicine across sources: Indian (BAN/INN), WHO (INN) and US
(USAN) spellings meet here, so 'Amoxycillin', 'amoxicillin', 'Adrenaline
(Epinephrine)' and 'acetaminophen' land on the same row as their siblings.

The key is the INN-style spelling, lower case; the name shown stays as the
first source printed it. Every spelling seen is kept as a drug term.

Uses (inside the app): `text`

Settings and constants:
- **L14** `_WORDS`
- **L32** `_SALTS`
- **L38** `_PAREN`
- **L39** `_JOINERS`
- **L79** `_INDIAN`

Functions and classes:
- **L42–48** `def _words`
- **L51–53** `def canonical`  
  The shared key: INN spelling, bracketed alternatives and joiners removed.
- **L56–59** `def stripped`  
  The key without salt words ('metformin hydrochloride' -> 'metformin').
- **L62–75** `def spellings`  
  Names to keep as terms: as printed, without the brackets, and each bracketed alternative.
- **L86–95** `def indian`  
  'Acetaminophen 500 mg' -> 'Paracetamol 500 mg' (case kept); other names unchanged.

## `backend/app/kb/embed.py` (159 lines)

MedCPT encoders on ONNX Runtime (CPU), and the stage that fills
`kb_chunks.embedding`.

MedCPT (NCBI) is three BERT models trained together on PubMed search logs:
- Article Encoder: a passage as (title, text), up to 512 tokens -> 768 numbers.
  Here the title is the passage's breadcrumb.
- Query Encoder: a short query, up to 64 tokens -> 768 numbers.
- Cross-Encoder: scores one (query, passage) pair; used to re-rank.
Vectors are compared by dot product (how MedCPT was trained), so the index
uses inner product. Models: data/models/medcpt/<name>/model.onnx, converted
from the official ncbi/MedCPT-* weights and checked against PyTorch.

Uses (inside the app): `load`

Settings and constants:
- **L24** `MODELS`
- **L25** `BATCH`

Functions and classes:
- **L28–52** `class _Encoder`
  - **L29–43** `def __init__`
  - **L45–52** `def run`
- **L55–57** `def article_encoder`
- **L60–62** `def query_encoder`
- **L65–73** `def cross_encoder`
- **L76–84** `def quantize_cross_encoder`  
  Writes model.int8.onnx next to the Cross-Encoder. Needs the `onnx` package, which the app does not: run with `uv run --with onnx`.
- **L87–89** `def embed_passages`  
  [(breadcrumb, text)] -> (n, 768).
- **L92–93** `def embed_queries`
- **L96–98** `def rerank`  
  Relevance score for each passage (higher is better).
- **L101–102** `def _vector`
- **L105–158** `def embed_missing`  
  Embeds every passage that has no vector yet, in batches, then makes sure the vector index exists. Resumable: a re-run picks up what is left. With `url`, a batch whose write fails (dropped connection, time limit) reconnects and is written again, up to 5 times in a row.

## `backend/app/kb/load.py` (316 lines)

Writes what a reader produced into the knowledge database.

A source is loaded in ONE transaction: its earlier rows are removed and the
new ones written, so a re-run gives the same result and a failure leaves the
previous load in place. Embeddings of passages whose text did not change are
kept, so a reload does not recompute them.

Uses (inside the app): `drugnames`, `sources`, `text`

Settings and constants:
- **L24** `SCHEMA`
- **L27** `OWNED`
- **L33** `DRUG_COLUMNS`
- **L39** `COLUMNS`
- **L239** `LINK_SQL`

Functions and classes:
- **L60–69** `def connect`
- **L72–95** `def init_schema`  
  Creates the tables (safe to repeat). On a company server the Medora user may not be allowed to create extensions: then the two extensions must already exist, and the message says what the admin has to run.
- **L98–146** `class Bundle`  
  Everything one source produced, by table.
  - **L106–108** `def add`
  - **L110–111** `def refuse`
  - **L113–120** `def drug`  
    Adds or updates a medicine under its shared key; every spelling becomes a drug term.
  - **L122–129** `def drug_terms`
  - **L131–146** `def passages`  
    Adds a section as one or more passages; returns their hashes.
- **L149–152** `def _value`
- **L155–219** `def load`
- **L222–225** `def _copy_value`
- **L228–236** `def mark_failed`
- **L301–315** `def link`  
  Connects rows across sources (conditions, drugs) after loading.

## `backend/app/kb/rag.py` (296 lines)

The two retrieval passes of a report, and the dose check after it.

  understand -> PASS 1 -> specialist panel + chair -> PASS 2 -> report writer -> checks
                (what could this be: presentation,   (how is it treated: treatment,
                 red flags, tests, referral)           doses and safety for the
                                                       conditions the chair named)

Pass 1 can only ask "what could this be?": the conditions are not known yet.
Pass 2 asks about treatment for the conditions the panel actually concluded,
so the writer reads the doses that matter instead of doses for every
condition the symptoms might suggest.

After the writer, every medicine's dose is looked up: in the pass-2 passages
and the medicine's printed doses (kb_doses). The result is recorded for the
doctor (`doseEvidence`); it does not change which medicines are shown (that
rule waits for the user's decision).

Uses (inside the app): `drugnames`, `retrieve`, `text`

Settings and constants:
- **L26** `PASS1_K`
- **L27** `PASS2_PER_CONDITION`
- **L28** `PASS2_MAX`
- **L29** `PASS2_RERANK`
- **L30** `PRINTED_PER_CONDITION`
- **L31** `PAGE_BOXES`
- **L35** `_GROUP_WORDS`
- **L41** `_DOSE_IN_TEXT`

Functions and classes:
- **L44–51** `def _who`
- **L54–58** `def pass1_question`  
  Short enough for the Query Encoder (64 tokens): who, what, how long.
- **L61–74** `def pass1`  
  `consider`: up to 3 conditions the symptom-understanding step names for looking up (the likely one and a dangerous one). Their own guideline pages join the candidates, judged against this patient's presentation; the panel is told that a passage does not make a condition likely.
- **L77–88** `def fits_patient`  
  False when a box's heading names only another patient group.
- **L91–103** `def _page_boxes`  
  Treatment boxes from the same guideline page as a condition's best passage, for this patient's group: "Cystitis in females (nitrofurantoin 100 mg BD x 5d)" when the search found "Male UTI" on that page.
- **L106–132** `def pass2`
- **L135–160** `def printed_doses`  
  Doses printed FOR the concluded conditions (STW pages, NFI indications), as a block for the writer and as rows for the dose check.
- **L163–167** `def number`  
  Labels [S1].. across both passes (pass 1 first).
- **L170–189** `def brands_taken`  
  'Dolo 650, Pan D' -> a line saying what each brand contains, from the brand table (256k Indian and US brands). Empty when nothing is known.
- **L192–203** `def _lines_naming`  
  Lines of a passage that name the medicine and carry a dose.
- **L206–233** `def dose_conflicts`  
  For the pharmacist review, written by code: each drafted medicine whose dose is NOT in the guideline lines that name it, with those lines. (The writer once gave ciprofloxacin the 100 mg printed for nitrofurantoin.)
- **L236–261** `def check_doses`  
  Adds `doseEvidence` to each medicine: whether its dose numbers were found in a guideline passage, a printed dose for the concluded conditions, or a printed dose for that medicine.

## `backend/app/kb/readers/codes.py` (48 lines)

ICD-10-CM (CDC order file) and ICD-11 MMS (WHO simple tabulation): codes and titles.

Uses (inside the app): `load`, `sources`

Functions and classes:
- **L9–18** `def _icd10cm`
- **L21–41** `def _icd11`
- **L44–47** `def read`

## `backend/app/kb/readers/fda.py` (116 lines)

US FDA drug labels (openFDA, 14 files, 8 GB): one label per medicine and route.

Only medicines already in the knowledge base (NLEM, NFI, WHO) are kept: the
labels are a fallback for safety detail, not a catalogue. US names meet the
Indian ones through `drugnames` (acetaminophen = paracetamol). For each
medicine and route the most complete label wins (prescription first, then
the most sections, then the newest). Its safety sections become
kb_drug_safety rows and passages; its dosing becomes a passage marked as a
US label (Indian sources come first for doses).

Uses (inside the app): `drugnames`, `load`, `sources`, `text`

Settings and constants:
- **L22** `SECTIONS`
- **L38** `MAX_WORDS`

Functions and classes:
- **L41–45** `def match_key`  
  Name for matching US labels: salt words dropped, unless the name is only salts ('Magnesium sulfate', 'Potassium nitrate'), then kept whole.
- **L48–68** `def _scan`
- **L71–73** `def _cap`
- **L76–115** `def read`

## `backend/app/kb/readers/guideline.py` (286 lines)

Any clinical guideline PDF with a text layer (national programme
guidelines, treatment manuals, formularies written as prose), read by code.

  1. Lines are rebuilt from words with their font size and weight
     (pdfplumber). A page whose words never cross its middle is two columns
     and is read left column first.
  2. Lines printed on many pages at the same place (running heads, footers,
     page numbers) are removed.
  3. Headings are lines clearly larger than the body text, or short bold
     lines; their level follows their size. Each heading path becomes the
     passage breadcrumb: "<source> › <chapter> › <section>".
  4. Tables (pdfplumber) become Markdown in the section they sit in; their
     words are left out of the running text.
  5. A page with almost no text layer (a scanned or image page) is read by
     Gemini vision with the same check as the ICMR posters: a box with a
     number not visible in the PDF is dropped. Without a Gemini key such
     pages are quarantined.

Nothing is paraphrased: passages are the PDF's own words, so no number can be
invented. Structured doses are not extracted from prose (too easy to attach a
dose to the wrong drug); the writer reads them in the passages.

Register a PDF in sources.py with reader "guideline", e.g.
  Source("nvbdcp-malaria-2014", "National Drug Policy on Malaria", "NVBDCP, MoHFW", "2013",
         "guideline", 1, "Government of India publication", True,
         ("medora_5/malaria_drug_policy.pdf",), "guideline")

Uses (inside the app): `checks`, `load`, `sources`, `stw`, `text`

Settings and constants:
- **L42** `_NUMBERED`
- **L43** `_REFERENCES`
- **L45** `_PAGE_FOOTER`
- **L46** `MIN_TEXT_WORDS`
- **L47** `HEADER_SHARE`
- **L49** `_KINDS`
- **L58** `VISION_PROMPT`

Functions and classes:
- **L65–69** `def _kind`
- **L72–111** `def _lines`  
  [{top, x0, size, bold, text}] in reading order, tables removed.
- **L114–121** `def _diagram`  
  A flowchart or decision chart: many lines of a few words each, which read as jumbled fragments. Such pages go to the vision reader.
- **L124–131** `def _furniture`  
  Lines repeated across pages: running heads, footers, page numbers.
- **L134–145** `async def _vision_pages`
- **L148–285** `def read`

## `backend/app/kb/readers/hf.py` (287 lines)

Community datasets from Hugging Face, one small mapping per dataset (code,
no model). They land in their own rows, tier 5, testing only:

- disease -> symptom lists: kb_disease_symptoms (and passages where there is text)
- medicine brands: kb_drug_products (composition parsed into drug + strength)
- a list of disease names: condition terms

The same data uploaded under several names is loaded once: brand sets skip
brands another source already holds, and disease lists drop repeated pairs.

Uses (inside the app): `drugnames`, `load`, `sources`, `text`

Settings and constants:
- **L26** `_PART`
- **L27** `_FORMS`
- **L247** `_QA`
- **L261** `_INSTRUCT`
- **L275** `READERS`

Functions and classes:
- **L31–45** `def _rows`
- **L48–57** `def _symptoms`
- **L60–71** `def _disease_symptoms`
- **L74–88** `def composition`
- **L91–93** `def composition_key`
- **L96–100** `def _form`
- **L103–107** `def _price`
- **L110–130** `def _product`
- **L133–136** `def _held_brands`
- **L141–150** `def _disease_database`
- **L153–166** `def _mayo`
- **L169–172** `def _medlineplus_symptoms`
- **L175–180** `def _kaggle_41`
- **L183–199** `def _json_symptom`  
  Part Kaggle set, part reversed co-occurrence pairs ('disease: Muscle Weakness, symptom: Angiolipoma'): a 'disease' that is only known as a symptom is refused.
- **L202–205** `def _columbia`
- **L208–216** `def _symptoms_doctors`
- **L219–230** `def _all_diseases`
- **L233–238** `def _indian_brands`
- **L241–244** `def _1mg`
- **L250–258** `def _1mg_qa`
- **L264–272** `def _1mg_instruct`
- **L283–286** `def read`

## `backend/app/kb/readers/legacy.py` (15 lines)

Medora's earlier knowledge tables, exported from the app database
(Supabase) on 2026-10-30 when knowledge moved to the knowledge database only.
See app/kb/staged.py for the rows they become.

Uses (inside the app): `load`, `sources`, `staged`

Functions and classes:
- **L13–14** `def read`

## `backend/app/kb/readers/medgen.py` (34 lines)

MedGen names (MGCONSO.RRF): English synonyms for concepts that Disease
Ontology, HPO or the Symptom Ontology already link by UMLS CUI. Nothing new
is created from MedGen; it only adds other names for what is there.

Uses (inside the app): `load`, `sources`, `text`

Functions and classes:
- **L12–33** `def read`

## `backend/app/kb/readers/medlineplus.py` (45 lines)

MedlinePlus health topics (NLM): plain-English summaries, English only.

Uses (inside the app): `load`, `sources`, `text`

Functions and classes:
- **L13–23** `def _text`
- **L26–44** `def read`

## `backend/app/kb/readers/mesh.py` (39 lines)

MeSH descriptors for diseases (C), mental disorders (F03) and signs and
symptoms (C23.888): the preferred concept's terms only (its narrower
concepts are different things).

Uses (inside the app): `load`, `sources`, `text`

Functions and classes:
- **L14–38** `def read`

## `backend/app/kb/readers/nfi.py` (390 lines)

National Formulary of India 2011, read by code (no model).

- Monographs (pages 39-660): a drug name at the left margin, optional
  "Pregnancy Category-X" / "Schedule H", then labelled fields (Indications,
  Availability, Dose, Contraindications, Precautions, Adverse Effects,
  Storage) with their text in a right-hand column.
- Appendix 6c: drug interactions, an UPPER CASE drug followed by rows
  "other drug | effect".
- Chapter introductions and the other appendices: passages.

Lines are rebuilt from word positions (pdfplumber), so a label and its value
are told apart by the gap between them, not by spacing in extracted text.

Uses (inside the app): `checks`, `load`, `sources`, `text`

Settings and constants:
- **L26** `END_PAGE`
- **L27** `GAP`
- **L29** `LABELS`
- **L35** `APPENDIX_TABLES`
- **L36** `SAFETY`
- **L37** `_PREG`
- **L38** `_SCHED`
- **L39** `_FOOTER`
- **L40** `_ROUTE`
- **L88** `_LABEL_FAMILY`
- **L91** `_FAMILY_KEYS`
- **L102** `_LABEL_PREFIX`
- **L105** `_NUMBERED`
- **L106** `_REFER`
- **L277** `_APPENDIX_TITLES`
- **L344** `_APPENDIX_COLUMNS`

Functions and classes:
- **L43–63** `def lines_of`  
  [(x of first word, [(x, segment text), ...])] top to bottom.
- **L66–76** `def _join`
- **L79–85** `class _Monograph`
  - **L80–85** `def __init__`
- **L94–99** `def _label`  
  The field a label names, spelling slips included ('Avaialbility:', 'Dosage:').
- **L109–115** `def _split_label`  
  'Contraindications Porphyria.' printed without a gap -> label, value.
- **L118–127** `def _name`  
  The drug name from the short lines before the labels (headings dropped).
- **L130–227** `def read`
- **L230–241** `def _paragraphs`
- **L244–274** `def _emit_monographs`
- **L281–298** `def _cell_starts`  
  Column starts: the x where cells begin again and again on this page (each row's first word in a column), merged within 8 points.
- **L301–341** `def _table_rows`  
  Reads one page of a 'Drug | ... ' appendix table word by word: the header row ('Drug', 'Status', 'Comments' ...) gives each column's x, every word goes to its column, and a row starts where the Drug column has a word starting with a capital. Returns the header's column starts (kept for the next page, which may print no header).
- **L351–372** `def _emit_appendix`
- **L375–389** `def _emit_interactions`

## `backend/app/kb/readers/nlem.py` (134 lines)

National List of Essential Medicines 2022: the medicine tables.

Each medicine: its NLEM code, section, care levels (P primary, S secondary,
T tertiary) and dosage forms with strengths. Read from the PDF's own tables
(pdfplumber), no model. The list ends where the alphabetical index begins;
the 'added' and 'deleted' annexes repeat it and are not read.

Uses (inside the app): `load`, `sources`, `text`

Settings and constants:
- **L18** `_CODE`
- **L19** `_SECTION`
- **L20** `_LEVELS`
- **L21** `_MARKERS`

Functions and classes:
- **L24–25** `def _key`
- **L28–31** `def _name`
- **L34–41** `def _forms`
- **L44–133** `def read`

## `backend/app/kb/readers/ontology.py` (123 lines)

Disease Ontology (conditions), Human Phenotype Ontology and Symptom
Ontology (symptoms): names, exact synonyms and cross-references only.

Uses (inside the app): `load`, `sources`, `text`

Settings and constants:
- **L13** `_SYN`
- **L14** `_HP_ROOT`
- **L97** `_NS`

Functions and classes:
- **L17–43** `def obo_terms`
- **L46–52** `def _xrefs`
- **L55–62** `def _terms`
- **L65–74** `def _read_doid`
- **L77–94** `def _read_hpo`
- **L105–116** `def _read_symp`
- **L119–122** `def read`

## `backend/app/kb/readers/stw.py` (295 lines)

ICMR Standard Treatment Workflows: one-page infographic posters.

Plain text extraction scrambles these (boxes, columns, flowchart arrows), so
each poster page is read twice and the two readings are checked against each
other:

- Gemini (vision) reads the page image into sections, doses and red flags:
  it understands the layout but may misread or invent.
- The PDF's own text layer holds the exact characters but not the layout.

A page is loaded only if every number in the vision reading is in the text
layer and the reading covers most of the page's words; otherwise the whole
page is quarantined. Doses are checked one by one again (a real medicine, an
amount with a unit, numbers on the page). Vision results are cached by page
image, so a re-run costs no model calls.

Uses (inside the app): `checks`, `llm`, `load`, `sources`, `text`

Settings and constants:
- **L36** `MODEL`
- **L39** `PARTIAL_COVERAGE`
- **L40** `PROMPT_VERSION`
- **L41** `CONCURRENCY`
- **L42** `CACHE`
- **L43** `_ICD`
- **L44** `_TITLE_PREFIX`
- **L47** `_REFERENCES`
- **L48** `_SKIP_HEADINGS`
- **L51** `PROMPT`
- **L72** `_SHORTER`

Functions and classes:
- **L76–81** `def _page_image`
- **L84–124** `async def _vision`  
  One reading of a page image. `note` asks a second reading to fix what the checks found missing. Broken or runaway JSON gets one more try at a different temperature.
- **L127–130** `def _boilerplate`  
  Words on most pages of the volume: header, footer, disclaimer.
- **L133–141** `def _transcript`
- **L144–149** `def _check`
- **L152–154** `def _score`
- **L157–168** `def _correction`
- **L171–181** `def _title`  
  'Standard Treatment Workflow (STW) for the Management of DENGUE FEVER' -> 'Dengue Fever'.
- **L184–186** `def _short`
- **L189–288** `async def _read_all`
- **L291–294** `def read`

## `backend/app/kb/readers/who_eml.py` (74 lines)

WHO Model List of Essential Medicines (24th list, 2025).

Medicine names sit in the left column, vertically centred beside their
dosage forms. Pairing each name with its strength lines by position was
tried (2026-10-27) and put strengths on the wrong medicine at block
boundaries (diazepam got carbamazepine's tablets), so it is not done: a wrong
strength is worse than none. What is taken: each medicine and its sections
(kb_drugs.who_eml), and each section as passages, where the strengths and
the antibiotic first/second-choice lists are kept as printed, columns apart
by " | ".

Uses (inside the app): `drugnames`, `load`, `nfi`, `sources`, `text`

Settings and constants:
- **L24** `_SECTION`
- **L25** `_MARKS`
- **L26** `_STOP`
- **L28** `_NOT_NAME`

Functions and classes:
- **L31–73** `def read`

## `backend/app/kb/retrieve.py` (612 lines)

Guideline retrieval (RAG) over the knowledge database, with MedCPT.

One search:
  1. the question is encoded by the MedCPT Query Encoder, and turned into a
     keyword query (any of its words);
  2. two candidate lists: nearest passages by vector (pgvector, inner product)
     and best full-text matches (Postgres), each limited to allowed sources
     and to the sections that suit the question;
  3. the lists are fused by rank (reciprocal rank fusion, k = 60), Indian
     government and WHO/NLM sources nudged up;
  4. the MedCPT Cross-Encoder reads each (question, passage) pair and the best
     few are kept, labelled [S1], [S2] ... for citation.

Which sources a report may use: those marked production_allowed, plus
"testing" sources (ICMR STW, NFI, WHO; awaiting permission) when
`knowledge_testing_sources` is on, plus community (Hugging Face) sources only
when `knowledge_community_sources` is on.

Offline (the database unreachable), the same search runs on a snapshot of
the allowed passages saved by `python -m app.kb snapshot` (vectors and text
in data/rag_cache/), with keyword overlap in place of full-text search.

Uses (inside the app): `drugnames`, `embed`, `text`

Settings and constants:
- **L38** `RRF_K`
- **L39** `CANDIDATES`
- **L40** `RERANK`
- **L45** `RERANK_WINDOW`
- **L49** `TOPIC_CANDIDATES`
- **L50** `_GENERIC`
- **L52** `TIER_BOOST`
- **L57** `TIER_RERANK`
- **L58** `EXCERPT_CHARS`
- **L59** `MAX_LEAFLETS`
- **L62** `RETRY_AFTER`
- **L65** `DIAGNOSIS`
- **L66** `TREATMENT`
- **L73** `_DRUG_REFERENCE`
- **L74** `_PREFERRED`
- **L78** `KIND_BOOST`
- **L91** `_SECTION_SQL`
- **L571** `_NEW_ITEM`

Functions and classes:
- **L81–84** `def _section_kind`
- **L87–88** `def _preferred`
- **L97–119** `class Passage`
  - **L112–119** `def cite`  
    For the stored report (camelCase, like the rest of it).
- **L122–143** `class Evidence`  
  What one pass found, ready to put in a prompt.
  - **L130–143** `def prompt`  
    The passages for a prompt; `most` and `chars` shorten it (offline, where the local model reads about 20 tokens a second).
- **L146–151** `def _topic_core`  
  'Uncomplicated urinary tract infection' -> 'urinary tract infection': the words a guideline heading would use. Too short to be specific: ''.
- **L154–155** `def _vector_text`
- **L158–167** `def _keyword_query`  
  Any of the question's meaningful words, for to_tsquery.
- **L170–552** `class Retriever`  
  Thread-safe: one database connection, used under a lock.
  - **L173–182** `def __init__`
  - **L185–208** `def _connection`
  - **L210–221** `def _query`
  - **L223–229** `def _source_filter`
  - **L232–240** `def warm`  
    Loads the three MedCPT models (about 2 s), so the first report does not.
  - **L242–297** `def search`  
    The best passages for one question; `kind` is DIAGNOSIS or TREATMENT. `topics` (and `topic_hint`) are condition names whose own guideline passages join the candidates; the cross-encoder still judges every candidate against the question, so a topic passage that does not fit the patient falls out.
  - **L299–330** `def _candidates_db`
  - **L332–349** `def _topic_candidates_db`  
    Each named condition's own passages (its name in the heading): the pass's own kind of section first (how to suspect it for pass 1, its treatment for pass 2), Indian sources first, then the closest to the question. International passages still come through the main search.
  - **L351–362** `def _topic_candidates_snapshot`
  - **L364–388** `def page_boxes`  
    The other boxes of the same guideline page (same source, page and topic). A treatment workflow splits one condition into boxes per patient group ("Cystitis in females", "Male UTI"); a search may find only one of them.
  - **L391–401** `def drug_id`
  - **L403–415** `def doses`  
    Printed doses for a medicine from the allowed sources, Indian first.
  - **L417–434** `def condition_doses`  
    Printed doses given FOR a condition (STW pages about it, NFI entries whose indications name it), Indian sources first.
  - **L436–446** `def safety`
  - **L448–469** `def drug_names`  
    Every medicine name in the guideline database, loaded once (for the doctor's type-ahead); empty while the database is unreachable.
  - **L471–483** `def brand`  
    What a brand the patient took contains ('Dolo 650' -> paracetamol 650 mg).
  - **L486–518** `def save_snapshot`  
    Saves the allowed, embedded passages for offline search. Runs on its own connection without the 8 s query limit (tens of thousands of vectors over a LAN take minutes), reads in batches, and replaces the old snapshot only once the new one is complete.
  - **L520–526** `def _load_snapshot`
  - **L528–552** `def _candidates_snapshot`
- **L555–568** `def label`  
  Numbers the passages of several passes [S1], [S2] ... without repeats.
- **L574–611** `def dose_found`  
  Whether a written dose's numbers all appear next to the medicine's name: on the line that names it (and its continuation lines), or anywhere in a text whose first line (heading, breadcrumb) is about that medicine. "Nitrofurantoin 100 mg BD" two lines above "Ciprofloxacin 500 mg BD" is not evidence for ciprofloxacin 100 mg.

## `backend/app/kb/sources.py` (168 lines)

Every source the knowledge base takes, with its licence and tier.

A source is registered here once, by a person, with what its licence allows:
nothing is loaded from a file that is not listed (unknown licence = not
loaded). `production_allowed` is what report generation will check: a source
that needs permission is loaded and tested now and switched on later.

Paths are relative to the repository root. `reader` names a module in
`app/kb/readers/`; `after` lists sources that must be loaded first (the FDA
labels are filtered to the drugs the Indian lists hold, for example).

Settings and constants:
- **L32** `_STW_LICENCE`
- **L33** `_STW_NOTE`
- **L104** `_HF_NOTE`
- **L145** `BY_KEY`
- **L148** `REJECTED`

Functions and classes:
- **L16–29** `class Source`
- **L108–111** `def _hf`

## `backend/app/kb/staged.py` (112 lines)

Rows for the knowledge database from data files of no known layout.

The back office takes any CSV, JSON, OBO/OWL or XML file and any article: the
AI plans how it maps (app/ingest: sniff, planner, transform, articles) and
code applies the plan to every record into a `Staged` result. Here that
result becomes a `Bundle` (app/kb/load.py), loaded as a source of its own like
every other source: diseases, symptoms and medicines as `kb_entities`,
disease -> symptom pairs as `kb_disease_symptoms`, disease -> medicine as
`kb_disease_drugs`, advice as `kb_precautions`.

Medora's earlier knowledge tables (exported from the app database on
2026-10-30, source `medora-legacy`) are turned into the same rows.

Uses (inside the app): `ingest.transform`, `load`

Settings and constants:
- **L20** `_KIND`

Functions and classes:
- **L23–29** `def _entity`
- **L32–43** `def _summarise`
- **L46–74** `def bundle_from_staged`
- **L77–111** `def bundle_from_legacy`  
  The export of the old knowledge tables (diseases, symptoms, drugs, links, precautions; ids are the old table ids).

## `backend/app/kb/stats.py` (172 lines)

What the knowledge database holds, for the back office's Database tab.

Counted live from the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL) and
kept for a few seconds, so a page that refreshes itself does not count again
on every request. When the database cannot be reached the last numbers that
were read are returned (also after a restart: they are saved to disk), marked
as not current.

Settings and constants:
- **L21** `FRESH_FOR`
- **L22** `RETRY_AFTER`
- **L24** `_TOTALS`
- **L52** `_TOTAL_KEYS`
- **L59** `_SOURCES`

Functions and classes:
- **L66–76** `def used_in_reports`  
  'yes' (allowed), 'testing' (only because a testing switch is on) or 'no': the same rule as the guideline search (retrieve.py) and the symptom index (knowledge_base.py).
- **L79–171** `class KnowledgeStats`
  - **L80–92** `def __init__`
  - **L94–97** `def forget`  
    Count again at the next request (after a load).
  - **L99–122** `def summary`
  - **L124–141** `def _count`
  - **L143–148** `def _save`
  - **L150–154** `def _read_saved`
  - **L156–171** `def _offline`  
    The offline copy of the guideline search (passages and when saved).

## `backend/app/kb/text.py` (116 lines)

Text helpers shared by the readers: normalising names, numbers, chunking.

Settings and constants:
- **L9** `MAX_TOKENS`
- **L10** `OVERLAP_WORDS`
- **L12** `_SPACE`
- **L13** `_NON_WORD`
- **L14** `_NUMBER`

Functions and classes:
- **L17–21** `def clean`  
  Unicode-normalised text with single spaces (newlines kept).
- **L24–27** `def normalize`  
  Lower-case letters and digits only, for matching names across sources.
- **L30–38** `def numbers`  
  Every number in the text, written one way (decimal point, no trailing zeros).
- **L41–42** `def words`
- **L45–46** `def content_hash`
- **L49–54** `def file_sha256`
- **L57–64** `def _tokenizer`
- **L67–72** `def count_tokens`  
  MedCPT tokens when its tokenizer is present, else an estimate.
- **L75–115** `def chunk`  
  Splits a section into passages that fit MedCPT with the breadcrumb.

## `backend/app/kb/uploads.py` (568 lines)

Files uploaded in the back office (Database tab) into the knowledge database.

Every upload becomes a source of its own, loaded exactly like a source
registered in sources.py and loaded with `python -m app.kb load`: the same
readers, checks, quarantine, linking, embedding and offline snapshot. Nothing
goes to the app database (Supabase); the history lives in `kb_uploads`.

  PDF (guideline, drug book, patient information)
      the `guideline` reader (text layer; picture pages through Gemini vision
      with the number check) -> load -> link -> embed -> offline snapshot.
      Starts at once: whoever uploads states the publisher and licence.
  Data file (CSV, TSV, JSON, OBO/OWL, XML, Excel)
      the AI plans how its columns map (app/ingest), code applies the plan;
      the plan and a preview wait for approval, because the planner has been
      wrong before (package sizes mapped to doses). Approve -> load -> link.
  Article (plain text about one disease)
      the AI extracts its facts, every name checked against the text; waits
      for approval like a data file.

One file is worked on at a time; the others wait. A server restart marks a
file that was in the middle of a step as interrupted (Retry picks it up).

Uses (inside the app): `embed`, `ingest`, `ingest.articles`, `ingest.plan`, `ingest.planner`, `ingest.sniff`, `ingest.transform`, `llm`, `readers`, `sources`, `staged`

Settings and constants:
- **L50** `PREVIEW_RECORDS`
- **L53** `MAX_REJECT_RATE`
- **L54** `REVIEW_BELOW_CONFIDENCE`
- **L55** `FLOOD_THRESHOLD`
- **L57** `TIERS`
- **L58** `PDF_KINDS`
- **L59** `RECORD_FORMATS`
- **L60** `BUSY`
- **L151** `_COLUMNS`

Functions and classes:
- **L63–68** `class UploadError`  
  A request the desk refuses; the message is for the person uploading.
  - **L66–68** `def __init__`
- **L71–76** `def file_sha256`
- **L79–93** `def kind_of`  
  (kind, format): pdf, records (csv/json/obo/owl/xml; Excel is turned into CSV first), article (prose) or other (not something to load).
- **L96–111** `def excel_to_csv`  
  The first sheet with data, as CSV beside the file.
- **L114–115** `def _slug`
- **L118–138** `def clean_meta`  
  What the uploader said about the file, checked.
- **L141–148** `def source_for`
- **L155–500** `class UploadDesk`
  - **L156–169** `def __init__`
  - **L173–175** `def configured`
  - **L177–187** `def connect`
  - **L189–207** `def _prepare`  
    Creates the tables once per run (safe to repeat), and marks files a restart interrupted.
  - **L209–213** `def _row`
  - **L215–220** `def _set`
  - **L222–224** `def get`
  - **L226–231** `def list`
  - **L235–267** `def receive`  
    Registers a stored file and starts working on it. Refuses a file whose content is already in the knowledge database.
  - **L271–279** `def _start`
  - **L281–284** `def _spawn`
  - **L286–301** `async def _run`
  - **L303–306** `async def wait`  
    Waits for every running job (tests).
  - **L308–315** `def _record_source`
  - **L317–348** `async def _plan`
  - **L350–366** `async def revise`
  - **L368–374** `def approve`
  - **L376–383** `def reject`
  - **L385–392** `def retry`
  - **L394–413** `def set_reports`  
    Whether reports may use this file (its licence allows it). Takes effect at once: the searches re-read the allowed sources.
  - **L415–428** `def remove`  
    Takes the file's rows out of the knowledge database (the source and everything that came from it).
  - **L430–474** `def _load`  
    Reads (PDF) or transforms (data, article) and loads; then links, embeds and refreshes the searches. Runs in a worker thread.
  - **L476–500** `def _after_change`  
    Passages get their search vectors and the offline copy is saved again; the symptom index is told to re-read.
- **L503–514** `def _records`
- **L517–533** `def _review_reasons`
- **L536–567** `def ensure_legacy`  
  Loads Medora's earlier knowledge (source medora-legacy, exported from Supabase) into the knowledge database once, if it is not there yet. True when it is there (or there is nothing to load); False when the database could not be reached, so the caller tries again later.
