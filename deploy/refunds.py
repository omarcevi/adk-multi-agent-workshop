"""make deploy-refunds — the refunds specialist -> Agent Runtime, as an A2A agent.

Runs in the background (5-10 min: the platform builds a container). When it
finishes it saves REFUNDS_RUNTIME_ID and the agent-card URL to .env.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)  # extra_packages paths are relative to the repo root
sys.path.insert(0, str(ROOT))

from scripts.envfile import get_value, set_value  # noqa: E402
from shopdesk import config  # noqa: E402

REQUIREMENTS = [
    "google-adk[a2a]==2.11.0",
    "google-cloud-aiplatform[agent_engines,adk]==2.4.0",
    "mcp==2.2.0",
    "python-dotenv>=1.0",
]


def main():
    import agentplatform

    from shopdesk.a2a_service import build_a2a_agent

    if not config.MCP_URLS["orders"]:
        sys.exit("Deploy the tool servers first: make deploy-mcp")
    bucket = get_value("STAGING_BUCKET")
    if not bucket:
        sys.exit("No STAGING_BUCKET in .env -> make setup")
    client = agentplatform.Client(project=config.PROJECT, location=config.REGION)
    deploy_config = {
        "staging_bucket": bucket,
        "display_name": "shopdesk-refunds",
        "description": "ShopDesk refunds specialist (A2A)",
        "requirements": REQUIREMENTS,
        "extra_packages": ["shopdesk"],
        "env_vars": {
            "MODEL_LOCATION": "global",
            "WORKSHOP_MODEL": config.MODEL,
            "AUTO_REFUND_LIMIT": str(config.AUTO_REFUND_LIMIT),
            "ORDERS_MCP_URL": config.MCP_URLS["orders"],
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        },
    }
    existing = get_value("REFUNDS_RUNTIME_ID")
    print(f"{'Updating' if existing else 'Creating'} the refunds specialist on Agent Runtime "
          f"in {config.REGION} ...", flush=True)
    if existing:
        name = f"projects/{config.PROJECT}/locations/{config.REGION}/reasoningEngines/{existing}"
        runtime = client.runtimes.update(name=name, agent=build_a2a_agent(), config=deploy_config)
    else:
        runtime = client.runtimes.create(agent=build_a2a_agent(), config=deploy_config)
    name = runtime.api_resource.name
    card = f"https://{config.REGION}-aiplatform.googleapis.com/v1beta1/{name}/a2a/v1/card"
    set_value("REFUNDS_RUNTIME_ID", name.split("/")[-1])
    set_value("A2A_AGENT_CARDS", card)
    print("Deployed:", name)
    print("Agent card:", card, flush=True)
    subprocess.run(["bash", "scripts/grant_runtime_roles.sh"], check=False)


if __name__ == "__main__":
    main()
