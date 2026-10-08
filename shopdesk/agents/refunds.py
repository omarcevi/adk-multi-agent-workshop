"""MODULE 3 — the refunds specialist (another team's agent).

Deployed on its own to Agent Runtime and reached only over A2A. The
orchestrator never imports this file; it discovers the agent from its card
(see shopdesk/a2a_service.py for the card).

Its money-moving tool, issue_refund, is guarded by GuardrailPlugin
(shopdesk/plugins/guardrails.py), which runs INSIDE this agent's deployment.
That is what the Module 4 challenge tests: talk the model into anything you
like; the plugin still blocks refunds above AUTO_REFUND_LIMIT.
"""

from __future__ import annotations

import uuid

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from shopdesk import config
from shopdesk.agents import gemini
from shopdesk.mcp_servers._common import load
from shopdesk.tools import mcp_toolset

REFUND_WINDOW_DAYS = 30


def check_refund_eligibility(order_id: str, reason: str) -> dict:
    """Check whether an order can be refunded and the maximum refundable amount.

    Args:
        order_id: Order ID, e.g. ORD-1001.
        reason: Why the customer wants a refund (damaged, late, changed_mind, other).
    """
    order = load("orders").get(order_id.strip().upper())
    if not order:
        return {"eligible": False, "why": "order not found"}
    if order["status"] not in ("delivered", "shipped"):
        return {"eligible": False, "why": f"order is {order['status']}; cancel instead"}
    return {
        "eligible": True,
        "max_amount": order["total"],
        "currency": order["currency"],
        "auto_approve_limit": config.AUTO_REFUND_LIMIT,
        "note": f"Refunds above {config.AUTO_REFUND_LIMIT} need a human approver.",
    }


def issue_refund(order_id: str, amount: float, reason: str, tool_context: ToolContext) -> dict:
    """Issue a refund to the original payment method. Moves money: use only after
    check_refund_eligibility says the order is eligible.

    Args:
        order_id: Order ID, e.g. ORD-1001.
        amount: Amount to refund, in the order currency.
        reason: Short reason recorded on the refund.
    """
    refund_id = f"RF-{uuid.uuid4().hex[:8].upper()}"
    tool_context.state["last_refund_id"] = refund_id
    return {"status": "issued", "refund_id": refund_id, "order_id": order_id, "amount": amount}


def build_refunds_agent() -> LlmAgent:
    return LlmAgent(
        name="refunds_specialist",
        model=gemini(config.MODEL),
        description=(
            "Refunds specialist. Checks refund eligibility for an order and issues "
            "refunds (full or partial) for damaged, late or unwanted items."
        ),
        instruction=(
            "You handle refund requests for ShopDesk.\n"
            "1. Find the order ID in the request; if missing, ask for it.\n"
            "2. Call check_refund_eligibility.\n"
            "3. If eligible, decide a fair amount (partial for a damaged part, full for "
            "a lost parcel) and call issue_refund.\n"
            "4. If a tool result says the refund needs human approval, tell the customer "
            "it has been escalated; do not retry with a smaller amount to dodge the limit.\n"
            "Reply in 2-4 sentences with the outcome and refund ID if any."
        ),
        tools=[check_refund_eligibility, issue_refund, mcp_toolset("orders", ["get_order"])],
    )
