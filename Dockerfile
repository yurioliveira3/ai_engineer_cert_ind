FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install torch CPU-only before the rest to prevent pip from pulling the full
# CUDA/nvidia/triton stack (~3.5 GB) which is never used in this container.
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

ENV HF_HOME=/app/data/hf_cache \
    PYTHONPATH=/app

RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/data && chown -R appuser:appuser /app/data
USER appuser

HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.fileWatcherType=none"]
