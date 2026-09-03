#!/usr/bin/env python3
"""Build the one Day 2 submission document from written work + real evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "day2-evidence.json"
TEMPLATE = ROOT / "templates" / "submission-base.txt"
OUT = ROOT / "submission" / "Day2-Building-Blocks-Lab-Submission-FINAL.md"


def fail(msg):
    raise SystemExit("ERROR: " + msg)


def path(r):
    return " → ".join(r.get("tool_order") or []) or "(none)"


def trace(r):
    lines = []
    for s in r["trace"]:
        calls = s.get("calls") or []
        if s.get("model_text"):
            lines.append(f"- Step {s['step']} commentary: {s['model_text']}")
        if not calls:
            lines.append(f"- Step {s['step']}: no tool call; stop_reason={s['stop_reason']}")
        for c in calls:
            lines.append(
                f"- Step {s['step']}: `{c['name']}({json.dumps(c['args'], ensure_ascii=False)})` "
                f"→ `{json.dumps(c['result'], ensure_ascii=False)}`"
            )
    return "\n".join(lines)


def first_error(r):
    for s in r["trace"]:
        for c in s.get("calls", []):
            if "error" in c.get("result", {}):
                return c["result"]["error"]
    return "(no tool error was observed in this run)"


def first_book_step(r):
    for s in r["trace"]:
        for c in s.get("calls", []):
            if c["name"] == "book_meeting":
                return s["step"]
    return None


def availability_before_book(r):
    book_step = first_book_step(r)
    if book_step is None:
        return None
    checked = set()
    for s in r["trace"]:
        if s["step"] >= book_step:
            break
        for c in s.get("calls", []):
            if c["name"] == "check_availability":
                pid = c.get("args", {}).get("person_id")
                if pid:
                    checked.add(pid)
    return sorted(checked)


def layer_for_experiment(r):
    for s in r["trace"]:
        for c in s.get("calls", []):
            if "error" in c.get("result", {}):
                return c.get("caught_layer") or "validation/program"
    if r.get("booked"):
        return "nothing blocked the wrong-but-valid action"
    return "description/schema/model behavior; no execution-layer rejection observed"


def lab22_md(l22):
    b = l22["baseline"]
    a = l22["a_gut_description"]
    bb = l22["b_remove_date_hint"]
    c = l22["c_force_conflict"]
    d = l22["d_remove_start_validation"]
    e = l22["e_delete_find_person"]

    checks = availability_before_book(b)
    return f"""# Lab 2.2 — Build a tool-using agent and break it deliberately

## Baseline run

- **Steps:** {b['steps']}
- **Total tool calls:** {b['tool_calls']}
- **Tool order:** `{path(b)}`
- **Parallel-call steps:** {b['parallel_steps'] or 'none'}
- **Input tokens:** {b['tokens']['input']}
- **Output tokens:** {b['tokens']['output']}
- **Booked records:** `{json.dumps(b['booked'], ensure_ascii=False)}`

### 1. Call sequence
The observed sequence was `{path(b)}`. Availability was checked for these ids before the first booking call: `{checks}`.

### 2. Parallel calls
Parallel tool requests occurred on step(s): **{b['parallel_steps'] or 'none'}**. Multiple calls under one model turn are independent requests that can be batched rather than requiring another reason step between them.

### 3. Slot reasoning
The model commentary and trace show the point where it moved from availability observations to a proposed booking:

{trace(b)}

The availability tools only returned busy blocks/working hours; the model had to infer the shared free interval before requesting `book_meeting`.

### 4. Steps versus tool calls
The run used **{b['steps']} model-loop steps** but **{b['tool_calls']} tool calls**. They differ because one model turn can request zero, one, or several tools; a step counts a model iteration, while tool calls count requested actions.

## Experiment (a) — gutted `book_meeting` description

- **Observed path:** `{path(a)}`
- **Booked:** `{json.dumps(a['booked'], ensure_ascii=False)}`
- **First error:** `{first_error(a)}`
- **Layer that caught the break:** **{layer_for_experiment(a)}**

{trace(a)}

This run demonstrates empirically whether the description still induced the pre-booking availability checks or whether execution-time validation became the last line of defense.

## Experiment (b) — removed date-format hint; goal says “next Monday”

- **Observed path:** `{path(bb)}`
- **First error:** `{first_error(bb)}`
- **Layer that caught the break:** **{layer_for_experiment(bb)}**

{trace(bb)}

The trace contains the exact date string the model supplied, so the result is measured rather than assumed.

