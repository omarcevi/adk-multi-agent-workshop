"""MODULE 2 — ADK workflow patterns.

    support_pipeline = Sequential[
        intake,                                   # 1. understand the request
        Parallel[order, stock, shipping],         # 2. fan-out research over MCP
        Loop[drafter, policy_reviewer] (max 3),   # 3. write -> critique -> rewrite
    ]

Rule of thumb: use a workflow agent where YOU know the steps (order is
guaranteed, not prompted); use an LLM agent only where judgement is needed.

Agents pass data through *session state*: each step writes with `output_key`,
the next step reads it with a `{key}` placeholder in its instruction. Open the
State tab in adk web after a run to see it.

Look at:
  * build_intake()       structured output -> state["case"]
  * build_research()     ParallelAgent: three researchers, one MCP server each
  * build_review_loop()  LoopAgent: ends when the reviewer calls exit_loop

Note: ADK 2.11 marks these workflow agents deprecated in favour of the
`Workflow` graph API, which can't yet be used as an LlmAgent sub-agent.
They remain the right tool when an orchestrator delegates to the workflow.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.tools import exit_loop
from pydantic import BaseModel, Field

from shopdesk import config
from shopdesk.tools import mcp_toolset

# TRY THIS (Module 2): set MAX_ROUNDS = 1 and compare the reply with the 3-round version.
MAX_ROUNDS = 3


# --- 1. Intake (structured output -> state["case"]) -------------------------------
class Case(BaseModel):
    intent: str = Field(description="one of: where_is_my_order, damaged_item, exchange, refund, other")
    order_id: str | None = Field(default=None, description="ORD-xxxx if the customer gave one")
    customer_id: str | None = Field(default=None, description="C-xx if known")
    summary: str = Field(description="one sentence summary of what the customer wants")


def build_intake() -> LlmAgent:
    return LlmAgent(
        name="intake",
        model=config.FAST_MODEL,
        description="Classifies the customer request and extracts IDs.",
        instruction=(
            "Read the customer's message and fill the Case schema. "
            "Only use IDs that literally appear in the conversation."
        ),
        output_schema=Case,
        output_key="case",
    )


# --- 2. Parallel research (each researcher owns one MCP server) --------------------
def build_research() -> ParallelAgent:
    order_researcher = LlmAgent(
        name="order_researcher",
        model=config.FAST_MODEL,
        description="Facts about the order: status, items, totals, notes.",
        instruction=(
            "Case: {case}\n"
            "Use the orders tools to collect facts about this order or customer. "
            "Reply with a short bullet list of facts only. If there is no order ID, say so."
        ),
        tools=[mcp_toolset("orders")],
        output_key="order_facts",
    )
    stock_researcher = LlmAgent(
        name="stock_researcher",
        model=config.FAST_MODEL,
        description="Stock levels and in-stock alternatives for the ordered items.",
        instruction=(
            "Case: {case}\n"
            "Get the order (to learn its SKUs), then check stock and alternatives for each SKU. "
            "Reply with a short bullet list of facts only."
        ),
        tools=[mcp_toolset("orders", ["get_order"]), mcp_toolset("inventory")],
        output_key="stock_facts",
    )
    shipping_researcher = LlmAgent(
        name="shipping_researcher",
        model=config.FAST_MODEL,
        description="Where the parcel is and when it arrives.",
        instruction=(
            "Case: {case}\n"
            "Get the order (to learn its tracking ID), then track the shipment. "
            "Reply with a short bullet list of facts only."
        ),
        tools=[mcp_toolset("orders", ["get_order"]), mcp_toolset("shipping")],
        output_key="shipping_facts",
    )
    return ParallelAgent(
        name="research",
        description="Runs the three researchers concurrently.",
        sub_agents=[order_researcher, stock_researcher, shipping_researcher],
    )


# --- 3. Loop: draft -> review until the reviewer approves (or 3 rounds) ------------
# TRY THIS (Module 2): add a rule, e.g. "Always address the customer by first name",
# and watch the reviewer send drafts back until they comply.
POLICY = """\
- Never promise a refund or compensation; refunds are decided by the refunds team.
- Never invent dates, prices or tracking numbers that are not in the facts.
- Keep it under 120 words, friendly, and end with one clear next step.
"""


def build_review_loop() -> LoopAgent:
    drafter = LlmAgent(
        name="drafter",
        model=config.MODEL,
        description="Writes the customer reply.",
        instruction=(
            "Write a reply to the customer.\n"
            "Case: {case}\nOrder facts: {order_facts?}\nStock facts: {stock_facts?}\n"
            "Shipping facts: {shipping_facts?}\n"
            "Reviewer feedback from the previous round (may be empty): {review?}\n"
            "Policy:\n" + POLICY + "\nOutput only the reply text."
        ),
        output_key="draft",
    )
    # BONUS (bonus_rag/): with POLICY_MCP_URL set, the reviewer also checks the
    # store's real policy documents through a RAG Engine-backed MCP server.
    policy_tools = [mcp_toolset("policy")] if config.MCP_URLS.get("policy") else []
    reviewer = LlmAgent(
        name="policy_reviewer",
        model=config.MODEL,
        description="Checks the draft against the support policy.",
        instruction=(
            "Check this draft against the policy and the facts.\n"
            "Draft: {draft}\nFacts: {order_facts?} {stock_facts?} {shipping_facts?}\n"
            "Policy:\n" + POLICY + "\n"
            + ("Also look up the relevant store policy with search_policy before deciding.\n"
               if policy_tools else "")
            + "If the draft fully complies, call the exit_loop tool (this ends the loop). "
            "Otherwise reply with a numbered list of concrete fixes."
        ),
        tools=[exit_loop, *policy_tools],
        output_key="review",
    )
    return LoopAgent(
        name="draft_review_loop",
        description=f"Drafts and reviews the reply, at most {MAX_ROUNDS} rounds.",
        sub_agents=[drafter, reviewer],
        max_iterations=MAX_ROUNDS,
    )


def build_support_pipeline() -> SequentialAgent:
    return SequentialAgent(
        name="support_pipeline",
        description=(
            "Handles order questions end to end: where is my order, damaged items, "
            "exchanges and stock questions. Researches the order and writes a "
            "policy-checked reply. Does NOT issue refunds."
        ),
        sub_agents=[build_intake(), build_research(), build_review_loop()],
    )
