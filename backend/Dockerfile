FROM python:3.12-slim

WORKDIR /app

# Install curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and shared materials
COPY backend /app/backend
COPY data /app/data
COPY tools /app/tools

ENV PYTHONPATH=/app/backend
ENV OPENAI_BASE_URL=https://api.openai.com/v1
ENV LLM_MODEL=gpt-4o
ENV QDRANT_URL=http://qdrant:6333

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
