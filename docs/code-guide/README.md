# Medora code guide

A guide for studying the whole backend and how the frontend talks to it.
Written 2026-11-05 against the code as it was that day. Line numbers like
`triage.py L582` point at that version; after code changes, regenerate the
map (see the end of this page) and the chapters may drift by a few lines.

## Reading order

| # | Chapter | What you learn |
| --- | --- | --- |
| 1 | [The big picture](01-big-picture.md) | The parts, the folders, the two databases, how a request travels |
| 2 | [Startup: main.py](02-startup.md) | What happens when the server starts, line by line |
| 3 | [A typed visit, screen by screen](03-a-typed-visit.md) | Each kiosk screen, the server call it makes, the code that answers |
| 4 | [The report pipeline](04-report-pipeline.md) | `build_report` step by step: understanding, evidence, panel, writer, review, rules |
| 5 | [Voice](05-voice.md) | The live conversation with Dr. Medora and its tool calls |
| 6 | [Offline mode](06-offline.md) | What changes without internet, and how visits are copied back |
| 7 | [Portals and security](07-portals-and-security.md) | Back office, hospital portal, doctor portal, keys and sign-ins |
| 8 | [Medical knowledge](08-knowledge.md) | The knowledge database, uploads, the two searches (RAG) |
| 9 | [data/, eval/, tests/](09-data-eval-tests.md) | What the folders hold and how the code is checked |

## The map (every function, with line numbers)

[`map/`](map/README.md) lists every backend file, every function and class
with its exact start and end line, its one-line description, and for each API
route which frontend files call it. Use it like an index: the chapters explain
the story, the map tells you where each piece is.

It is generated from the code, so it is always accurate when regenerated:

```bash
python3 docs/code-guide/gen_map.py .     # run from the Medora folder
```

## How to study

1. Read chapters 1 and 2 with `backend/app/main.py` open beside them.
2. Do a typed visit on the kiosk while reading chapter 3, and open each
   file it names at the line it names.
3. Read chapter 4 with `backend/app/triage.py` open: it is the heart of
   Medora.
4. The rest in any order. When a chapter says "see the map", open the map
   file for that folder.
