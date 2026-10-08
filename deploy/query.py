"""make query MSG="..." — talk to the deployed ShopDesk app on Agent Runtime.

Prints each event with the agent that produced it, so you can see the routing.
    make query MSG="Where is my order ORD-1002?"
    make query MSG="Please refund 20 EUR for the cracked kettle lid on ORD-1001" USER=C-42
"""

import argparse
import asyncio

from scripts.runtimes import find_app_runtime, stream_query


async def main(message: str, user_id: str, session_id: str | None):
    # Keep `client` referenced: when it's garbage-collected it closes the async session.
    client, app = find_app_runtime()
    if not session_id:
        session = await app.async_create_session(user_id=user_id)
        session_id = session["id"]
    print(f"(user {user_id}, session {session_id})\n")
    try:
        async for event in stream_query(app, user_id=user_id, session_id=session_id, message=message):
            author = event.get("author", "?")
            for part in (event.get("content") or {}).get("parts", []):
                if part.get("text"):
                    print(f"[{author}] {part['text']}")
                elif part.get("function_call"):
                    fc = part["function_call"]
                    print(f"[{author}] -> {fc['name']}({fc.get('args', {})})")
    except TimeoutError as e:
        raise SystemExit(f"\n{e}") from None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--user", default="C-42")
    ap.add_argument("--session")
    a = ap.parse_args()
    asyncio.run(main(a.message, a.user, a.session))
