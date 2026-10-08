"""Create a RAG Engine corpus from bonus_rag/policies/ and save its name to .env.

RAG Engine in us-central1 is allowlist-only for new projects, so the corpus
lives in RAG_REGION (default europe-west4, a GA region open to everyone).
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import vertexai  # noqa: E402
from vertexai import rag  # noqa: E402

from scripts.envfile import get_value, set_value  # noqa: E402
from shopdesk import config  # noqa: E402

RAG_REGION = os.getenv("RAG_REGION", "europe-west4")

vertexai.init(project=config.PROJECT, location=RAG_REGION)
name = get_value("RAG_CORPUS")
if name:
    print("Using corpus", name)
else:
    name = rag.create_corpus(display_name="shopdesk-policies",
                             description="ShopDesk store policies for the policy reviewer").name
    # Saved right away: the corpus is billed while it exists, so a failed upload below
    # must not orphan it. Re-running uploads only the files that are missing.
    set_value("RAG_CORPUS", name)
    set_value("RAG_REGION", RAG_REGION)
    print("Created corpus", name)
present = {f.display_name for f in rag.list_files(corpus_name=name)}
for doc in sorted((ROOT / "bonus_rag" / "policies").glob("*.md")):
    if doc.name in present:
        continue
    for attempt in range(3):  # a new corpus sometimes fails its first indexing ({'code': 13})
        try:
            rag.upload_file(corpus_name=name, path=str(doc), display_name=doc.name)
            break
        except RuntimeError as e:
            if attempt == 2:
                raise
            print(f"  retrying {doc.name}: {e}")
            time.sleep(10)
    print("  uploaded", doc.name)
