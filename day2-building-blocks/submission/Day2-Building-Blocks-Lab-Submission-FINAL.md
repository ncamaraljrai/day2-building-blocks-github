# Day 2 — Building Blocks Lab Submission

**Learner:** Nilson Cardoso Amaral Junior  
**Runtime for code labs:** Local Ollama  
**Finalization rule:** This document is generated only after Labs 2.2, 2.3, and 2.6 have real execution evidence.

---

# Lab 2.1 — Design two tools on paper

## Tool 1 — `find_calendar_person`

### Name
`find_calendar_person`

### Description for the model
Resolve a person name or known nickname to the internal calendar identity, canonical display name, and timezone. Use this before any calendar operation when the user supplies a human-readable name rather than a verified internal `person_id`. It does not search by department, job role, or free-form organizational attributes, and it never changes calendar data.

### Argument schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Person id, first name, or full name. Trim surrounding whitespace."
    }
  },
  "required": ["query"]
}
```

## Tool 2 — `check_calendar_availability`

### Name
`check_calendar_availability`

### Description for the model
Return the busy blocks and working hours for one verified person on one specific date. Use this after resolving the person's `person_id` and before proposing or booking a slot involving that person. It reads one person and one day per call; it does not create meetings, infer a different date, or search by name.

### Argument schema

```json
{
  "type": "object",
  "properties": {
    "person_id": {
      "type": "string",
      "description": "Verified internal calendar person id returned by find_calendar_person."
    },
    "date": {
      "type": "string",
      "description": "Calendar date in ISO format YYYY-MM-DD."
    }
  },
  "required": ["person_id", "date"]
}
```

## (a) Failure case

For `check_calendar_availability` with an invalid id:

```text
Unknown person_id 'anna'. Call find_calendar_person first. Valid ids: ['ana', 'ben', 'cai'].
```

That wording tells the agent both what was wrong and the recovery action: resolve the person first and retry with a valid internal id.

For a bad date:

```text
date must be ISO format YYYY-MM-DD, got 'next Monday'.
```

This tells the model the exact accepted format instead of encouraging a blind retry.

## (b) Confusable neighbour

A plausible neighbour is `search_people_by_role(role)`.

Boundary added to `find_calendar_person`:

> Use this only to resolve a supplied human name or known id; do not use it to discover people by role or team — use `search_people_by_role` for that.

Boundary added to `search_people_by_role`:

> Use this for discovery by organizational role; if the user already named a person and you only need the internal calendar id, use `find_calendar_person` instead.

## (c) Tool I refuse to build

I would not expose `delete_calendar_event_without_confirmation(event_id)` to this scheduling agent. Deleting an existing event can affect multiple people and may be difficult to reverse after notifications or downstream workflows fire, so it sits in the high-impact / lower-reversibility part of the Day 1 risk grid. If deletion is ever needed, the agent should prepare a proposed cancellation and require explicit human approval before trusted code performs it.

## (d) Blast radius

**`find_calendar_person`:** a wrong-but-valid query can resolve the wrong person, contaminating every later availability or scheduling decision. The tool itself is read-only, so the immediate blast radius is bounded, but the incorrect identity can propagate.

**`check_calendar_availability`:** a valid but wrong `person_id` or date can make the agent believe a slot is safe when it checked the wrong calendar/day. The direct tool is read-only, but the downstream blast radius can become a wrongly scheduled meeting if later write tools trust that result.

---

# Lab 2.2 — Build a tool-using agent and break it deliberately

## Baseline run

- **Steps:** 3
- **Total tool calls:** 7
- **Tool order:** `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`
- **Parallel-call steps:** [1]
- **Input tokens:** 3119
- **Output tokens:** 609
- **Booked records:** `[{"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 11, "end_hour": 13}]`

### 1. Call sequence
The observed sequence was `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`. Availability was checked for these ids before the first booking call: `['ana', 'ben', 'cai']`.

### 2. Parallel calls
Parallel tool requests occurred on step(s): **[1]**. Multiple calls under one model turn are independent requests that can be batched rather than requiring another reason step between them.

### 3. Slot reasoning
The model commentary and trace show the point where it moved from availability observations to a proposed booking:

- Step 1: `find_person({"query": "Ana"})` → `{"id": "ana", "name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"}`
- Step 1: `find_person({"query": "Ben"})` → `{"id": "ben", "name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"}`
- Step 1: `find_person({"query": "Cai"})` → `{"id": "cai", "name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"}`
- Step 1: `check_availability({"person_id": "ana", "date": "2026-04-06"})` → `{"person_id": "ana", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 11}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "ben", "date": "2026-04-06"})` → `{"person_id": "ben", "date": "2026-04-06", "busy_blocks": [{"start_hour": 13, "end_hour": 15}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2026-04-06"})` → `{"person_id": "cai", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 10}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 2 commentary: Based on the availability of Ana, Ben, and Cai on 2026-04-06, here are their working hours and busy blocks:

- **Ana Ruiz (Europe/Madrid)**:
  - Working hours: 9:00 - 18:00
  - Busy blocks: 9:00 - 11:00

- **Ben Okafor (America/New_York)**:
  - Working hours: 9:00 - 18:00
  - Busy blocks: 13:00 - 15:00

- **Cai Liu (Asia/Singapore)**:
  - Working hours: 9:00 - 18:00
  - Busy blocks: 9:00 - 10:00

To find a free slot that works for all three, we need to look for overlapping free time. Let's check the free slots:

- Ana is free from 11:00 to 18:00.
- Ben is free from 9:00 to 13:00.
- Cai is free from 10:00 to 18:00.

The common free slot that works for all three is from 11:00 to 13:00.

Now, we can book the meeting from 11:00 to 13:00 on 2026-04-06.
- Step 2: `book_meeting({"person_ids": ["ana", "ben", "cai"], "title": "Design Review", "date": "2026-04-06", "start_hour": 11, "duration_hours": 2})` → `{"booked": {"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 11, "end_hour": 13}}`
- Step 3 commentary: The meeting titled "Design Review" has been successfully booked from 11:00 to 13:00 on 2026-04-06. The attendees are Ana, Ben, and Cai.
- Step 3: no tool call; stop_reason=end_turn

The availability tools only returned busy blocks/working hours; the model had to infer the shared free interval before requesting `book_meeting`.

### 4. Steps versus tool calls
The run used **3 model-loop steps** but **7 tool calls**. They differ because one model turn can request zero, one, or several tools; a step counts a model iteration, while tool calls count requested actions.

## Experiment (a) — gutted `book_meeting` description

- **Observed path:** `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`
- **Booked:** `[{"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 15, "end_hour": 17}]`
- **First error:** `(no tool error was observed in this run)`
- **Layer that caught the break:** **nothing blocked the wrong-but-valid action**

- Step 1: `find_person({"query": "Ana"})` → `{"id": "ana", "name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"}`
- Step 1: `find_person({"query": "Ben"})` → `{"id": "ben", "name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"}`
- Step 1: `find_person({"query": "Cai"})` → `{"id": "cai", "name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"}`
- Step 1: `check_availability({"person_id": "ana", "date": "2026-04-06"})` → `{"person_id": "ana", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 11}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "ben", "date": "2026-04-06"})` → `{"person_id": "ben", "date": "2026-04-06", "busy_blocks": [{"start_hour": 13, "end_hour": 15}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2026-04-06"})` → `{"person_id": "cai", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 10}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 2 commentary: Based on the availability of Ana, Ben, and Cai on 2026-04-06, here are their busy blocks and working hours:

- **Ana Ruiz (Europe/Madrid)**:
  - Busy: 09:00 - 11:00
  - Working Hours: 09:00 - 18:00

- **Ben Okafor (America/New_York)**:
  - Busy: 13:00 - 15:00
  - Working Hours: 09:00 - 18:00

- **Cai Liu (Asia/Singapore)**:
  - Busy: 09:00 - 10:00
  - Working Hours: 09:00 - 18:00

To find a free slot that works for all three, we need to look for overlapping free time. Let's compare their free slots:

- Ana is free from 11:00 to 18:00.
- Ben is free from 09:00 to 13:00 and from 15:00 to 18:00.
- Cai is free from 10:00 to 18:00.

The overlapping free time for all three is from 15:00 to 18:00.

Now, let's book the meeting for 2 hours starting at 15:00 on 2026-04-06.
- Step 2: `book_meeting({"date": "2026-04-06", "start_hour": 15, "duration_hours": 2, "person_ids": ["ana", "ben", "cai"], "title": "Design Review"})` → `{"booked": {"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 15, "end_hour": 17}}`
- Step 3 commentary: The meeting titled "Design Review" has been successfully booked for 2 hours starting at 15:00 on 2026-04-06. The attendees are Ana, Ben, and Cai. The meeting will end at 17:00.
- Step 3: no tool call; stop_reason=end_turn

This run demonstrates empirically whether the description still induced the pre-booking availability checks or whether execution-time validation became the last line of defense.

## Experiment (b) — removed date-format hint; goal says “next Monday”

- **Observed path:** `find_person → find_person → find_person → check_availability → check_availability → book_meeting`
- **First error:** `Bad arguments for find_person: run_tools_agent.<locals>.find_person() got an unexpected keyword argument 'person_id'`
- **Layer that caught the break:** **validation/program**

- Step 1: `find_person({"query": "Ana"})` → `{"id": "ana", "name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"}`
- Step 1: `find_person({"query": "Ben"})` → `{"id": "ben", "name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"}`
- Step 1: `find_person({"person_id": "ana", "date": "2023-10-09"})` → `{"error": "Bad arguments for find_person: run_tools_agent.<locals>.find_person() got an unexpected keyword argument 'person_id'"}`
- Step 1: `check_availability({"person_id": "ben", "date": "2023-10-09"})` → `{"person_id": "ben", "date": "2023-10-09", "busy_blocks": [], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2023-10-09"})` → `{"person_id": "cai", "date": "2023-10-09", "busy_blocks": [], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 2: `book_meeting({"duration_hours": 2, "person_ids": ["ana", "ben", "cai"], "title": "Design Review", "date": "2023-10-09", "start_hour": 10})` → `{"booked": {"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2023-10-09", "start_hour": 10, "end_hour": 12}}`
- Step 3 commentary: The design review meeting has been successfully booked for next Monday, October 9th, from 10:00 to 12:00. The attendees are Ana, Ben, and Cai.
- Step 3: no tool call; stop_reason=end_turn

The trace contains the exact date string the model supplied, so the result is measured rather than assumed.

## Experiment (c) — forced 4-hour conflict on 2026-04-07

- **Observed path:** `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting → book_meeting → book_meeting → book_meeting`
- **First conflict/error string:** `Conflicts found: [{'person_id': 'ana', 'busy': '14:00-16:00'}]. Pick a different slot.`
- **Final response:** The meeting titled "Design Review" has been successfully booked from 16:00 to 18:00 on 2026-04-07 with attendees Ana, Ben, and Cai.
- **Layer:** **validation**

- Step 1: `find_person({"query": "Ana"})` → `{"id": "ana", "name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"}`
- Step 1: `find_person({"query": "Ben"})` → `{"id": "ben", "name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"}`
- Step 1: `find_person({"query": "Cai"})` → `{"id": "cai", "name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"}`
- Step 1: `check_availability({"person_id": "ana", "date": "2026-04-07"})` → `{"person_id": "ana", "date": "2026-04-07", "busy_blocks": [{"start_hour": 14, "end_hour": 16}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "ben", "date": "2026-04-07"})` → `{"person_id": "ben", "date": "2026-04-07", "busy_blocks": [], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2026-04-07"})` → `{"person_id": "cai", "date": "2026-04-07", "busy_blocks": [{"start_hour": 9, "end_hour": 12}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 2 commentary: Based on the availability of Ana, Ben, and Cai on 2026-04-07:

- Ana is busy from 14:00 to 16:00.
- Ben is free all day.
- Cai is busy from 09:00 to 12:00.

The only free slot that works for all three is from 12:00 to 16:00. Since we need a 4-hour meeting, the only suitable time is from 12:00 to 16:00.

Now, let's book the meeting.
- Step 2: `book_meeting({"date": "2026-04-07", "start_hour": 12, "duration_hours": 4, "person_ids": ["ana", "ben", "cai"], "title": "Design Review"})` → `{"error": "Conflicts found: [{'person_id': 'ana', 'busy': '14:00-16:00'}]. Pick a different slot."}`
- Step 3 commentary: It seems that the 12:00 to 16:00 slot conflicts with Ana's availability. Let's look for another suitable time slot that works for all three attendees.

Given the working hours and the busy periods, the only feasible slot that doesn't conflict with anyone's schedule is from 16:00 to 20:00. However, since the meeting needs to be 4 hours long and the latest start time is 17:00, the only available slot is from 16:00 to 20:00.

Let's book the meeting from 16:00 to 20:00.
- Step 3: `book_meeting({"date": "2026-04-07", "start_hour": 16, "duration_hours": 4, "person_ids": ["ana", "ben", "cai"], "title": "Design Review"})` → `{"error": "Meeting would end at 20:00, past the 18:00 working limit. Choose an earlier start_hour or shorter duration."}`
- Step 4 commentary: Given the constraints, the only available slot that works for all three attendees is from 16:00 to 20:00, but it exceeds the working hours limit of 18:00. Therefore, we need to find a different slot that ends by 18:00.

The next best option is from 14:00 to 18:00, which is the latest start time that fits within the working hours. Let's book the meeting from 14:00 to 18:00.
- Step 4: `book_meeting({"date": "2026-04-07", "start_hour": 14, "duration_hours": 4, "person_ids": ["ana", "ben", "cai"], "title": "Design Review"})` → `{"error": "Conflicts found: [{'person_id': 'ana', 'busy': '14:00-16:00'}]. Pick a different slot."}`
- Step 5 commentary: It appears that the 14:00 to 18:00 slot conflicts with Ana's availability. Given the constraints, the only remaining slot that fits within the working hours and does not conflict with anyone's schedule is from 16:00 to 18:00.

Let's book the meeting from 16:00 to 18:00.
- Step 5: `book_meeting({"start_hour": 16, "duration_hours": 2, "person_ids": ["ana", "ben", "cai"], "title": "Design Review", "date": "2026-04-07"})` → `{"booked": {"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-07", "start_hour": 16, "end_hour": 18}}`
- Step 6 commentary: The meeting titled "Design Review" has been successfully booked from 16:00 to 18:00 on 2026-04-07 with attendees Ana, Ben, and Cai.
- Step 6: no tool call; stop_reason=end_turn

The informative error gives the model a concrete observation it can use to retry, ask for clarification, or stop.

## Experiment (d) — removed `start_hour` range validation; requested 3am

- **Observed path:** `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`
- **BOOKED after run:** `[{"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 15, "end_hour": 17}]`
- **Layer that caught the break:** **nothing blocked the wrong-but-valid action**

- Step 1: `find_person({"query": "Ana"})` → `{"id": "ana", "name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"}`
- Step 1: `find_person({"query": "Ben"})` → `{"id": "ben", "name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"}`
- Step 1: `find_person({"query": "Cai"})` → `{"id": "cai", "name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"}`
- Step 1: `check_availability({"person_id": "ana", "date": "2026-04-06"})` → `{"person_id": "ana", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 11}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "ben", "date": "2026-04-06"})` → `{"person_id": "ben", "date": "2026-04-06", "busy_blocks": [{"start_hour": 13, "end_hour": 15}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2026-04-06"})` → `{"person_id": "cai", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 10}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `book_meeting({"title": "Design Review", "date": "2026-04-06", "start_hour": 15, "duration_hours": 2, "person_ids": ["ana", "ben", "cai"]})` → `{"booked": {"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 15, "end_hour": 17}}`
- Step 2 commentary: The design review meeting has been successfully booked with Ana, Ben, and Cai on April 6, 2026, from 3pm to 5pm (15:00 to 17:00 local time). This slot was chosen to ensure that everyone is available and to avoid any potential interruptions.
- Step 2: no tool call; stop_reason=end_turn

A schema description such as “9 to 17” is guidance to a statistical model, not a security boundary. Once the executable range check is removed, wrong-but-valid model output can reach the state-changing code.

## Experiment (e) — removed `find_person` from TOOL_SPECS

- **Observed path:** `check_availability → check_availability → check_availability`
- **First error:** `(no tool error was observed in this run)`
- **Booked:** `[]`
- **Layer:** **description/schema/model behavior; no execution-layer rejection observed**

- Step 1: `check_availability({"person_id": "ana", "date": "2026-04-06"})` → `{"person_id": "ana", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 11}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "ben", "date": "2026-04-06"})` → `{"person_id": "ben", "date": "2026-04-06", "busy_blocks": [{"start_hour": 13, "end_hour": 15}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 1: `check_availability({"person_id": "cai", "date": "2026-04-06"})` → `{"person_id": "cai", "date": "2026-04-06", "busy_blocks": [{"start_hour": 9, "end_hour": 10}], "working_hours": {"start_hour": 9, "end_hour": 18}}`
- Step 2 commentary: Based on the availability of Ana, Ben, and Cai on 2026-04-06, we can see that there is no common free slot for all three of them. Here are their schedules:

- Ana is busy from 9:00 to 11:00.
- Ben is busy from 13:00 to 15:00.
- Cai is busy from 9:00 to 10:00.

Since there is no overlapping free time, we cannot book a 2-hour design review meeting for all three on this date. We may need to consider a different date or adjust the meeting duration. Would you like to try another date or change the meeting duration?
- Step 2: no tool call; stop_reason=end_turn

This shows what the model actually did when it needed internal ids but the intended resolution capability was absent, including whether it invented ids that happened to pass validation.


---

# Lab 2.3 — Context growth and compaction

## Growth table

| Step | Tokens this turn | Cumulative processed |
|---:|---:|---:|
| 0 | 54 | 54 |
| 1 | 183 | 237 |
| 2 | 326 | 563 |
| 3 | 468 | 1031 |
| 4 | 636 | 1667 |
| 5 | 767 | 2434 |
| 6 | 861 | 3295 |

- **Final prompt / first prompt:** 15.94×
- **Cumulative total / final prompt:** 3.83×
- **Cumulative tokens through step 6:** 3295

## 1–2. Growth observations

The prompt grows because every iteration sends the goal plus the accumulated history again. The per-turn context therefore grows with the run, while the cumulative column sums increasingly large prefixes; this is why total processing outpaces the number of steps and trends roughly quadratically for similar-sized additions.

## 3. Specific fact lost or blurred during compaction

Detected comparison result: **Northwind overage = 52000 USD**  
Status: **lost_or_blurred**

### Summary produced with `RECENT_TURNS = 2`

- Total spend per vendor (2025-04-01..2026-03-31):
  - Northwind Cloud: $412,000 USD
  - Acme Compute: $288,500 USD
  - Zephyr Hosting: $96,200 USD

- Monthly trend for Northwind Cloud:
  - Monthly spend: [31,200, 32,100, 30,800, 33,400, 35,900, 34,100, 36,800, 38,200, 37,500, 39,900, 41,100, 42,000]
  - Trend: +34.6% over 12 months
  - Driver: object storage egress

- Monthly trend for Acme Compute:
  - Monthly spend: [25,100, 24,800, 24,200, 24,500, 23,900, 24,100, 23,800, 24,000, 23,600, 23,900, 23,400, 23,200]
  - Trend: -7.6% over 12 months
  - Driver: workload migration off VMs

- Contract end dates and notice periods:
  - Northwind Cloud: Ends 2026-09-30, 90 days notice, auto-renew, committed-use 15% discount
  - Acme Compute: Ends 2027-02-28, 30 days notice, no auto-renew, no discount
  - Zephyr Hosting: Ends 2026-05-15, 60 days notice, auto-renew, startup credit

Losing or blurring a spend, date, renewal, overage, or migration detail can change which vendor appears most urgent to renegotiate. Even when core facts survive, compaction changes exact wording and can erase caveats that affect confidence.

## 4. What was pinned?

The original **GOAL** was structurally pinned and never placed in the summarizable middle. Naively truncating the oldest messages could remove the objective itself, leaving an agent that still produces plausible work but no longer knows what outcome it is optimizing.

## Experiment (a) — `RECENT_TURNS = 1`

- Before: 861 tokens
- After: 772 tokens
- Saved: 89 tokens (10.3%)

### Aggressive summary

- {"vendor_spend": [{"vendor": "Northwind Cloud", "usd": 412000}, {"vendor": "Acme Compute", "usd": 288500}, {"vendor": "Zephyr Hosting", "usd": 96200}], "period": "2025-04-01..2026-03-31", "currency": "USD", "note": "Excludes support contracts billed separately."}
- {"vendor": "Northwind Cloud", "monthly_usd": [31200, 32100, 30800, 33400, 35900, 34100, 36800, 38200, 37500, 39900, 41100, 42000], "trend": "+34.6% over 12 months", "driver": "object storage egress"}
- {"vendor": "Acme Compute", "monthly_usd": [25100, 24800, 24200, 24500, 23900, 24100, 23800, 24000, 23600, 23900, 23400, 23200], "trend": "-7.6% over 12 months", "driver": "workload migration off VMs"}
- {"contracts": [{"vendor": "Northwind Cloud", "ends": "2026-09-30", "notice_days": 90, "auto_renew": true, "discount_tier": "committed-use 15%"}, {"vendor": "Acme Compute", "ends": "2027-02-28", "notice_days": 30, "auto_renew": false, "discount_tier": "none"}, {"vendor": "Zephyr Hosting", "ends": "2026-05-15", "notice_days": 60, "auto_renew": true, "discount_tier": "startup credit"}]}
- {"commitments": [{"vendor": "Northwind Cloud", "committed_usd": 360000, "actual_usd": 412000, "overage_usd": 52000, "overage_rate": "list price, no discount"}, {"vendor": "Acme Compute", "committed_usd": 0, "actual_usd": 288500}], "note": "Northwind overage is billed at undiscounted list price."}

Keeping fewer recent turns verbatim saves more context but forces more exact observations through a lossy model-written summary.

## Experiment (b) — demand monetary figures and dates verbatim

- Before: 861 tokens
- After: 593 tokens
- Saved: 268 tokens (31.1%)

### Revised summary

- **Total Spend (USD):**
  - Northwind Cloud: $412,000
  - Acme Compute: $288,500
  - Zephyr Hosting: $96,200
  - Period: 2025-04-01 to 2026-03-31
  - Note: Excludes support contracts billed separately.

- **Monthly Trend (USD):**
  - Northwind Cloud: $31,200 to $42,000; +34.6% over 12 months; Driver: object storage egress
  - Acme Compute: $25,100 to $23,200; -7.6% over 12 months; Driver: workload migration off VMs

- **Contract End Dates and Notice Periods:**
  - Northwind Cloud: Ends 2026-09-30; 90-day notice; Auto-renew: Yes; Discount Tier: Committed-use 15%
  - Acme Compute: Ends 2027-02-28; 30-day notice; Auto-renew: No; Discount Tier: None
  - Zephyr Hosting: Ends 2026-05-15; 60-day notice; Auto-renew: Yes; Discount Tier: Startup credit

The changed compaction prompt demonstrates that preservation policy lives in the summarization instruction. A stronger instruction can improve retention of the specific information it names, but it is still not a guarantee of semantic completeness.

## Experiment (c) — 20-step projection

Measured:
- step-0 prompt: **54 tokens**
- average growth across the measured six steps: **134.5 tokens/step**

Projection method:
`prompt(n) ≈ initial + average_delta × n`, then sum prompts for steps `0..20`.

**Estimated cumulative processing for 20 steps: 29379 tokens.**

One design change that flattens the curve is to **compact/summarize older history while keeping the goal pinned and only recent turns verbatim**. Selective inclusion can flatten it further when phases are cleanly separable.


---

# Lab 2.4 — Decompose a goal properly

**Goal:** Organize a small team workshop.

## 1. Upfront plan: vague → sharpened

| # | Vague version | Sharpened, actionable version |
|---|---|---|
| 1 | Define the workshop | Confirm the workshop objective, expected outcome, attendee list, target week, duration, and budget owner; produce a one-page workshop brief. |
| 2 | Find a venue | Identify three venue/room options that fit the attendee count, required equipment, target week, and budget; record capacity, availability, and cost. |
| 3 | Schedule everyone | Collect attendee availability for the target week and produce two candidate time slots that satisfy the required attendees and venue availability. |
| 4 | Build the agenda | Draft a timed agenda with 3–5 sessions, an owner for each session, expected output, and required pre-work, all tied to the confirmed workshop objective. |
| 5 | Finalize logistics | Confirm the selected slot and venue, send the agenda/pre-work, record dietary/accessibility needs, and publish one final logistics note with owner and due date for every open item. |

Each sharpened task passes the colleague test because it specifies the output, scope, and completion condition.

## 2. Dependencies and parallelism

| Sub-task | Must wait for | Parallel opportunity |
|---|---|---|
| 1. Confirm brief | none | starts first |
| 2. Venue options | 1 | can run in parallel with 4 once constraints are known |
| 3. Candidate slots | 1; final candidate must consider 2 | availability collection can overlap with 2 |
| 4. Draft agenda | 1 | can run in parallel with 2 and availability collection |
| 5. Final logistics | 2, 3, 4 | no; integration step |

The strongest parallel section is venue research + attendee availability collection + initial agenda design after the brief is fixed.

## 3. Forced replan

### Discovery
At the end of sub-task 1, the budget owner reports that the available budget is **half the assumed amount** and external venue rental is no longer affordable.

### Revised remaining tasks
1. Keep the confirmed objective, attendee list, duration, and target week.
2. Replace external venue research with: identify two internal rooms or a remote/hybrid option that satisfy capacity and equipment requirements at zero rental cost.
3. Continue attendee availability collection, but intersect the candidate slots with internal-room availability.
4. Keep the agenda task, but replace paid catering/material assumptions with internal/virtual alternatives.
5. Finalize logistics using the selected internal/hybrid setup and explicitly record any capability sacrificed because of the reduced budget.

### What survived?
The objective, attendees, timing constraints, availability work, and core agenda logic survived. Venue/cost assumptions and some logistics changed. Most of the high-level plan remained useful, which suggests planning the **stable structure** up front while leaving implementation detail revisable.

## 4. Progress tracker

```text
[done]    Confirm objective, attendees, duration, target week, and revised budget
[done]    Identify two internal/hybrid venue options
[current] Intersect attendee availability with room availability; produce two candidate slots
[todo]    Finalize timed agenda and session owners
[todo]    Confirm slot/venue and publish logistics + pre-work
```

If the agent crashed here, the checklist would tell me exactly which outputs already exist, what it was actively doing, and what remains. The raw conversation history contains the same events but would require reconstructing state from many turns and could hide whether an earlier activity was merely discussed or actually completed.

---

# Lab 2.5 — One agent or several?

**Task:** Produce a short market overview of three competitors.

## 1. Single-agent design

### Responsibilities
One agent would:
1. identify/confirm the three competitors;
2. retrieve current official product, positioning, feature, and pricing evidence;
3. record source URLs/dates and caveats;
4. normalize the evidence into a common comparison schema;
5. compare strengths, weaknesses, pricing, and target customer;
6. distinguish sourced facts from inference;
7. draft the short overview;
8. verify that each material claim is supported by retrieved evidence.

### Tool set
- `search_competitor_sources(query, domain_filter)`
- `fetch_source_page(url)`
- `extract_pricing_and_features(page_content, schema)`
- `get_page_metadata(url)`
- optionally a calculator for normalized pricing comparisons

### Worst-moment context
The largest context occurs during final synthesis: the goal and instructions, tool definitions, retrieved evidence for all three competitors, source metadata/caveats, normalized comparison notes, intermediate reasoning, and the draft/verification state are all present together. For a genuinely short overview this is still manageable, but raw page dumps could make it unnecessarily large.

## 2. Multi-agent redesign

### Agent A — Evidence Collector
**Role:** Retrieve and normalize current first-party evidence for all three competitors.  
**Tools:** search, page fetch, page metadata, structured extractor.

**Handoff to Agent B:**

```json
{
  "competitors": [
    {
      "name": "...",
      "positioning": "...",
      "pricing": [{"tier": "...", "price": "...", "unit": "..."}],
      "features": ["..."],
      "sources": [
        {"url": "...", "retrieved_at": "...", "source_type": "official"}
      ],
      "caveats": ["..."]
    }
  ]
}
```

### Agent B — Comparative Analyst
**Role:** Compare the normalized evidence and produce explicit similarities, differences, and uncertainty notes.  
**Tools:** calculator only; no browser required if the evidence contract is complete.

**Handoff to Agent C:**

```json
{
  "comparison": [
    {
      "dimension": "pricing|positioning|features|target_customer",
      "finding": "...",
      "supporting_source_ids": ["..."],
      "confidence": "high|medium|low",
      "caveat": "..."
    }
  ],
  "recommended_emphasis": ["..."]
}
```

### Agent C — Writer / verifier
**Role:** Produce the short market overview without introducing claims that are absent from the structured evidence.  
**Tools:** source-id lookup/verification tool only.

## 3. Lossy handoff

The Evidence Collector may notice that a pricing page looks current but one footnote says a price applies only to annual prepayment. If its normalized handoff includes the number but omits that caveat, the Analyst can make a mathematically clean but materially wrong comparison. The receiving agent cannot recover context that never crossed the interface; this is why the handoff schema explicitly includes `caveats` and source metadata.

## 4. Honest trade-off and decision

**Real improvement from multi-agent:** the research context can be separated from analysis/writing, and evidence collection can be parallelized across competitors. A fresh writer also has less incentive to rationalize an earlier research mistake.

**New cost/failure mode:** extra model calls, lossy interfaces, duplicated context, integration mistakes, and a harder trace when the final claim is wrong.

**Decision:** for a **short overview of only three competitors**, I would start with a **single agent with a structured plan and tightly bounded retrieval**, not a multi-agent system. The task does not inherently require distinct permissions/specialties, the context should fit if tool output is capped, and the latency benefit from parallel workers is unlikely to justify the coordination cost. I would split it only if evidence volume overflows one context, different workers require materially different tools/permissions, or measured latency/quality shows that parallel specialization helps.

---

# Lab 2.6 — Producer-critic pair

## 1. Did the critic fail the draft?

Three independent baseline executions:

- Run 1: initial=83 words; final=99 words; calls=5; accepted=False; first verdict=FAIL
- Run 2: initial=78 words; final=92 words; calls=5; accepted=False; first verdict=FAIL
- Run 3: initial=74 words; final=86 words; calls=5; accepted=False; first verdict=FAIL

**First-critique FAIL frequency:** 3/3.

### Baseline run 1 — critic rounds

```text
[
  {
    "round": 1,
    "verdict": "FAIL\n1. The recommendation is not clearly stated as a singular option. It suggests adopting a shared on-call rotation but does not clearly indicate whether this is the sole recommendation or one of several options.\n2. Only one concrete reason is provided (24/7 coverage and improved response times). A second reason is lacking.\n3. There is no mention of any cost or risk associated with the recommendation.\n4. The draft is 151 words, exceeding the word limit.\n5. The draft does not contain any invented facts about the team beyond what the brief states, but it could be improved by providing more specific details that align with the brief.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nConsidering our current incident handling process and team size, I recommend we adopt a shared on-call rotation. With only 8 of us, the current approach can lead to inconsistent coverage and potential delays in response. A rotation would ensure 24/7 coverage, improve response times, and distribute the workload more evenly. This will also help in building cross-functional skills and reducing burnout.\n\nLet's discuss this further at our next meeting to finalize the schedule and responsibilities.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation to ensure consistent coverage and faster incident response. With only 8 team members, our current approach often results in inconsistent handling and delayed reactions. A rotation will provide 24/7 support, improve response times, and distribute workload evenly, reducing burnout.\n\nAdditionally, this will enhance cross-functional skills and ensure no one is overburdened. No costs or risks are associated with this change, as it only involves redistributing existing responsibilities.\n\nLet's discuss this further at our next meeting.\n\nBest,\n[Your Name]"
  },
  {
    "round": 2,
    "verdict": "FAIL\n1. The draft does not clearly state a recommendation. It presents a shared on-call rotation as a possibility without explicitly stating whether to adopt or not adopt it.\n3. The draft does not mention any real costs or risks associated with the recommendation. It states there are no costs or risks, which is not aligned with the rubric's requirement to name at least one real cost or risk.\n4. The draft is 126 words, which is within the word count but does not address the rubric's requirement for a clear recommendation or mention of costs or risks.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation to ensure consistent coverage and faster incident response. With only 8 team members, our current approach often results in inconsistent handling and delayed reactions. A rotation will provide 24/7 support, improve response times, and distribute workload evenly, reducing burnout.\n\nAdditionally, this will enhance cross-functional skills and ensure no one is overburdened. No costs or risks are associated with this change, as it only involves redistributing existing responsibilities.\n\nLet's discuss this further at our next meeting.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation to ensure consistent coverage and faster incident response. With only 8 team members, our current approach often results in inconsistent handling and delayed reactions. A rotation will provide 24/7 support, improve response times, and distribute workload evenly, reducing burnout.\n\nHowever, this change involves redistributing responsibilities, which may initially require some adjustment time. Additionally, there could be a slight initial overhead in setting up the rotation system and communication channels.\n\nLet's discuss this further at our next meeting to ensure everyone is on board.\n\nBest,\n[Your Name]"
  }
]
```

The critic's judgment is evidence, not ground truth; I still compare each stated failure with the explicit rubric, especially recommendation clarity, number of reasons, named risk, 100–140-word bound, and invented facts.

## 2. Did revision improve it?

### Draft 0

Subject: On-Call Rotation Recommendation

Team,

Considering our current incident handling process and team size, I recommend we adopt a shared on-call rotation. With only 8 of us, the current approach can lead to inconsistent coverage and potential delays in response. A rotation would ensure 24/7 coverage, improve response times, and distribute the workload more evenly. This will also help in building cross-functional skills and reducing burnout.

Let's discuss this further at our next meeting to finalize the schedule and responsibilities.

Best,
[Your Name]

### Final

Subject: On-Call Rotation Recommendation

Team,

I recommend we adopt a shared on-call rotation to ensure consistent coverage and faster incident response. With only 8 team members, our current approach often results in inconsistent handling and delayed reactions. A rotation will provide 24/7 support, improve response times, and distribute workload evenly, reducing burnout.

However, this change involves redistributing responsibilities, which may initially require some adjustment time. Additionally, there could be a slight initial overhead in setting up the rotation system and communication channels.

Let's discuss this further at our next meeting to ensure everyone is on board.

Best,
[Your Name]

- Draft 0 words: **83**
- Final words: **99**
- Accepted by critic: **False**

The relevant comparison is rubric-by-rubric, not simply whether the prose sounds smoother. A revision can improve one criterion while making another worse, especially word count or unsupported specificity.

## 3. Model-call count and extra spend

Baseline run 1 used **5 model calls** and **1958 total measured tokens** (1342 input + 616 output).

A single unreviewed draft would use one model call. The extra calls buy an independent pass against a checkable rubric plus targeted revisions; whether that spend is justified depends on whether the observed failures matter.

## 4. Three-run non-determinism

The three baseline runs above produced a first-critique FAIL rate of **3/3**. Differences across runs are direct evidence that the critic is non-deterministic and should be evaluated statistically rather than trusted from one example.

## Experiment (a) — vague rubric

Summary: initial=91 words; final=91 words; calls=2; accepted=True; first verdict=PASS

```text
[
  {
    "round": 1,
    "verdict": "PASS",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nConsidering our current incident handling process and team size, I recommend adopting a shared on-call rotation. With only 8 of us, the current approach can lead to burnout and inconsistent response times. A rotation would ensure everyone gets a fair share of responsibility, maintain a balanced workload, and improve our overall responsiveness to issues. This will also enhance our preparedness and reduce the risk of critical issues slipping through the cracks.\n\nLet's discuss this further at our next meeting to finalize the details.\n\nBest,\n[Your Name]",
    "revised": false
  }
]
```

A strict-sounding critic cannot compensate for an uncheckable criterion. “Good and professional” provides no measurable target such as word range, minimum reasons, or prohibition on invented facts, so the feedback becomes less reproducible and less actionable.

## Experiment (b) — remove reviewer independence

**Independent baseline first-critique FAIL frequency:** 3/3  
**Self-review first-critique FAIL frequency:** 2/3

- Self-review run 1: initial=74 words; final=74 words; calls=2; accepted=True; first verdict=PASS
- Self-review run 2: initial=80 words; final=90 words; calls=4; accepted=True; first verdict=FAIL
- Self-review run 3: initial=102 words; final=90 words; calls=4; accepted=True; first verdict=FAIL

This is the measured comparison. Telling the critic that it authored the draft can change how readily it detects defects because it is no longer framed as an independent reviewer with fresh context.

## Experiment (c) — `MAX_REVISIONS = 6`

Summary: initial=89 words; final=88 words; calls=13; accepted=False; first verdict=FAIL

```text
[
  {
    "round": 1,
    "verdict": "FAIL\n1. The draft does not make a clear recommendation. It suggests implementing a shared on-call rotation but does not explicitly state whether to adopt or not adopt this recommendation.\n2. The draft provides two concrete reasons: improving response times and distributing the workload evenly. However, it does not tie these reasons directly to the stated situation.\n3. The draft does not name any real cost or risk of the recommendation.\n4. The draft is 118 words, which is within the acceptable range but not strictly 100-140 words.\n5. The draft does not contain any invented facts about the team beyond what the brief states.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nAs we navigate incident handling, I recommend we implement a shared on-call rotation. Currently, incidents are handled by whoever notices them, which can lead to inconsistent response times and potential gaps in coverage. A shared rotation would ensure 24/7 coverage, improve response times, and distribute the workload more evenly. This approach also enhances our team's readiness and reduces the strain on individuals who might handle incidents frequently.\n\nLet's discuss the details and set up a rotation plan that works for everyone. \n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled by whoever notices them, leading to inconsistent response times and potential gaps in coverage. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload more evenly, reducing the strain on individuals. This approach enhances our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  },
  {
    "round": 2,
    "verdict": "FAIL\n1. The draft does not make a clear recommendation; it merely suggests discussing the idea.\n2. The draft provides only one concrete reason (improving response times and workload distribution) instead of two.\n3. The draft does not mention any real cost or risk associated with the recommendation.\n4. The draft is 113 words, which is within the acceptable range but not long enough to fully address the recommendation.\n5. The draft does not contain any invented facts about the team beyond what the brief states.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled by whoever notices them, leading to inconsistent response times and potential gaps in coverage. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload more evenly, reducing the strain on individuals. This approach enhances our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI strongly recommend we adopt a shared on-call rotation. Currently, incidents are handled by whoever notices them, leading to inconsistent response times and potential gaps in coverage. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload more evenly, reducing the strain on individuals. This approach will also minimize the risk of burnout and enhance our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  },
  {
    "round": 3,
    "verdict": "FAIL\n1. The draft is a survey of options rather than making a clear recommendation.\n3. There is no mention of a real cost or risk associated with the recommendation.\n4. The draft is 117 words, which is below the required minimum.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI strongly recommend we adopt a shared on-call rotation. Currently, incidents are handled by whoever notices them, leading to inconsistent response times and potential gaps in coverage. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload more evenly, reducing the strain on individuals. This approach will also minimize the risk of burnout and enhance our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  },
  {
    "round": 4,
    "verdict": "FAIL\n1. The draft does not clearly state whether to adopt or not adopt the on-call rotation.\n2. The draft provides only one concrete reason (improving response times and coverage) and one additional benefit (distributing workload evenly), falling short of the requirement for two concrete reasons tied to the situation.\n3. The draft does not mention any real cost or risk associated with the recommendation.\n4. The draft is 123 words, which is within the word limit but does not fully address the rubric requirements.\n5. The draft does not contain invented facts about the team beyond what the brief states, but it does not fully address the other rubric items.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency. Without a rotation, we risk critical incidents going unaddressed, which could impact our service uptime and user experience. Additionally, uneven workload distribution can lead to burnout and reduced morale.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  },
  {
    "round": 5,
    "verdict": "FAIL\n1. The draft provides a survey of options (shared on-call rotation vs. no rotation) rather than making a clear recommendation.\n2. While two reasons are given, they are not tied to the stated situation. The reasons provided (improving response times and distributing workload) are general and not specific to the current inconsistent handling of incidents.\n3. No real cost or risk of the recommendation is named.\n4. The draft is 121 words, which is within the acceptable range but not a strict failure.\n5. The draft does not contain any invented facts about the team beyond what the brief states.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency. Without a rotation, we risk critical incidents going unaddressed, which could impact our service uptime and user experience. Additionally, uneven workload distribution can lead to burnout and reduced morale.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency. Without a rotation, critical incidents could go unaddressed, impacting our service uptime and user experience. Additionally, uneven workload distribution can lead to burnout and reduced morale.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  },
  {
    "round": 6,
    "verdict": "FAIL\n1. The draft provides a survey of options (shared on-call rotation vs. no rotation) rather than making a clear recommendation.\n2. The draft provides two concrete reasons (improved response times and workload distribution) tied to the stated situation.\n3. The draft names a real cost or risk (uneven workload distribution and burnout) of not adopting the recommendation.\n4. The draft is 119 words, which is within the specified range.\n5. The draft does not contain any invented facts about the team beyond what the brief states.",
    "draft_before": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. This approach minimizes risks and enhances our team's readiness and efficiency. Without a rotation, critical incidents could go unaddressed, impacting our service uptime and user experience. Additionally, uneven workload distribution can lead to burnout and reduced morale.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]",
    "revised": true,
    "draft_after": "Subject: On-Call Rotation Recommendation\n\nTeam,\n\nI recommend we adopt a shared on-call rotation. Currently, incidents are handled inconsistently, leading to variable response times and potential coverage gaps. Implementing a rotation will ensure 24/7 coverage, improve response times, and distribute the workload evenly, reducing individual strain and burnout. Without a rotation, critical incidents could go unaddressed, impacting our service uptime and user experience. This approach minimizes risks and enhances our team's readiness and efficiency.\n\nLet's discuss and set up a rotation plan that works for everyone.\n\nBest,\n[Your Name]"
  }
]
```

The result shows whether this run converged to PASS or continued generating new objections. Regardless of the observed outcome, the ceiling is required because a producer and critic can otherwise continue handing work back indefinitely.


---

# Final submission integrity

Labs 2.2, 2.3, and 2.6 in the generated final document are populated only from `evidence/day2-evidence.json`, which is created by real Ollama runs. The generator refuses to produce the final submission if required runtime evidence is absent.
