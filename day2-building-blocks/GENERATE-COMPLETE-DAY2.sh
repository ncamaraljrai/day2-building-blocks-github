#!/usr/bin/env bash
set -euo pipefail
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
command -v python3 >/dev/null || { echo "Python 3 required"; exit 1; }
command -v ollama >/dev/null || { echo "Ollama required"; exit 1; }
curl -fsS http://localhost:11434/api/tags >/dev/null || {
  echo "Start Ollama first: ollama serve"
  exit 1
}
ollama pull "$MODEL"
python3 tools/run_day2_evidence.py
python3 tools/finalize_submission.py
python3 tools/verify_completeness.py
echo "Submit: submission/Day2-Building-Blocks-Lab-Submission-FINAL.md"
