#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m spacy download en_core_web_md || python -m spacy download en_core_web_sm
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
