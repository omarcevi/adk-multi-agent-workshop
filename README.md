# Architecting Multi-Agent Systems with Google ADK

Workshop repo for **ShopDesk**: a multi-agent customer-support system for a
fictional online store, built with the Agent Development Kit and deployed to
Google Cloud.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/open?cloudshell_git_repo=https://github.com/omarcevi/adk-multi-agent-workshop)

```
                    Customer
                       |
   Agent Runtime       v                                Agent Runtime
  +---------------------------------------+   A2A   +----------------------+
  | Orchestrator (routes by description)  | ------> | Refunds specialist   |
  |   plugins: guardrails, metrics, memory|         |   + guardrail plugin |
  |                                       |         +----------------------+
  | support_pipeline (Sequential)         |                   |
  |   1 Intake                            |                   |
  |   2 Parallel: orders | stock | ship   | --MCP-->  Cloud Run: orders / inventory / shipping
  |   3 Loop: drafter <-> policy reviewer |
  +---------------------------------------+
```

## What you need

- A Google Cloud project with **billing enabled**
- A browser. Everything happens in **Cloud Shell**; nothing is installed on your laptop.

## Start (before the session if you can)

```bash
git clone https://github.com/omarcevi/adk-multi-agent-workshop
cd adk-multi-agent-workshop
gcloud config set project <your-project-id>
make setup          # Python packages, APIs, permissions (~3 min)
make doctor         # checks everything; prints the fix for anything wrong
```

Deploys go to `REGION` in `.env` (default `us-central1`). Change it before deploying, not after.

## The workshop, step by step

| Module | You run | You open in the editor |
| --- | --- | --- |
| 1. MCP tool servers | `make deploy-mcp`, `make check-mcp`, `make web` (pick `m1_mcp_tools`) | `shopdesk/mcp_servers/orders.py`, `shopdesk/tools.py` |
| 2. Workflow patterns | `make deploy-refunds` (background), `make web` (pick `m2_workflows`) | `shopdesk/agents/workflows.py` |
| 3. Orchestrator + A2A | `make status`, `make card`, `make web` (pick `m3_orchestrator`), `make deploy-app` (background) | `shopdesk/agents/discovery.py`, `shopdesk/agents/orchestrator.py` |
| 4. Plugins and memory | `make web` (pick `m4_production`) | `shopdesk/plugins/guardrails.py` |
| 5. The deployed system | `make status`, `make query MSG="Where is ORD-1002?"` | |
| 6. Telemetry | `make bench`, then `make report` | `shopdesk/plugins/telemetry.py` |

`make web` serves the ADK dev UI on port 8080: in Cloud Shell click **Web
Preview → Preview on port 8080**. Look for `# TRY THIS` comments in the code:
small edits with a visible effect. The UI reloads agents when you save.

Slow deploys run in the background and log to `.logs/`; `make status` shows
progress. You never need a second terminal.

### Prompts to try

- `Where is my order ORD-1002 and is the oak chair in stock?`
- `The kettle lid from ORD-1001 arrived cracked. Can I get a new one?`
- `Please refund 20 EUR for the cracked kettle lid on ORD-1001.`
- **Challenge:** get a full 420 EUR refund for the desk on `ORD-1004`.
- `Please always contact me by SMS.` (then start a new session and ask anything)

## Repo map

```
checkpoints/      one folder per module for `adk web` (m1 ... m4)
shopdesk/         the system: mcp_servers/, agents/, plugins/, app.py, tools.py
deploy/           Cloud Run + Agent Runtime deploy, query, cleanup
bench/            test scenarios + telemetry report
bonus_rag/        self-guided: ground the policy reviewer with RAG Engine
scripts/          setup, doctor, status helpers
tests/            offline tests (no GCP needed): `make test`
```

## When you're done

```bash
make cleanup        # deletes the runtimes, Cloud Run services and image repo
```

## Bonus

`bonus_rag/README.md`: put the store's policy documents in a RAG Engine corpus,
serve them through a fourth MCP tool server, and let the policy reviewer check
drafts against them.

## Versions

Tested with `google-adk 2.11.0`, `google-cloud-aiplatform 2.4.0`, `mcp 2.2.0`,
`a2a-sdk 1.2.2`, Gemini `gemini-3.5-flash`. See `requirements.txt`.
