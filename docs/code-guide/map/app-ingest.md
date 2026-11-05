# `app/ingest`

## `backend/app/ingest/__init__.py` (16 lines)

Reading data files of no known layout: the AI plans, code executes.

  sniff      what format is this file really, and what does a sample look like
  planner    AI reads the sample and returns a declarative Plan (or a verdict
             that the file is junk / not data)
  articles   AI extraction for free-text articles, checked against the text
  records    streams records out of CSV, JSON, OBO/OWL and XML files of any size
  transform  applies the Plan to every record: clean, validate, de-duplicate

The AI never touches rows of structured files: it sees a sample and decides
the mapping, which is then applied deterministically. Nothing here writes to a
database: a back-office upload (app/kb/uploads.py) turns the staged result
into rows of the knowledge database (app/kb/staged.py). The old tables in the
app database (Supabase) are no longer used.

(no functions)

## `backend/app/ingest/articles.py` (120 lines)

AI extraction for free-text articles about a single disease.

Unlike structured files there are no columns to map, so the model reads the
article and returns the facts. To keep invented facts out of the database,
every extracted name must be found in the article itself.

Uses (inside the app): `llm`, `plan`, `transform`

Settings and constants:
- **L12** `MAX_ARTICLE_CHARS`
- **L14** `EXTRACT_SYSTEM`
- **L44** `ARTICLE_PLAN`

Functions and classes:
- **L68–76** `def _grounded`  
  True when the phrase, or all of its meaningful words, occur in the text.
- **L79–82** `def _strings`
- **L85–119** `async def extract_article`  
  The article as one record for ARTICLE_PLAN, plus the names that were dropped because the article does not contain them.

## `backend/app/ingest/plan.py` (130 lines)

The Plan: what the AI decides about a file, in a form code can execute.

Uses (inside the app): `sniff`

Settings and constants:
- **L11** `ENTITY_FIELDS`

Functions and classes:
- **L18–23** `class Col`  
  Where a value comes from. `sources` are column names or JSON paths; the first one with a value wins. `split` breaks a multi-valued cell.
- **L26–44** `class EntityOutput`
  - **L36–44** `def _known_fields`
- **L47–59** `class LinkOutput`  
  Disease -> symptom or disease -> drug. Missing names are created.
  - **L55–59** `def _one_target`
- **L62–72** `class PrecautionOutput`
  - **L68–72** `def _has_subject`
- **L80–129** `class Plan`
  - **L94–100** `def _consistent`
  - **L102–110** `def cols`
  - **L112–129** `def check_against`  
    Problems that make the plan unexecutable on this file.

## `backend/app/ingest/planner.py` (184 lines)

Asks the model what a file is and how it maps onto the knowledge tables.

Uses (inside the app): `llm`, `plan`, `settings`, `sniff`

Settings and constants:
- **L17** `PLANNER_SYSTEM`

Functions and classes:
- **L98–134** `class RetryingLlm`  
  Rides out rate limits and brief outages; spaces calls for a free tier.
  - **L101–107** `def __init__`
  - **L109–134** `async def json`
- **L137–142** `def make_ingest_llm`  
  Planning needs the stronger model. It never falls back silently to the small offline one, because a weak plan would load wrong data.
- **L145–183** `async def make_plan`  
  The model's plan, validated. An unexecutable plan is sent back with the reason; if it is still wrong after that, the error is raised.

## `backend/app/ingest/records.py` (273 lines)

Streams records out of source files without loading them into memory.

Settings and constants:
- **L15** `OBO_KEYS`
- **L136** `_OWL_NS`

Functions and classes:
- **L18–29** `def _repair_row`  
  Fixes the two ways rows go wrong in hand-assembled CSVs.
- **L32–45** `def iter_csv`
- **L48–58** `def json_prefix`  
  `results` -> `results.item`; `graphs[].nodes` -> `graphs.item.nodes.item`.
- **L61–65** `def iter_json`
- **L68–97** `def find_json_records`  
  Path of the array holding the file's records, in Plan notation.
- **L100–133** `def iter_obo`  
  Terms of an OBO ontology, skipping obsolete ones. `synonyms` holds the exact synonyms only.
