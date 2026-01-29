FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model so startup is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY web_app.py .
COPY process_corpus.py .
COPY tag_passages.py .
COPY extract_scripture_references.py .
COPY generate_embeddings.py .
COPY search_corpus.py .
COPY strangely_warm_index/ strangely_warm_index/
COPY scripts/ scripts/
COPY templates/ templates/
COPY static/ static/
COPY metadata/ metadata/

# Copy corpus data
COPY chunked/passages.jsonl chunked/passages.jsonl
COPY cleaned/ cleaned/

# Generate embeddings and centroids at build time
# This takes ~20 min but only runs once per build
RUN python generate_embeddings.py \
    && python -c "from strangely_warm_index.classifier import compute_centroids; compute_centroids()" \
    && echo "Embeddings and centroids ready"

EXPOSE 8000

CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]
