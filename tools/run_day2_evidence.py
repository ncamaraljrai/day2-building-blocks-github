#!/usr/bin/env python3
"""
Run the Day 2 code labs and required experiments with a REAL local Ollama model.

Produces:
    evidence/day2-evidence.json
    evidence/day2-evidence.md
    evidence/raw/*.txt
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ollama_shim import OllamaAnthropic

MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

EVIDENCE_DIR = ROOT / "evidence"
RAW_DIR = EVIDENCE_DIR / "raw"
EVIDENCE_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)


def client(temp=0.0):
    return OllamaAnthropic(model=MODEL, host=HOST, temperature=temp)


def probe():
    r = client().messages.create(
        max_tokens=20,
        messages=[{"role": "user", "content": "Reply exactly: day2 OK"}],
    )
    if not r.content:
        raise RuntimeError("Ollama returned no content")
    return True


# =====================================================================
# LAB 2.2
# =====================================================================

BASE_PEOPLE = {
    "ana": {"name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"},
    "ben": {"name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"},
    "cai": {"name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"},
}

BASE_BUSY = {
    "ana": [("2026-04-06", 9, 11), ("2026-04-07", 14, 16)],
    "ben": [("2026-04-06", 13, 15)],
    "cai": [("2026-04-06", 9, 10), ("2026-04-07", 9, 12)],
}


def make_state():
    return copy.deepcopy(BASE_PEOPLE), copy.deepcopy(BASE_BUSY), []


def tool_specs():
    return [
        {
            "name": "find_person",
            "description": (
                "Resolve a person's name or nickname to their internal id, timezone "
                "and role. Call this first whenever the user refers to a person by "
                "name, before any other tool that needs a person_id. It matches on "
                "id or on full name; it cannot search by role or team."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A person's id, first name, or full name.",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "check_availability",
            "description": (
                "Return the busy time blocks for one person on one specific day, "
                "plus their working hours. Use this to find a free slot before "
                "booking. It covers one person and one day per call — call it "
                "repeatedly for several people. It does not suggest slots; you "
                "must compare the results yourself."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "person_id": {
                        "type": "string",
                        "description": "Internal id from find_person, e.g. 'ana'.",
                    },
                    "date": {
                        "type": "string",
                        "description": "The day to check, ISO format YYYY-MM-DD.",
                    },
                },
                "required": ["person_id", "date"],
            },
        },
        {
            "name": "book_meeting",
            "description": (
                "Create a meeting on the shared calendar. This writes real data and "
                "notifies attendees, so only call it once you have confirmed every "
                "attendee is free using check_availability. Meetings must fall "
                "inside 09:00-18:00 and last 1 to 4 hours. It rejects any slot that "
                "conflicts with an existing commitment."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "person_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Attendee ids from find_person.",
                    },
                    "date": {"type": "string", "description": "ISO date YYYY-MM-DD."},
                    "start_hour": {
                        "type": "integer",
                        "description": "Start hour in 24h local time, 9 to 17.",
                    },
                    "duration_hours": {
                        "type": "integer",
                        "description": "Length in whole hours, 1 to 4.",
                    },
                    "title": {"type": "string", "description": "Short meeting title."},
                },
                "required": ["person_ids", "date", "start_hour", "duration_hours", "title"],
            },
        },
    ]


def run_tools_agent(goal, *, specs=None, validate_start=True, temp=0.0, max_steps=10):
    PEOPLE, BUSY, BOOKED = make_state()
    specs = copy.deepcopy(specs if specs is not None else tool_specs())

    def find_person(query: str):
        key = query.strip().lower()
        if key in PEOPLE:
            return {"id": key, **PEOPLE[key]}
        matches = [k for k, v in PEOPLE.items() if key in v["name"].lower()]
        if len(matches) == 1:
            return {"id": matches[0], **PEOPLE[matches[0]]}
        if len(matches) > 1:
            return {"error": f"'{query}' matches several people: {matches}. Be more specific."}
        return {
            "error": f"No person matching '{query}'. "
                     f"Known ids: {sorted(PEOPLE)}. Use one of those ids."
        }

    def check_availability(person_id: str, date: str):
        if person_id not in PEOPLE:
            return {"error": f"Unknown person_id '{person_id}'. Call find_person first. "
                             f"Valid ids: {sorted(PEOPLE)}."}
        try:
            datetime.date.fromisoformat(date)
        except (ValueError, TypeError):
            return {"error": f"date must be ISO format YYYY-MM-DD, got '{date}'."}
        blocks = [
            {"start_hour": s, "end_hour": e}
            for (d, s, e) in BUSY.get(person_id, []) if d == date
        ]
        return {
            "person_id": person_id,
            "date": date,
            "busy_blocks": blocks,
            "working_hours": {"start_hour": 9, "end_hour": 18},
        }

    def book_meeting(person_ids: list, date: str, start_hour: int,
                     duration_hours: int, title: str):
        if not isinstance(person_ids, list) or not person_ids:
            return {"error": "person_ids must be a non-empty list of person ids."}
        unknown = [p for p in person_ids if p not in PEOPLE]
        if unknown:
            return {"error": f"Unknown person_ids: {unknown}. Valid ids: {sorted(PEOPLE)}."}
        try:
            datetime.date.fromisoformat(date)
        except (ValueError, TypeError):
            return {"error": f"date must be ISO format YYYY-MM-DD, got '{date}'."}
        if validate_start and not (isinstance(start_hour, int) and 9 <= start_hour <= 17):
            return {"error": f"start_hour must be an integer between 9 and 17, got {start_hour}."}
        if not isinstance(start_hour, int):
            return {"error": f"start_hour must be an integer, got {start_hour!r}."}
        if not (isinstance(duration_hours, int) and 1 <= duration_hours <= 4):
            return {"error": f"duration_hours must be an integer between 1 and 4, got {duration_hours}."}
        if not isinstance(title, str) or not title.strip():
            return {"error": "title must be a non-empty string describing the meeting."}
        end_hour = start_hour + duration_hours
        if end_hour > 18:
            return {"error": f"Meeting would end at {end_hour}:00, past the 18:00 working "
                             f"limit. Choose an earlier start_hour or shorter duration."}
        conflicts = []
        for person in person_ids:
            for (d, s, e) in BUSY.get(person, []):
                if d == date and start_hour < e and end_hour > s:
                    conflicts.append({"person_id": person, "busy": f"{s}:00-{e}:00"})
        if conflicts:
            return {"error": f"Conflicts found: {conflicts}. Pick a different slot."}
        meeting = {
            "id": f"mtg-{len(BOOKED) + 1}",
            "title": title,
            "attendees": person_ids,
            "date": date,
            "start_hour": start_hour,
            "end_hour": end_hour,
        }
        BOOKED.append(meeting)
        for person in person_ids:
            BUSY.setdefault(person, []).append((date, start_hour, end_hour))
        return {"booked": meeting}

    functions = {
        "find_person": find_person,
        "check_availability": check_availability,
        "book_meeting": book_meeting,
    }

    messages = [{"role": "user", "content": goal}]
    trace, input_tokens, output_tokens = [], 0, 0
    final = ""
    stopped_by = None

    for step in range(1, max_steps + 1):
        response = client(temp).messages.create(
            max_tokens=2048,
            tools=specs,
            messages=messages,
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        model_text = "\n".join(
            b.text.strip() for b in response.content
            if getattr(b, "type", None) == "text" and b.text.strip()
        )

        row = {
            "step": step,
            "model_text": model_text,
            "stop_reason": response.stop_reason,
            "calls": [],
        }

        if response.stop_reason != "tool_use":
            final = "\n".join(
                b.text for b in response.content if getattr(b, "type", None) == "text"
            ).strip()
            trace.append(row)
            stopped_by = "model_final"
            break

        messages.append({"role": "assistant", "content": response.content})
        results = []

        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            fn = functions.get(block.name)
            if fn is None:
                result = {"error": f"Unknown tool {block.name}"}
                caught_layer = "program/tool-dispatch"
            else:
                try:
                    result = fn(**block.input)
                    caught_layer = "validation" if "error" in result else None
                except TypeError as exc:
                    result = {"error": f"Bad arguments for {block.name}: {exc}"}
                    caught_layer = "validation/program"
                except Exception as exc:
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                    caught_layer = "program"

            row["calls"].append({
                "name": block.name,
                "args": block.input,
                "result": result,
                "caught_layer": caught_layer,
            })
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
                "is_error": "error" in result,
            })

        trace.append(row)
        messages.append({"role": "user", "content": results})
    else:
        final = "Stopped: step limit reached"
        stopped_by = "max_steps"

    return {
        "goal": goal,
        "steps": len(trace),
        "tool_calls": sum(len(s["calls"]) for s in trace),
        "tool_order": [c["name"] for s in trace for c in s["calls"]],
        "parallel_steps": [
            s["step"] for s in trace if len(s["calls"]) > 1
        ],
        "trace": trace,
        "final": final,
        "booked": BOOKED,
        "stopped_by": stopped_by,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        },
    }


def lab22():
    baseline_goal = (
        "Book a 2-hour design review with Ana, Ben and Cai on 2026-04-06. "
        "Find a slot that works for all three."
    )
    baseline = run_tools_agent(baseline_goal, temp=0.3)

    specs_a = tool_specs()
    for s in specs_a:
        if s["name"] == "book_meeting":
            s["description"] = "Books a meeting."
    gut_description = run_tools_agent(baseline_goal, specs=specs_a)

    specs_b = tool_specs()
    for s in specs_b:
        if s["name"] == "check_availability":
            s["input_schema"]["properties"]["date"]["description"] = "The date."
    no_date_hint = run_tools_agent(
        "Book a 2-hour design review with Ana, Ben and Cai next Monday. "
        "Find a slot that works for all three.",
        specs=specs_b,
    )

    conflict = run_tools_agent(
        "Book a 4-hour design review with Ana, Ben and Cai on 2026-04-07. "
        "Find a slot that works for all three."
    )

    no_start_validation = run_tools_agent(
        "Book a 2-hour design review with Ana, Ben and Cai on 2026-04-06 "
        "at 3am so nobody is interrupted.",
        validate_start=False,
    )

    specs_e = [s for s in tool_specs() if s["name"] != "find_person"]
    no_find_person = run_tools_agent(baseline_goal, specs=specs_e)

    return {
        "baseline": baseline,
        "a_gut_description": gut_description,
        "b_remove_date_hint": no_date_hint,
        "c_force_conflict": conflict,
        "d_remove_start_validation": no_start_validation,
        "e_delete_find_person": no_find_person,
    }


# =====================================================================
# LAB 2.3
# =====================================================================

GOAL = (
    "Audit our three cloud vendors and recommend which contract to renegotiate "
    "first. Consider spend, growth trend, and contract end date."
)

SIMULATED_RUN = [
    ("I'll start by pulling total spend per vendor.",
     {"vendor_spend": [{"vendor": "Northwind Cloud", "usd": 412000},
                       {"vendor": "Acme Compute", "usd": 288500},
                       {"vendor": "Zephyr Hosting", "usd": 96200}],
      "period": "2025-04-01..2026-03-31", "currency": "USD",
      "note": "Excludes support contracts billed separately."}),
    ("Now the month-by-month trend for the largest vendor.",
     {"vendor": "Northwind Cloud",
      "monthly_usd": [31200, 32100, 30800, 33400, 35900, 34100,
                      36800, 38200, 37500, 39900, 41100, 42000],
      "trend": "+34.6% over 12 months", "driver": "object storage egress"}),
    ("Checking the same trend for the second vendor.",
     {"vendor": "Acme Compute",
      "monthly_usd": [25100, 24800, 24200, 24500, 23900, 24100,
                      23800, 24000, 23600, 23900, 23400, 23200],
      "trend": "-7.6% over 12 months", "driver": "workload migration off VMs"}),
    ("Pulling contract end dates and notice periods.",
     {"contracts": [
         {"vendor": "Northwind Cloud", "ends": "2026-09-30", "notice_days": 90,
          "auto_renew": True, "discount_tier": "committed-use 15%"},
         {"vendor": "Acme Compute", "ends": "2027-02-28", "notice_days": 30,
          "auto_renew": False, "discount_tier": "none"},
         {"vendor": "Zephyr Hosting", "ends": "2026-05-15", "notice_days": 60,
          "auto_renew": True, "discount_tier": "startup credit"}]}),
    ("Looking for committed-use shortfalls or overage penalties.",
     {"commitments": [
         {"vendor": "Northwind Cloud", "committed_usd": 360000,
          "actual_usd": 412000, "overage_usd": 52000,
          "overage_rate": "list price, no discount"},
         {"vendor": "Acme Compute", "committed_usd": 0, "actual_usd": 288500}],
      "note": "Northwind overage is billed at undiscounted list price."}),
    ("Checking whether any team has migration plans that change the picture.",
     {"planned_migrations": [
         {"from": "Acme Compute", "to": "Northwind Cloud", "team": "data-platform",
          "estimated_monthly_usd": 8400, "starts": "2026-06-01"}],
      "note": "Would increase Northwind spend further before renewal."}),
]


def build_history(entries):
    messages = [{"role": "user", "content": GOAL}]
    for commentary, output in entries:
        messages.append({"role": "assistant", "content": commentary})
        messages.append({"role": "user", "content": json.dumps(output)})
    return messages


def count_tokens(messages):
    return client().messages.count_tokens(messages=messages).input_tokens


def summarize_middle(middle, instruction):
    r = client().messages.create(
        max_tokens=1400,
        system=instruction,
        messages=[{
            "role": "user",
            "content": "Compress this agent history:\n\n" + json.dumps(middle, indent=1),
        }],
    )
    return "".join(
        b.text for b in r.content if getattr(b, "type", None) == "text"
    ).strip(), {
        "input": r.usage.input_tokens,
        "output": r.usage.output_tokens,
        "total": r.usage.input_tokens + r.usage.output_tokens,
    }


def compaction(recent_turns, instruction):
    full = build_history(SIMULATED_RUN)
    pinned = full[0]
    middle = full[1:-(recent_turns * 2)] if recent_turns else full[1:]
    recent = full[-(recent_turns * 2):] if recent_turns else []
    summary, summary_tokens = summarize_middle(middle, instruction)
    compacted = [pinned, {"role": "assistant", "content": "[EARLIER WORK]\n" + summary}] + recent
    before = count_tokens(full)
    after = count_tokens(compacted)
    return {
        "recent_turns": recent_turns,
        "middle_messages": len(middle),
        "recent_messages": len(recent),
        "summary": summary,
        "before": before,
        "after": after,
        "saved": before - after,
        "saved_pct": round((1 - after / before) * 100, 1) if before else 0,
        "summary_call_tokens": summary_tokens,
    }


def detect_lost_fact(summary):
    # Prefer exact monetary/date facts, then important caveats.
    candidates = [
        ("Northwind annual spend = 412000 USD", ["412000", "412,000"]),
        ("Acme annual spend = 288500 USD", ["288500", "288,500"]),
        ("Zephyr annual spend = 96200 USD", ["96200", "96,200"]),
        ("Northwind growth = +34.6%", ["34.6"]),
        ("Northwind contract end = 2026-09-30", ["2026-09-30"]),
        ("Zephyr contract end = 2026-05-15", ["2026-05-15"]),
        ("Northwind overage = 52000 USD", ["52000", "52,000"]),
        ("planned migration = 8400 USD/month", ["8400", "8,400"]),
        ("planned migration start = 2026-06-01", ["2026-06-01"]),
        ("support contracts are excluded", ["support contract"]),
        ("Northwind overage is at undiscounted list price", ["undiscounted", "list price"]),
        ("Zephyr discount tier = startup credit", ["startup credit"]),
    ]
    low = summary.lower()
    for label, variants in candidates:
        if not any(v.lower() in low for v in variants):
            return {"fact": label, "status": "lost_or_blurred"}
    return {
        "fact": "No monitored core fact was missing verbatim; compaction still changed wording/detail.",
        "status": "no_monitored_fact_missing",
    }


def lab23():
    table = []
    cumulative = 0
    per_step = []
    for n in range(len(SIMULATED_RUN) + 1):
        tokens = count_tokens(build_history(SIMULATED_RUN[:n]))
        cumulative += tokens
        per_step.append(tokens)
        table.append({
            "step": n,
            "tokens_this_turn": tokens,
            "cumulative_processed": cumulative,
        })

    default_instruction = (
        "You compress an AI agent's working history. Preserve every concrete "
        "figure, date, name, and finding that could matter later. Drop "
        "narration and restatements. Output a dense bulleted recap, nothing else."
    )

    base_compaction = compaction(2, default_instruction)
    lost = detect_lost_fact(base_compaction["summary"])

    aggressive = compaction(1, default_instruction)

    strict_instruction = (
        "You compress an AI agent's working history. Preserve ALL monetary "
        "figures and ALL dates VERBATIM, including currency/units where present. "
        "Also preserve names, trends, contract terms, caveats, and migration "
        "plans that could affect a recommendation. Drop only narration and "
        "restatements. Output a dense bulleted recap, nothing else."
    )
    strict = compaction(2, strict_instruction)

    initial = per_step[0]
    last = per_step[-1]
    avg_delta = (last - initial) / len(SIMULATED_RUN)
    projected_20 = round(sum(initial + avg_delta * n for n in range(21)))

    return {
        "growth_table": table,
        "first_tokens": initial,
        "final_tokens": last,
        "final_to_first_ratio": round(last / initial, 2) if initial else None,
        "cumulative_total": cumulative,
        "cumulative_to_final_ratio": round(cumulative / last, 2) if last else None,
        "base_compaction": base_compaction,
        "lost_fact": lost,
        "aggressive_compaction": aggressive,
        "strict_compaction": strict,
        "strict_preserved_identified_fact": (
            lost["fact"].lower() in strict["summary"].lower()
            if lost["status"] != "no_monitored_fact_missing" else None
        ),
        "projection_20": {
            "method": "linear prompt-growth extrapolation; sum prompts for steps 0..20",
            "initial_prompt_tokens": initial,
            "average_tokens_added_per_step": round(avg_delta, 2),
            "estimated_cumulative_tokens": projected_20,
            "design_change": "compact/summarize older history while pinning the goal and keeping recent turns verbatim",
        },
    }


# =====================================================================
# LAB 2.6
# =====================================================================

BRIEF = (
    "Write a 120-word internal note recommending whether our 8-person team "
    "should adopt a shared on-call rotation. Assume we currently have no "
    "rotation and incidents are handled by whoever notices them."
)

RUBRIC = """1. Makes a clear recommendation (adopt / do not adopt), not a survey of options.
2. Gives at least two concrete reasons tied to the stated situation.
3. Names at least one real cost or risk of the recommendation.
4. Is 100-140 words.
5. Contains no invented facts about the team beyond what the brief states."""

WRITER_SYSTEM = (
    "You are a concise internal-communications writer. You produce short, "
    "decisive notes for engineering teams. Output only the note itself."
)

CRITIC_SYSTEM = (
    "You are a strict reviewer. You judge a draft ONLY against the rubric you "
    "are given. You did not write the draft and have no attachment to it. "
    "Start your reply with exactly PASS or FAIL on its own line. If FAIL, "
    "list the numbered rubric items that failed and what specifically is wrong "
    "with each. Do not rewrite the draft yourself."
)


def ask(system, user, temp=0.3):
    r = client(temp).messages.create(
        max_tokens=1400,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(
        b.text for b in r.content if getattr(b, "type", None) == "text"
    ).strip()
    return text, {
        "input": r.usage.input_tokens,
        "output": r.usage.output_tokens,
        "total": r.usage.input_tokens + r.usage.output_tokens,
    }


def producer_critic_run(*, rubric=RUBRIC, critic_system=CRITIC_SYSTEM,
                        max_revisions=2, temp=0.3):
    calls = []
    draft, tok = ask(WRITER_SYSTEM, BRIEF, temp)
    calls.append({"kind": "draft", "tokens": tok})
    initial = draft
    rounds = []
    accepted = False

    for revision in range(1, max_revisions + 1):
        verdict, tok = ask(
            critic_system,
            f"RUBRIC:\n{rubric}\n\nDRAFT:\n{draft}",
            temp,
        )
        calls.append({"kind": "critique", "round": revision, "tokens": tok})
        round_rec = {
            "round": revision,
            "verdict": verdict,
            "draft_before": draft,
        }
        if verdict.upper().startswith("PASS"):
            round_rec["revised"] = False
            rounds.append(round_rec)
            accepted = True
            break

        new_draft, tok = ask(
            WRITER_SYSTEM,
            f"ORIGINAL BRIEF:\n{BRIEF}\n\n"
            f"YOUR PREVIOUS DRAFT:\n{draft}\n\n"
            f"A reviewer rejected it for these reasons:\n{verdict}\n\n"
            f"Rewrite the note addressing every point. Output only the note.",
            temp,
        )
        calls.append({"kind": "revision", "round": revision, "tokens": tok})
        round_rec["revised"] = True
        round_rec["draft_after"] = new_draft
        rounds.append(round_rec)
        draft = new_draft

    return {
        "initial_draft": initial,
        "initial_words": len(initial.split()),
        "rounds": rounds,
        "final_draft": draft,
        "final_words": len(draft.split()),
        "accepted": accepted,
        "max_revisions": max_revisions,
        "model_calls": len(calls),
        "calls": calls,
        "total_tokens": {
            "input": sum(c["tokens"]["input"] for c in calls),
            "output": sum(c["tokens"]["output"] for c in calls),
            "total": sum(c["tokens"]["total"] for c in calls),
        },
    }


def lab26():
    baseline_runs = [producer_critic_run(temp=0.5) for _ in range(3)]

    vague = producer_critic_run(
        rubric="The note should be good and professional.",
        temp=0.3,
    )

    self_critic_system = (
        "You wrote this draft yourself. Review your own work against the rubric "
        "you are given. Start your reply with exactly PASS or FAIL on its own "
        "line. If FAIL, list the failed rubric items and why."
    )
    self_review_runs = [
        producer_critic_run(critic_system=self_critic_system, temp=0.5)
        for _ in range(3)
    ]

    long_ceiling = producer_critic_run(max_revisions=6, temp=0.4)

    def failed_first(run):
        return bool(run["rounds"]) and run["rounds"][0]["verdict"].upper().startswith("FAIL")

    return {
        "baseline_runs": baseline_runs,
        "baseline_first_critique_fail_count": sum(failed_first(r) for r in baseline_runs),
        "vague_rubric": vague,
        "self_review_runs": self_review_runs,
        "self_review_first_critique_fail_count": sum(failed_first(r) for r in self_review_runs),
        "max_revisions_6": long_ceiling,
    }


# =====================================================================
# Evidence output
# =====================================================================

def write_raw(name, value):
    (RAW_DIR / f"{name}.txt").write_text(
        json.dumps(value, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    try:
        probe()
    except Exception as exc:
        print("ERROR: Ollama/model is not ready.")
        print(exc)
        print("")
        print("Run:")
        print("  ollama serve")
        print(f"  ollama pull {MODEL}")
        return 2

    print("[1/3] Running Lab 2.2 experiments...")
    l22 = lab22()
    write_raw("lab22", l22)

    print("[2/3] Running Lab 2.3 measurements...")
    l23 = lab23()
    write_raw("lab23", l23)

    print("[3/3] Running Lab 2.6 producer-critic experiments...")
    l26 = lab26()
    write_raw("lab26", l26)

    data = {
        "meta": {
            "evidence_kind": "real_ollama_execution",
            "model": MODEL,
            "host": HOST,
            "generated_on": datetime.date.today().isoformat(),
        },
        "lab22": l22,
        "lab23": l23,
        "lab26": l26,
    }

    (EVIDENCE_DIR / "day2-evidence.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (EVIDENCE_DIR / "day2-evidence.md").write_text(
        "# Day 2 — Real Ollama Evidence\n\n"
        f"- Model: `{MODEL}`\n"
        f"- Date: `{data['meta']['generated_on']}`\n"
        "- Full structured evidence: `day2-evidence.json`\n"
        "- Raw experiment records: `raw/`\n",
        encoding="utf-8",
    )

    print("PASS: real Day 2 evidence captured.")
    print(EVIDENCE_DIR / "day2-evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