## Experiment (c) — forced 4-hour conflict on 2026-04-07

- **Observed path:** `{path(c)}`
- **First conflict/error string:** `{first_error(c)}`
- **Final response:** {c['final']}
- **Layer:** **{layer_for_experiment(c)}**

{trace(c)}

The informative error gives the model a concrete observation it can use to retry, ask for clarification, or stop.

## Experiment (d) — removed `start_hour` range validation; requested 3am

- **Observed path:** `{path(d)}`
- **BOOKED after run:** `{json.dumps(d['booked'], ensure_ascii=False)}`
- **Layer that caught the break:** **{layer_for_experiment(d)}**

{trace(d)}

A schema description such as “9 to 17” is guidance to a statistical model, not a security boundary. Once the executable range check is removed, wrong-but-valid model output can reach the state-changing code.

## Experiment (e) — removed `find_person` from TOOL_SPECS

- **Observed path:** `{path(e)}`
- **First error:** `{first_error(e)}`
- **Booked:** `{json.dumps(e['booked'], ensure_ascii=False)}`
- **Layer:** **{layer_for_experiment(e)}**

{trace(e)}

This shows what the model actually did when it needed internal ids but the intended resolution capability was absent, including whether it invented ids that happened to pass validation.
"""


def lab23_md(x):
    rows = "\n".join(
        f"| {r['step']} | {r['tokens_this_turn']} | {r['cumulative_processed']} |"
        for r in x["growth_table"]
    )
    base = x["base_compaction"]
    agg = x["aggressive_compaction"]
    strict = x["strict_compaction"]
    lost = x["lost_fact"]
    proj = x["projection_20"]

    return f"""# Lab 2.3 — Context growth and compaction

## Growth table

| Step | Tokens this turn | Cumulative processed |
|---:|---:|---:|
{rows}

- **Final prompt / first prompt:** {x['final_to_first_ratio']}×
- **Cumulative total / final prompt:** {x['cumulative_to_final_ratio']}×
- **Cumulative tokens through step 6:** {x['cumulative_total']}

## 1–2. Growth observations

The prompt grows because every iteration sends the goal plus the accumulated history again. The per-turn context therefore grows with the run, while the cumulative column sums increasingly large prefixes; this is why total processing outpaces the number of steps and trends roughly quadratically for similar-sized additions.

## 3. Specific fact lost or blurred during compaction

Detected comparison result: **{lost['fact']}**  
Status: **{lost['status']}**

### Summary produced with `RECENT_TURNS = 2`

{base['summary']}

Losing or blurring a spend, date, renewal, overage, or migration detail can change which vendor appears most urgent to renegotiate. Even when core facts survive, compaction changes exact wording and can erase caveats that affect confidence.

## 4. What was pinned?

The original **GOAL** was structurally pinned and never placed in the summarizable middle. Naively truncating the oldest messages could remove the objective itself, leaving an agent that still produces plausible work but no longer knows what outcome it is optimizing.

## Experiment (a) — `RECENT_TURNS = 1`

- Before: {agg['before']} tokens
- After: {agg['after']} tokens
- Saved: {agg['saved']} tokens ({agg['saved_pct']}%)

### Aggressive summary

{agg['summary']}

Keeping fewer recent turns verbatim saves more context but forces more exact observations through a lossy model-written summary.

## Experiment (b) — demand monetary figures and dates verbatim

- Before: {strict['before']} tokens
- After: {strict['after']} tokens
- Saved: {strict['saved']} tokens ({strict['saved_pct']}%)

### Revised summary

{strict['summary']}

The changed compaction prompt demonstrates that preservation policy lives in the summarization instruction. A stronger instruction can improve retention of the specific information it names, but it is still not a guarantee of semantic completeness.

## Experiment (c) — 20-step projection

Measured:
- step-0 prompt: **{proj['initial_prompt_tokens']} tokens**
- average growth across the measured six steps: **{proj['average_tokens_added_per_step']} tokens/step**

Projection method:
`prompt(n) ≈ initial + average_delta × n`, then sum prompts for steps `0..20`.

**Estimated cumulative processing for 20 steps: {proj['estimated_cumulative_tokens']} tokens.**

