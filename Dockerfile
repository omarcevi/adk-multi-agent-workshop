# Container for the three MCP tool servers on Cloud Run (`make deploy-mcp`).
# One image, three services: MCP_SERVER picks which server a service runs.
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "mcp==2.2.0" "uvicorn>=0.30" "python-dotenv>=1.0"
COPY shopdesk/__init__.py shopdesk/config.py shopdesk/
COPY shopdesk/data shopdesk/data
COPY shopdesk/mcp_servers shopdesk/mcp_servers
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python -m shopdesk.mcp_servers.${MCP_SERVER} --host 0.0.0.0 --port ${PORT:-8080}"]
