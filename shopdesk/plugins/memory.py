"""Module 4 — long-term memory as a plugin.

After every finished user turn, push the session into the memory service:
* locally: InMemoryMemoryService (keyword search, gone on restart)
* on Agent Runtime: Memory Bank, which extracts and consolidates facts per user

The orchestrator reads it back with the `preload_memory` tool at the start of
each turn. Doing the *write* in a plugin (after_run) instead of an agent
callback means it fires exactly once per turn, whichever agent the turn ended in.
"""

from __future__ import annotations

import logging

from google.adk.plugins.base_plugin import BasePlugin

log = logging.getLogger("shopdesk.memory")


class MemoryPlugin(BasePlugin):
    def __init__(self):
        super().__init__(name="memory_writer")

    async def after_run_callback(self, *, invocation_context) -> None:
        service = invocation_context.memory_service
        if service is None:
            return
        try:
            session = await invocation_context.session_service.get_session(
                app_name=invocation_context.session.app_name,
                user_id=invocation_context.session.user_id,
                session_id=invocation_context.session.id,
            )
            await service.add_session_to_memory(session or invocation_context.session)
        except Exception as e:  # memory must never break a customer reply
            log.warning("memory write failed: %s", e)
