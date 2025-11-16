High-level fix (what we’re actually doing)

We’re going to add one post-pass module that:

Takes the full sheet text (e.g. E5.00-PANEL-SCHEDULES-Rev.3)

Splits it into panel blocks using a generic pattern:

Panel:\s*([A-Za-z0-9.\-]+)


That covers:

K1, L1, H1, K1S

L1-20, L2-20, L2.2-20, L3.1-20, etc.

For each panel block:

Send the panel text to SCHEDULE_MODEL = gpt-4.1-mini

Ask it to return one JSON object per circuit (not per row), so both odd and even are explicitly listed.

Replace / fill the panel’s CIRCUITS array in your structured JSON with that model output.

So instead of kludging more heuristics into the existing geometry/column logic, we basically say:

“You know what? For panel schedules, let the model do the hard part. We’ll give it a clean slice of text per panel and ask for ‘all circuits 1–84 with spares/spaces’ as JSON.”

That’s the OpenAI-dev-approved, future-proof answer:
minimal deterministic code, maximal use of a cheap, smart model.

What the model call should look like (conceptually)

For each panel block, you send something like:

You are extracting circuits from an electrical panel schedule.

Here is the raw text for a single panel:

[panel text block here]


Return JSON with one object per circuit (not per row), like:

{
  "panel_name": "K1",
  "circuits": [
    {
      "circuit_number": 1,
      "load_name": "SLUSHIE MACHINE",
      "trip_amps": 20,
      "is_spare_or_space": false
    },
    {
      "circuit_number": 2,
      "load_name": "SPACE",
      "trip_amps": null,
      "is_spare_or_space": true
    }
  ]
}


Rules:

Use the circuit numbers that appear in the text (e.g. 1–84).

Include ALL circuits, including “SPARE” or “SPACE”.

If a row contains two circuits (odd on the left, even on the right), return two separate circuit objects.

Ignore panel totals, enclosure/rating, and footnotes.

Do not invent extra circuits; only output circuits that clearly exist in the text.

gpt-4.1-mini is perfect for this: the prompt is clear, panel text is small, and you can do this per panel without caring about custom names.

How to wire it (what to tell Cursor)

Here’s the Cursor prompt you can paste. It assumes the code that emits panel JSON lives under tools/schedule_postpass or similar (adjust paths as needed — Cursor will find them):

👉 Prompt for Cursor (copy-paste this):

I have a bug in my schedule/panel extraction:
panel schedules like E5.00-PANEL-SCHEDULES-Rev.3.pdf are missing all even-numbered circuits in the final JSON.
Odd circuits (1,3,5,…) are there, but the even circuits are not being extracted correctly.

I want a small, model-driven post-pass that fixes this in a generic, future-proof way without depending on panel names like “K1” or “L1”.
I’m using gpt-4.1-mini and gpt-4.1-nano with these env vars:

DEFAULT_MODEL=gpt-4.1-mini

LARGE_DOC_MODEL=gpt-4.1-mini

SCHEDULE_MODEL=gpt-4.1-mini

TINY_MODEL=gpt-4.1-nano

TINY_MODEL_THRESHOLD=3000

Please implement the following:

Add a new module in the processing/ETL code, something like:

tools/schedule_postpass/panel_text_postpass.py
with a function:

async def fill_panels_from_sheet_text(
    sheet_json: dict,
    sheet_text: str,
    client: OpenAI | AsyncOpenAI,
) -> dict:
    """
    Use SCHEDULE_MODEL (gpt-4.1-mini) to extract all circuits for each panel
    from the raw sheet text, and fill/replace ELECTRICAL.PANELS[*].CIRCUITS.
    Returns a modified copy of sheet_json.
    """


Inside fill_panels_from_sheet_text:

Use a generic regex to find panel headers in sheet_text:

PANEL_RE = re.compile(r"Panel:\\s*([A-Za-z0-9.\\-]+)")


This must work for:

K1, L1, H1, K1S

high-rise panels like L1-20, L2-20, L2.2-20, L3.1-20, etc.

Build panel blocks by slicing sheet_text between successive Panel: matches:

# pseudo-code
matches = list(PANEL_RE.finditer(sheet_text))
for i, m in enumerate(matches):
    name = m.group(1)
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(sheet_text)
    panel_block_text = sheet_text[start:end]


For each panel_block_text, call SCHEDULE_MODEL once with a prompt that:

explains that this is the text for a single panel schedule

asks for one JSON object per circuit, including spares/spaces

makes it explicit that rows often contain two circuits (odd + even) and both must be returned.

Parse the JSON response and map it into the existing schema under:

sheet_json["ELECTRICAL"]["PANELS_BY_NAME"][panel_name]["CIRCUITS"]


or whatever the current PANELS / CIRCUITS structure is in this repo.
Important: keep existing metadata fields (like panel_name, voltages, etc.) and only replace/fill the CIRCUITS list.

Wiring it into the pipeline:

Find where the structured JSON for electrical sheets (panel schedules) is finalized — the place where we already have:

sheet_json (structured)

the raw sheet_text for the same sheet (the full text content of the page)

After the existing panel extraction logic runs, call:

if is_panel_schedule_sheet(sheet_json):  # e.g. title contains "PANEL SCHEDULES" or ELECTRICAL.PANELS exists
    sheet_json = await fill_panels_from_sheet_text(
        sheet_json=sheet_json,
        sheet_text=sheet_text,
        client=openai_client,  # reuse the existing client + SCHEDULE_MODEL env var
    )


Implement is_panel_schedule_sheet in the simplest robust way:

e.g. bool(sheet_json.get("ELECTRICAL", {}).get("PANELS")) or by checking the drawing title.

Safety / debuggability:

If the model call fails or returns invalid JSON, do not crash the pipeline.
Log a warning and return the original sheet_json unchanged.

Add a small log statement per panel like:

[panel_text_postpass] panel K1: model_circuits=84, existing_circuits=77


so I can see quickly that it fixed the “missing evens” case.

Testing focus (very important):

Test this on E5.00-PANEL-SCHEDULES-Rev.3.pdf.

Confirm that after the post-pass:

K1 has 84 circuits

L1 has 84 circuits

H1 has 42 circuits

K1S has 12 circuits
including all SPARE/SPACE slots.

I don’t care about perfect semantics right now (trip/phase details can be slightly off); I do care that we have the correct count of circuits with correct numbers.

Please keep this change as self-contained as possible:

New module for the post-pass

A small hook in the existing ETL after panel JSON is created

No invasive refactors of the core extractor

I want this to be easy to revert in my IDE if something goes wrong, but powerful enough that it actually fixes the “missing all even circuits” problem in one shot.

If you paste that into Cursor, it should:

Find the right place in your repo

Add a small, focused post-pass

Wire it in with minimal disruption

And from there, it’s just:

Run your ETL on E5.00

Check panel circuit counts

If you like it, keep it. If you hate it, revert.

If you want, after Cursor makes the patch, you can paste the new panel_text_postpass.py in here and I’ll walk through it with you line-by-line to make sure it’s clean and doesn’t sneak in any brittle BS.

Look into this.