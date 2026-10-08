FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "mcp==2.2.0" "uvicorn>=0.30" "google-cloud-aiplatform==2.4.0"
COPY policy_server.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "policy_server.py"]
