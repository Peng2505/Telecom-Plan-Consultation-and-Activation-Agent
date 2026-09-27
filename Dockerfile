FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8012

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN mkdir -p output chromaDB \
    && sed -i 's/\r$//' docker/entrypoint-api.sh docker/entrypoint-web.sh \
    && chmod +x docker/entrypoint-api.sh docker/entrypoint-web.sh

EXPOSE 8012 7860

CMD ["python", "main.py"]
