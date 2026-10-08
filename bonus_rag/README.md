# Bonus: ground the policy reviewer with RAG Engine

In the workshop, the policy reviewer checks drafts against a few rules pasted
into its prompt (`POLICY` in `shopdesk/agents/workflows.py`). Real stores have
policy *documents*. This bonus puts them in a RAG Engine corpus and exposes
them through a fourth MCP tool server, `policy`, so the architecture stays the
same: the reviewer just gains one more tool.

```
policy reviewer --MCP--> shopdesk-policy-mcp (Cloud Run) --> RAG Engine corpus
                                                             (bonus_rag/policies/*.md)
```

## Run it

```bash
make bonus-rag    # corpus + policy MCP server on Cloud Run, URL saved into .env
# restart adk web, pick m2_workflows, ask about the cracked kettle lid on ORD-1001
# ship it: the Module 3 `adk deploy agent_engine ...` command plus --agent_engine_id $APP_RUNTIME_ID
```

`make bonus-rag` creates the corpus, deploys the policy server to Cloud Run and
writes `POLICY_MCP_URL` into `.env`. With that set, `build_review_loop()` gives the
reviewer the `search_policy` tool and tells it to look up the policy first.

## Things to notice

- Open the trace: the reviewer now calls `search_policy` before approving.
- Edit a policy file (e.g. change the 30-day return window), run
  `python bonus_rag/create_corpus.py` after clearing `RAG_CORPUS` in `.env`,
  and watch the replies follow the new policy without touching agent code.

## Region and cost

RAG Engine in `us-central1` needs allowlisting for new projects, so the corpus
lives in `RAG_REGION` (default `europe-west4`). RAG Engine's managed vector
database is billed while it exists; check the RAG Engine pricing page and delete
the corpus when you're done (`make cleanup` removes the Cloud Run service; delete
the corpus from the console under Vertex AI > RAG Engine).
