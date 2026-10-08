"""make status — what is actually deployed in your project right now."""

import json
import subprocess

from scripts.envfile import get_value
from shopdesk import config

OK, NO = "\033[32m✓\033[0m", "-"


def cloud_run() -> dict:
    out = subprocess.run(
        ["gcloud", "run", "services", "list", "--region", config.REGION,
         "--filter=metadata.name~^shopdesk-", "--format=json"],
        capture_output=True, text=True,
    )
    try:
        return {s["metadata"]["name"]: s.get("status", {}).get("url", "") for s in json.loads(out.stdout or "[]")}
    except json.JSONDecodeError:
        return {}


def runtimes() -> dict:
    try:
        import agentplatform

        client = agentplatform.Client(project=config.PROJECT, location=config.REGION)
        return {r.api_resource.display_name: r.api_resource.name.split("/")[-1]
                for r in client.runtimes.list()
                if (r.api_resource.display_name or "").startswith("shopdesk")}
    except Exception as e:  # noqa: BLE001
        print(f"  (could not list Agent Runtime: {e})")
        return {}


def main():
    print(f"\n\033[1mShopDesk on {config.PROJECT} ({config.REGION})\033[0m")
    services = cloud_run()
    for name in ["orders", "inventory", "shipping"]:
        svc = f"shopdesk-{name}-mcp"
        print(f"  {OK if svc in services else NO} Cloud Run      {svc}")
    rts = runtimes()
    for display, what in [("shopdesk-refunds", "refunds specialist (A2A)"), ("shopdesk-app", "ShopDesk app")]:
        rid = rts.get(display)
        print(f"  {OK if rid else NO} Agent Runtime  {what}" + (f"  [{rid}]" if rid else ""))
    print(f"  {OK if get_value('A2A_AGENT_CARDS') else NO} A2A card URL in .env" +
          ("" if get_value("A2A_AGENT_CARDS") else "  (make card, once the refunds specialist is up)"))
    print("\nA deploy still running shows up here only when it finishes.")


if __name__ == "__main__":
    main()