- **L145–167** `def iter_owl`  
  Classes of an OBO-style OWL ontology (RDF/XML), read like an OBO file: id, name, definition and EXACT synonyms; deprecated ones skipped.
- **L170–194** `def xml_record_tag`  
  The element that repeats directly under the root: one record each.
- **L197–215** `def _xml_value`  
  An element as JSON-like data: attributes as "@name", children by tag (a list when the tag repeats), text alone when there is nothing else.
- **L218–234** `def iter_xml`  
  Each `record_tag` element under the root, as JSON-like data, streamed so files of hundreds of megabytes stay out of memory.
- **L237–272** `def get_values`  
  Every string found at `path`, e.g. `openfda.generic_name[0]` or `meta.synonyms[].val`. A plain CSV column name is a path of one step.

## `backend/app/ingest/sniff.py` (210 lines)

Works out what a file really is from its content, never from its name.

Uses (inside the app): 

Settings and constants:
- **L12** `SAMPLE_ROWS`
- **L13** `PROFILE_ROWS`
- **L14** `_CODE`

Functions and classes:
- **L17–56** `class Sniffed`
  - **L32–56** `def describe`  
    The description handed to the planning model.
- **L59–69** `def _shorten`  
  Trims a sample record so long documents do not flood the prompt.
- **L72–87** `def _profile`
- **L90–104** `def _json_paths`  
  Paths to every scalar or list-of-scalars in a record, in Plan notation.
- **L107–190** `def sniff`
- **L193–209** `def _delimiter`  
  A delimiter that splits the header and most rows into the same width.

## `backend/app/ingest/transform.py` (360 lines)

Applies a Plan to records: clean, validate, de-duplicate, stage.

Nothing here touches the database. The result is a `Staged` object that says
exactly what a load would write and what was refused, so the same code serves
previews and real loads.

Uses (inside the app): `plan`, `records`

Settings and constants:
- **L19** `NAME_LIMITS`
- **L20** `TEXT_LIMIT`
- **L21** `PRECAUTION_LIMITS`
- **L22** `MAX_ALIASES`
- **L27** `MAX_SYMPTOMS_PER_DISEASE`
- **L28** `REJECT_SAMPLES_PER_REASON`
- **L30** `_PLACEHOLDERS`
- **L37** `_DRUG_CLASS`
- **L48** `_CP1252`
- **L49** `_APOSTROPHES`

Functions and classes:
- **L52–64** `def normalize`  
  The matching key: case, accents, punctuation and spacing do not count.
- **L67–73** `def fuzzy_key`  
  A looser key for a second matching pass: spacing and a plural "s" do not count, so "Chicken pox" = "Chickenpox" and "Headaches" = "Headache".
- **L76–81** `def _is_variant_of`  
  True when one name is the other plus extra words: a subtype, a broader term or a product variant ("Retinal migraine" for "Migraine"), which is not another name for the same thing.
- **L84–95** `def clean_name`
- **L98–112** `def clean_text`
- **L115–129** `def check_name`  
  Why `name` cannot be a row in `table`, or None when it can.
- **L132–141** `class EntityDraft`
  - **L140–141** `def text`
- **L144–278** `class Staged`
  - **L159–162** `def reject`
  - **L164–170** `def reject_rate`  
    Share of names and precautions refused. Dropped aliases are reported but do not count: losing an alias loses no row.
  - **L172–183** `def summary`
  - **L187–209** `def entity`  
    Stages a name and returns its key, or None when it is refused.
  - **L211–221** `def alias`
  - **L223–232** `def add_text`
  - **L234–255** `def drop_implausible_diseases`  
    Removes "diseases" with an impossible number of symptoms, and the symptoms that only they referred to (see MAX_SYMPTOMS_PER_DISEASE).
  - **L257–269** `def drop_ambiguous_aliases`  
    An alias must identify one row. A name that several rows claim ("Pain relief" as a brand of many drugs), or that is itself the name of another row, identifies none and is removed everywhere.
  - **L271–278** `def precaution`
- **L281–292** `def _values`
- **L295–297** `def _first`
- **L300–315** `def apply_plan`
- **L318–329** `def _entity`
- **L332–344** `def _link`
- **L347–359** `def _precaution`
