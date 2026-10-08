# ShopDesk — Architecting Multi-Agent Systems with Google ADK
# Everything here runs in Cloud Shell. `make help` lists the targets.

PY := .venv/bin/python
ADK := .venv/bin/adk
export PYTHONPATH := $(CURDIR)
MSG ?= Where is my order ORD-1002?
USER_ID ?= C-42

.PHONY: help setup doctor web deploy-mcp check-mcp deploy-refunds card deploy-app status query bench report cleanup test bonus-rag

help:            ## list the targets
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'

# --- Before the session ---------------------------------------------------------
setup:           ## one-time: project, Python packages, APIs, permissions
	@bash scripts/setup.sh

doctor:          ## check setup and print the fix for anything wrong
	@bash scripts/doctor.sh

# --- Try things locally (one terminal, Cloud Shell Web Preview on port 8080) -------
web:             ## open the ADK dev UI with every checkpoint (Web Preview -> port 8080)
	$(ADK) web checkpoints --host 0.0.0.0 --port 8080 --reload_agents \
	  --allow_origins "regex:https://.*\.cloudshell\.dev"

# --- Module 1 ----------------------------------------------------------------------
deploy-mcp:      ## Module 1: the 3 MCP tool servers -> Cloud Run (~2 min)
	@bash deploy/mcp.sh

check-mcp:       ## Module 1: call each tool server without and with your identity
	@$(PY) deploy/check_mcp.py

# --- Modules 2-3 (slow deploys run in the background) ---------------------------------
deploy-refunds:  ## Module 2: refunds specialist -> Agent Runtime as A2A (background)
	@bash scripts/bg.sh refunds "$(PY) deploy/refunds.py"

card:            ## Module 3: show the refunds specialist's agent card
	@$(PY) deploy/card.py

deploy-app:      ## Module 3: full ShopDesk app -> Agent Runtime (background)
	@bash scripts/bg.sh app "bash deploy/app.sh"

status:          ## what's deployed and what's still building
	@bash scripts/status.sh

# --- Modules 5-6 ---------------------------------------------------------------------
query:           ## Module 5: talk to the deployed app: make query MSG="..."
	@$(PY) deploy/query.py "$(MSG)" --user $(USER_ID)

bench:           ## Module 6: send the test scenarios to the deployed app
	@$(PY) bench/run_bench.py --runs 2

report:          ## Module 6: latency, delegation success, tokens per agent (from Cloud Logging)
	@$(PY) bench/report.py --cloud-logging --hours 3

# --- After ---------------------------------------------------------------------------
cleanup:         ## delete everything the workshop deployed
	@bash deploy/cleanup.sh

bonus-rag:       ## Bonus: ground the policy reviewer with RAG Engine (see bonus_rag/README.md)
	@bash bonus_rag/deploy.sh

test:            ## offline tests, no GCP needed (for the instructor)
	@$(PY) -m pytest -q
