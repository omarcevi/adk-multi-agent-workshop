"""A fourth MCP tool server: store policy search, backed by RAG Engine.

Same shape as the other three servers: the agent only sees an MCP tool called
search_policy. That RAG Engine sits behind it is an implementation detail the
agent never knows about.
"""

import os

import vertexai
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from vertexai import rag

vertexai.init(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.environ["RAG_REGION"])
CORPUS = os.environ["RAG_CORPUS"]

server = MCPServer(name="policy", instructions="Search ShopDesk's official store policies.")


@server.tool()
def search_policy(question: str) -> dict:
    """Find the store policy passages relevant to a question, e.g. 'refund for a cracked lid'."""
    resp = rag.retrieval_query(
        text=question,
        rag_resources=[rag.RagResource(rag_corpus=CORPUS)],
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=3),
    )
    passages = [
        {"source": c.source_display_name, "text": c.text}
        for c in resp.contexts.contexts
    ]
    return {"question": question, "passages": passages}


if __name__ == "__main__":
    import uvicorn

    app = server.streamable_http_app(
        stateless_http=True, host="0.0.0.0",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), log_level="warning")
