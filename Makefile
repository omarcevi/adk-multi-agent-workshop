# ShopDesk — Architecting Multi-Agent Systems with Google ADK
#
# The workshop itself uses the real commands (adk web, gcloud run deploy,
# adk deploy, python ui/chat.py); see README.md. These targets are helpers.

PY := .venv/bin/python
export PYTHONPATH := $(CURDIR)
MSG ?= Where is my order ORD-1002?
USER_ID ?= C-42

.PHONY: help setup doctor check-mcp card status query bench report cleanup bonus-rag test

help:            ## list the helpers
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

setup:           ## one-time: project, Python packages, APIs, permissions
	@bash scripts/setup.sh

doctor:          ## check setup and print the fix for anything wrong
	@bash scripts/doctor.sh

check-mcp:       ## find your Cloud Run tool servers, save their URLs, knock with and without identity
	@$(PY) deploy/check_mcp.py

card:            ## show the refunds specialist's agent card
	@$(PY) deploy/card.py

status:          ## what is deployed in your project right now
	@$(PY) scripts/status.py

query:           ## talk to the deployed app: make query MSG="..."
	@$(PY) deploy/query.py "$(MSG)" --user $(USER_ID)

bench:           ## send the test scenarios to the deployed app (once; --runs 2 at home)
	@$(PY) bench/run_bench.py --runs 1

report:          ## latency, delegation success, tokens per agent (from Cloud Logging)
	@$(PY) bench/report.py --cloud-logging --hours 3

cleanup:         ## delete everything the workshop deployed
	@bash deploy/cleanup.sh

bonus-rag:       ## bonus: ground the policy reviewer with RAG Engine (bonus_rag/README.md)
	@bash bonus_rag/deploy.sh

test:            ## offline tests, no GCP needed
	@$(PY) -m pytest -q
