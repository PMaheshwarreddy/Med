"""Medora's earlier knowledge tables, exported from the app database
(Supabase) on 2026-10-30 when knowledge moved to the knowledge database only.
See app/kb/staged.py for the rows they become."""

import json
from pathlib import Path

from ..load import Bundle
from ..sources import Source
from ..staged import bundle_from_legacy


def read(source: Source, paths: list[Path], **_) -> Bundle:
    return bundle_from_legacy(json.loads(paths[0].read_text(encoding="utf-8")))
