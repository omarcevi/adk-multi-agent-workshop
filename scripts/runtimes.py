"""Find the deployed ShopDesk app on Agent Runtime.

After a raw `adk deploy agent_engine --display_name shopdesk-app ...`, nobody has
to copy the runtime ID: we look it up by display name once and remember it in .env.
"""

from __future__ import annotations

from scripts.envfile import get_value, set_value
from shopdesk import config

APP_DISPLAY_NAME = "shopdesk-app"


def resource_name(runtime_id: str) -> str:
    return f"projects/{config.PROJECT}/locations/{config.REGION}/reasoningEngines/{runtime_id}"


def find_app_runtime():
    """Return (client, runtime). Keep `client` referenced for as long as you use
    `runtime`: when the client is garbage-collected it closes the async session."""
    import agentplatform

    client = agentplatform.Client(project=config.PROJECT, location=config.REGION)
    rid = get_value("APP_RUNTIME_ID")
    if not rid:
        matches = [r for r in client.runtimes.list()
                   if (r.api_resource.display_name or "") == APP_DISPLAY_NAME]
        if not matches:
            raise SystemExit(
                f"No '{APP_DISPLAY_NAME}' on Agent Runtime in {config.REGION} yet.\n"
                "Deploy it first (Module 3: adk deploy agent_engine ... --display_name shopdesk-app)."
            )
        latest = max(matches, key=lambda r: str(getattr(r.api_resource, "update_time", "") or ""))
        rid = latest.api_resource.name.split("/")[-1]
        set_value("APP_RUNTIME_ID", rid)
    return client, client.runtimes.get(name=resource_name(rid))
