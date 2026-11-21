# One image that runs the whole system: PostgreSQL, the action server,
# the Rasa server and the FastAPI gateway (see deploy/start.sh).
# deploy/compose.yaml builds it and puts Caddy in front for HTTPS.
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    RASA_TELEMETRY_ENABLED=false
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Download the BERT weights at build time so start-up does not depend on it
RUN python -c "from transformers import BertTokenizer, TFBertModel; \
BertTokenizer.from_pretrained('bert-base-uncased'); TFBertModel.from_pretrained('bert-base-uncased')"

COPY --chown=user . .
RUN chmod +x deploy/start.sh && mkdir -p /home/user/pgdata

EXPOSE 7860
CMD ["deploy/start.sh"]
