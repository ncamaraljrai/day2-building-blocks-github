# Day 2 — Building Blocks

GitHub-ready Day 2 lab package aligned to the course's **What to submit** section.

## Important

The final graded Markdown is **not pre-generated**. Labs 2.2, 2.3 and 2.6 require observed model behavior, so the final file is created only after real local Ollama runs.

## Windows

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\GENERATE-COMPLETE-DAY2.ps1
```

The script executes all required code-lab experiments, records raw evidence, generates the one-document submission, and verifies completeness.

## Submit only

```text
submission\Day2-Building-Blocks-Lab-Submission-FINAL.md
```

## Included written work

- Lab 2.1 — two tool designs + (a)–(d)
- Lab 2.4 — vague/sharpened plan, dependencies, replan, tracker
- Lab 2.5 — single/multi-agent designs, exact handoffs, lossy handoff, decision

## Runtime evidence generated locally

- Lab 2.2 baseline + experiments (a)–(e)
- Lab 2.3 measured token growth + compaction experiments + 20-step projection
- Lab 2.6 three baseline runs + vague rubric + self-review comparison + 6-revision ceiling

## Model

Default: `qwen2.5:7b`

Override:

```powershell
$env:OLLAMA_MODEL="qwen2.5:14b"
.\GENERATE-COMPLETE-DAY2.ps1
```

No paid API key or third-party Python package is required.