One design change that flattens the curve is to **compact/summarize older history while keeping the goal pinned and only recent turns verbatim**. Selective inclusion can flatten it further when phases are cleanly separable.
"""


def run_summary(r):
    first_verdict = r["rounds"][0]["verdict"] if r["rounds"] else "(no critique)"
    return (
        f"initial={r['initial_words']} words; final={r['final_words']} words; "
        f"calls={r['model_calls']}; accepted={r['accepted']}; "
        f"first verdict={first_verdict.splitlines()[0] if first_verdict else ''}"
    )


def lab26_md(x):
    baseline_lines = "\n".join(
        f"- Run {i+1}: {run_summary(r)}"
        for i, r in enumerate(x["baseline_runs"])
    )
    self_lines = "\n".join(
        f"- Self-review run {i+1}: {run_summary(r)}"
        for i, r in enumerate(x["self_review_runs"])
    )
    sample = x["baseline_runs"][0]
    long = x["max_revisions_6"]

    return f"""# Lab 2.6 — Producer-critic pair

## 1. Did the critic fail the draft?

Three independent baseline executions:

{baseline_lines}

**First-critique FAIL frequency:** {x['baseline_first_critique_fail_count']}/3.

### Baseline run 1 — critic rounds

```text
{json.dumps(sample['rounds'], indent=2, ensure_ascii=False)}
```

The critic's judgment is evidence, not ground truth; I still compare each stated failure with the explicit rubric, especially recommendation clarity, number of reasons, named risk, 100–140-word bound, and invented facts.

## 2. Did revision improve it?

### Draft 0

{sample['initial_draft']}

### Final

{sample['final_draft']}

- Draft 0 words: **{sample['initial_words']}**
- Final words: **{sample['final_words']}**
- Accepted by critic: **{sample['accepted']}**

The relevant comparison is rubric-by-rubric, not simply whether the prose sounds smoother. A revision can improve one criterion while making another worse, especially word count or unsupported specificity.

## 3. Model-call count and extra spend

Baseline run 1 used **{sample['model_calls']} model calls** and **{sample['total_tokens']['total']} total measured tokens** ({sample['total_tokens']['input']} input + {sample['total_tokens']['output']} output).

A single unreviewed draft would use one model call. The extra calls buy an independent pass against a checkable rubric plus targeted revisions; whether that spend is justified depends on whether the observed failures matter.

## 4. Three-run non-determinism

The three baseline runs above produced a first-critique FAIL rate of **{x['baseline_first_critique_fail_count']}/3**. Differences across runs are direct evidence that the critic is non-deterministic and should be evaluated statistically rather than trusted from one example.

## Experiment (a) — vague rubric

Summary: {run_summary(x['vague_rubric'])}

```text
{json.dumps(x['vague_rubric']['rounds'], indent=2, ensure_ascii=False)}
```

A strict-sounding critic cannot compensate for an uncheckable criterion. “Good and professional” provides no measurable target such as word range, minimum reasons, or prohibition on invented facts, so the feedback becomes less reproducible and less actionable.

## Experiment (b) — remove reviewer independence

**Independent baseline first-critique FAIL frequency:** {x['baseline_first_critique_fail_count']}/3  
**Self-review first-critique FAIL frequency:** {x['self_review_first_critique_fail_count']}/3

{self_lines}

This is the measured comparison. Telling the critic that it authored the draft can change how readily it detects defects because it is no longer framed as an independent reviewer with fresh context.

## Experiment (c) — `MAX_REVISIONS = 6`

Summary: {run_summary(long)}

```text
{json.dumps(long['rounds'], indent=2, ensure_ascii=False)}
```

The result shows whether this run converged to PASS or continued generating new objections. Regardless of the observed outcome, the ceiling is required because a producer and critic can otherwise continue handing work back indefinitely.
"""


def main():
    if not EVIDENCE.exists():
        fail("No real evidence. Run tools/run_day2_evidence.py first.")

    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if data.get("meta", {}).get("evidence_kind") != "real_ollama_execution":
        fail("Evidence is not marked as real Ollama execution.")

    for key in ("lab22", "lab23", "lab26"):
        if key not in data:
            fail(f"Missing {key} evidence.")

    base = TEMPLATE.read_text(encoding="utf-8")
    final = (
        base
        .replace("[[LAB22_RUNTIME]]", lab22_md(data["lab22"]))
        .replace("[[LAB23_RUNTIME]]", lab23_md(data["lab23"]))
        .replace("[[LAB26_RUNTIME]]", lab26_md(data["lab26"]))
    )

    if "[[LAB" in final:
        fail("Unresolved runtime marker remains.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(final, encoding="utf-8")
    print("PASS: final one-document Day 2 submission generated.")
    print(OUT)


if __name__ == "__main__":
    main()
