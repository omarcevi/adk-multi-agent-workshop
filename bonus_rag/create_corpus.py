"""Create a RAG Engine corpus from bonus_rag/policies/ and save its name to .env.

RAG Engine in us-central1 is allowlist-only for new projects, so the corpus
lives in RAG_REGION (default europe-west4, a GA region open to everyone).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import vertexai  # noqa: E402
from vertexai import rag  # noqa: E402

from scripts.envfile import get_value, set_value  # noqa: E402
from shopdesk import config  # noqa: E402

RAG_REGION = os.getenv("RAG_REGION", "europe-west4")

if get_value("RAG_CORPUS"):
    print("Corpus already exists:", get_value("RAG_CORPUS"))
    raise SystemExit(0)

vertexai.init(project=config.PROJECT, location=RAG_REGION)
corpus = rag.create_corpus(display_name="shopdesk-policies",
                           description="ShopDesk store policies for the policy reviewer")
print("Created corpus", corpus.name)
for doc in sorted((ROOT / "bonus_rag" / "policies").glob("*.md")):
    rag.upload_file(corpus_name=corpus.name, path=str(doc), display_name=doc.name)
    print("  uploaded", doc.name)
set_value("RAG_CORPUS", corpus.name)
set_value("RAG_REGION", RAG_REGION)
