"""make query MSG="..." — talk to the deployed ShopDesk app on Agent Runtime.

Prints each event with the agent that produced it, so you can see the routing.
    make query MSG="Where is my order ORD-1002?"
    make query MSG="Please refund 20 EUR for the cracked kettle lid on ORD-1001" USER=C-42
"""

import argparse
import asyncio

from shopdesk import config
from scripts.envfile import get_value


async def main(message: str, user_id: str, session_id: str | None):
    import agentplatform

    rid = get_value("APP_RUNTIME_ID")
    if not rid:
        raise SystemExit("App not deployed yet -> make status")
    name = f"projects/{config.PROJECT}/locations/{config.REGION}/reasoningEngines/{rid}"
    # Keep the client referenced: when it's garbage-collected it closes the async session.
    client = agentplatform.Client(project=config.PROJECT, location=config.REGION)
    app = client.runtimes.get(name=name)
    if not session_id:
        session = await app.async_create_session(user_id=user_id)
        session_id = session["id"]
    print(f"(user {user_id}, session {session_id})\n")
    async for event in app.async_stream_query(user_id=user_id, session_id=session_id, message=message):
        author = event.get("author", "?")
        for part in (event.get("content") or {}).get("parts", []):
            if part.get("text"):
                print(f"[{author}] {part['text']}")
            elif part.get("function_call"):
                fc = part["function_call"]
                print(f"[{author}] -> {fc['name']}({fc.get('args', {})})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--user", default="C-42")
    ap.add_argument("--session")
    a = ap.parse_args()
    asyncio.run(main(a.message, a.user, a.session))
