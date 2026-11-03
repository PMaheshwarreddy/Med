"""Reading data files of no known layout: the AI plans, code executes.

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
"""
