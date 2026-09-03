#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "submission" / "Day2-Building-Blocks-Lab-Submission-FINAL.md"
EVIDENCE = ROOT / "evidence" / "day2-evidence.json"

def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)

if not EVIDENCE.exists():
    fail("evidence/day2-evidence.json is missing")
if not FINAL.exists():
    fail("final submission is missing")

data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
if data.get("meta", {}).get("evidence_kind") != "real_ollama_execution":
    fail("runtime evidence is not real Ollama evidence")

text = FINAL.read_text(encoding="utf-8")

required = [
    "# Lab 2.1",
    "# Lab 2.2",
    "# Lab 2.3",
    "# Lab 2.4",
    "# Lab 2.5",
    "# Lab 2.6",
    "Experiment (a)",
    "Experiment (b)",
    "Experiment (c)",
    "Experiment (d)",
    "Experiment (e)",
    "Growth table",
    "20-step projection",
    "Three-run non-determinism",
    "remove reviewer independence",
]
for phrase in required:
    if phrase not in text:
        fail(f"required section absent: {phrase}")

if "[[LAB" in text:
    fail("unresolved runtime marker remains")

# Lab 2.2 needs real tool-call evidence.
baseline = data["lab22"]["baseline"]
if baseline.get("steps", 0) < 1 or baseline.get("tool_calls", 0) < 1:
    fail("Lab 2.2 baseline lacks real steps/tool calls")

# Lab 2.3 needs measured token table.
table = data["lab23"].get("growth_table", [])
if len(table) != 7 or any(r.get("tokens_this_turn", 0) <= 0 for r in table):
    fail("Lab 2.3 measured growth table is incomplete")

# Lab 2.6 must have 3 baseline and 3 self-review runs.
if len(data["lab26"].get("baseline_runs", [])) != 3:
    fail("Lab 2.6 baseline was not run three times")
if len(data["lab26"].get("self_review_runs", [])) != 3:
    fail("Lab 2.6 self-review experiment was not run three times")

print("PASS: DAY 2 COMPLETENESS READY")
print(FINAL)
