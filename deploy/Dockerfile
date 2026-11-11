# Single-container image for a Hugging Face Docker Space.
# Runs PostgreSQL, the action server, the Rasa server and the FastAPI gateway
# together, because a Space runs one container with one public port (7860).
# deploy/push_space.ps1 copies this file to the root of the Space repository.
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql build-essential \
    && rm -rf /var/lib/apt/lists/*

# Spaces run the container as user 1000
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
RUN chmod +x deploy/start.sh

EXPOSE 7860
CMD ["deploy/start.sh"]
