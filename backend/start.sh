#!/bin/bash
# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
source venv/bin/activate 2>/dev/null || true
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
