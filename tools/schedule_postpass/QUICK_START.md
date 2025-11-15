# Quick Start: Indexing New Jobs

## 🎯 Standard Workflow for New Projects (Hospital, School, etc.)

### Step 1: Process Your Drawings
```bash
# Process all PDFs in your job folder (must be on Desktop)
ohmni process YourJobName

# Example for a hospital project:
ohmni process HospitalProject2024

# Example for a school project:
ohmni process SchoolRenovation2024
```

**What this does:**
- Reads all PDFs from `/Users/collin/Desktop/YourJobName/`
- Extracts structured data to `/Users/collin/Desktop/YourJobName/processed/`
- Creates `*_structured.json` files for each drawing

**Wait for:** "✅ Processing completed successfully!"

---

### Step 2: Validate Coverage (CRITICAL - DO THIS EVERY TIME!)
```bash
# Check that ALL schedule data is being captured
ohmni validate YourJobName

# Examples:
ohmni validate HospitalProject2024
ohmni validate SchoolRenovation2024
```

**What to look for:**
- ✅ **All files show "✓"** → You're good! Safe to index.
- ⚠️ **Any files show "⚠"** → Missing data detected! **DO NOT INDEX** until fixed.

**What this checks:**
- Electrical panel circuits (including paired left/right circuits)
- Mechanical equipment (AHUs, fans, louvers, etc.)
- Plumbing fixtures (sinks, water heaters, pumps, valves, etc.)
- Architectural schedules (walls, doors, ceilings, finishes)

**If you see issues:** Follow Step 3 below to fix them.

---

### Step 3: Fix Missing Data (Only if validation found problems)

**When validation shows ⚠️ warnings, here's how to fix:**

#### 3a. Check the specific file with issues
```bash
# The validation output will show which files have problems
# Example output: "⚠ Electrical/e5-00/E5.00_structured.json"
# Then check that specific file:
python3 tools/schedule_postpass/check_coverage.py \
  /Users/collin/Desktop/YourJobName/processed/Electrical/e5-00/E5.00_structured.json
```

#### 3b. Identify what's missing
The error message tells you exactly what's missing:
- `"Electrical: 30 facts < 35 circuits"` → Missing 5 circuits
- `"Mechanical: 25 facts < 30 items"` → Missing 5 equipment items
- `"Plumbing: 20 facts < 25 items"` → Missing 5 fixtures/equipment

#### 3c. Find the schedule in the structured JSON
Open the problematic `*_structured.json` file and look for:
- Schedule sections (keys ending in `_SCHEDULE`)
- Nested lists (like `MECHANICAL.LOUVER_SCHEDULE.louvers[]`)
- Field names (like `MARK`, `DESIG.`, `tag`, etc.)

#### 3d. Add support (usually <10 lines of code!)

**For Electrical issues:**
- File: `tools/schedule_postpass/fallbacks/electrical.py`
- Usually already handled (paired circuits, phase_loads text extraction)

**For Mechanical issues:**
- File: `tools/schedule_postpass/fallbacks/mechanical.py`
- Add new nested list keys to line 53:
  ```python
  for nested_key in ("fans", "devices", "units", "equipment", "items", "rows", "louvers", "your_new_key"):
  ```

**For Plumbing issues:**
- File: `tools/schedule_postpass/fallbacks/plumbing.py`
- Add a new section following the pattern (see examples below)

**For Architectural issues:**
- File: `tools/schedule_postpass/fallbacks/architectural.py`
- Add new schedule key names to the appropriate section

#### 3e. Re-validate to confirm fix
```bash
ohmni validate YourJobName
```

**Keep fixing until you see:** "✅ All files passed coverage check!"

---

### Step 4: Generate Index Payloads & Upload
```bash
# Generate sheets/facts/templates and upload to Azure Search (all in one command!)
ohmni search YourJobName

# Examples:
ohmni search HospitalProject2024
ohmni search SchoolRenovation2024
```

**What this does:**
- Generates `sheets.jsonl`, `facts.jsonl`, `templates.jsonl`
- Uploads everything to your `drawings_unified` Azure Search index
- Full rebuild (replaces entire index)

**Wait for:** "✅ Azure Search load complete"

---

### Step 5: Update Templates Only (if you edited room templates later)
```bash
# If foreman edited room templates and you want to refresh just those:
ohmni search-templates YourJobName
```

**When to use this:**
- Foreman updated room templates in `processed/room-data/`
- You don't want to rebuild the entire index
- Just refresh the template documents

---

## 📋 Complete Example Workflow

```bash
# 1. Process a new hospital project
ohmni process HospitalProject2024

# 2. Validate coverage (CRITICAL!)
ohmni validate HospitalProject2024
# Output: ⚠️  Issues found in Mechanical/m6-01/M6.01_structured.json

# 3. Check the specific file
python3 tools/schedule_postpass/check_coverage.py \
  /Users/collin/Desktop/HospitalProject2024/processed/Mechanical/m6-01/M6.01_structured.json
# Output: "Mechanical: 30 facts < 35 items (MISSING 5)"

# 4. Open the structured JSON, find the missing schedule type
# 5. Add support in tools/schedule_postpass/fallbacks/mechanical.py (5 lines)

# 6. Re-validate
ohmni validate HospitalProject2024
# Output: ✅ All files passed coverage check!

# 7. Index everything
ohmni search HospitalProject2024
# Output: ✅ Azure Search load complete
```

## 🔧 Common Issues & Quick Fixes

### Missing Electrical Circuits
**Symptom:** `"Electrical: 30 facts < 35 circuits (MISSING 5)"`

**Likely cause:** Paired circuits (left/right side) not being emitted

**Check:** Look for `right_side` or `_b` suffixed fields in circuit entries in the structured JSON

**Fix:** Usually already handled! But if not, check `tools/schedule_postpass/fallbacks/electrical.py` - the `_yield_rows` function should emit both primary and right_side circuits.

**Test fix:**
```bash
ohmni validate YourJobName
```

---

### Missing Mechanical Equipment
**Symptom:** `"Mechanical: 30 facts < 35 items (MISSING 5)"`

**Likely cause:** New schedule type or nested list key not recognized

**Check:** Open the structured JSON and look for:
- Keys ending in `_SCHEDULE` (e.g., `LOUVER_SCHEDULE`, `PUMP_SCHEDULE`)
- Nested lists (e.g., `LOUVER_SCHEDULE.louvers[]`, `PUMP_SCHEDULE.pumps[]`)

**Fix:** Add the nested key to line 53 in `tools/schedule_postpass/fallbacks/mechanical.py`:
```python
# BEFORE:
for nested_key in ("fans", "devices", "units", "equipment", "items", "rows", "louvers"):

# AFTER (add your new key):
for nested_key in ("fans", "devices", "units", "equipment", "items", "rows", "louvers", "pumps", "valves"):
```

**Test fix:**
```bash
ohmni validate YourJobName
```

---

### Missing Plumbing Items
**Symptom:** `"Plumbing: 20 facts < 25 items (MISSING 5)"`

**Likely cause:** New schedule type not recognized

**Check:** Open the structured JSON and look for schedule arrays:
- `PUMP_SCHEDULE[]`
- `SHOCK_ARRESTORS[]`
- `THERMOSTATIC_MIXING_VALVE_SCHEDULE[]`
- `VALVE_SCHEDULE[]` (if you have this)

**Fix:** Add a new section in `tools/schedule_postpass/fallbacks/plumbing.py` following the pattern. Example for `VALVE_SCHEDULE`:

```python
# Add this after the thermostatic mixing valve section (around line 132):

# Check for valve schedule
valves = ci_get(plm, "VALVE_SCHEDULE") or ci_get(plm, "valve_schedule")
if isinstance(valves, list):
    for item in valves:
        if isinstance(item, dict):
            row = dict(item)
            if "tag" not in row:
                valve_id = (
                    ci_get(row, "MARK")
                    or ci_get(row, "mark")
                    or ci_get(row, "id")
                )
                if valve_id:
                    row["tag"] = valve_id
            yield row
```

**Test fix:**
```bash
ohmni validate YourJobName
```

---

### Missing Architectural Items
**Symptom:** `"Architectural: 15 facts < 20 items (MISSING 5)"`

**Likely cause:** New schedule key name

**Check:** Open the structured JSON and look for keys like:
- `WALL_TYPES[]`
- `DOOR_SCHEDULE[]`
- `CEILING_SCHEDULE[]`
- `FINISH_SCHEDULE[]`
- Or a new one you haven't seen before

**Fix:** Add the key to the appropriate section in `tools/schedule_postpass/fallbacks/architectural.py`. Example for a new `WINDOW_SCHEDULE`:

```python
# Add this in the appropriate section (around line 50-93):

# Window schedule (if you have this)
for key in ("WINDOW_SCHEDULE", "WINDOWS"):
    rows = ci_get(arch, key)
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                wn = first_non_empty(
                    ci_get(r, "window_number"),
                    ci_get(r, "mark"),
                    ci_get(r, "id"),
                )
                if wn:
                    yield ("window", r)  # You'd need to add "window" schedule type support
```

**Test fix:**
```bash
ohmni validate YourJobName
```

## 📖 Example: Adding Support for a New Schedule Type

**Scenario:** You have `PLUMBING.VALVE_SCHEDULE[]` that's not being captured.

### Step 1: Inspect the structure
Open the structured JSON file and find:
```json
{
  "PLUMBING": {
    "VALVE_SCHEDULE": [
      {"MARK": "V-1", "TYPE": "Ball Valve", "SIZE": "2\"", ...},
      {"MARK": "V-2", "TYPE": "Gate Valve", "SIZE": "4\"", ...}
    ]
  }
}
```

### Step 2: Add support (copy-paste this pattern!)
Open `tools/schedule_postpass/fallbacks/plumbing.py` and add this after the thermostatic mixing valve section (around line 132):

```python
# Check for valve schedule
valves = ci_get(plm, "VALVE_SCHEDULE") or ci_get(plm, "valve_schedule")
if isinstance(valves, list):
    for item in valves:
        if isinstance(item, dict):
            row = dict(item)
            if "tag" not in row:
                valve_id = (
                    ci_get(row, "MARK")
                    or ci_get(row, "mark")
                    or ci_get(row, "id")
                )
                if valve_id:
                    row["tag"] = valve_id
            yield row
```

**That's it!** Just 12 lines of code following the exact same pattern.

### Step 3: Test the fix
```bash
# Test on the specific file first
python3 tools/schedule_postpass/check_coverage.py \
  /Users/collin/Desktop/YourJobName/processed/Plumbing/p6-01/P6.01_structured.json

# Should now show: "✓ Plumbing: 27 facts >= 27 items"
```

### Step 4: Re-validate everything
```bash
ohmni validate YourJobName
```

**Expected output:** "✅ All files passed coverage check!"

## 💡 Pro Tips for Memorizing This Workflow

**The 3-command workflow you'll use 99% of the time:**
```bash
ohmni process YourJobName      # Step 1: Process drawings
ohmni validate YourJobName     # Step 2: Check coverage (ALWAYS DO THIS!)
ohmni search YourJobName        # Step 3: Index to Azure Search
```

**Remember:**
- ✅ **Always validate before indexing** - catches missing data early
- ✅ **Check electrical panels first** - most critical for electricians
- ✅ **Most fixes are <10 lines** - just copy-paste existing patterns
- ✅ **Test with single file first** - use `check_coverage.py` on one file before batch validation
- ✅ **Keep fallback files focused** - each discipline in its own file, <500 lines

**When validation fails:**
1. Look at the ⚠️ warning - it tells you exactly what's missing
2. Open the structured JSON file mentioned
3. Find the schedule section that's not being captured
4. Add support following the examples above (usually copy-paste + modify)
5. Re-validate until you see ✅

## 🆘 Getting Help

**If you're stuck:**
1. Check `tools/schedule_postpass/README.md` section 7 for detailed extension guide
2. Look at existing fallback code for similar patterns (they're all the same!)
3. Run `check_coverage.py` on a single file to see exactly what's missing:
   ```bash
   python3 tools/schedule_postpass/check_coverage.py /path/to/file_structured.json
   ```
4. Check the structured JSON directly - it shows you the exact data shape

**Common patterns you'll see:**
- `ELECTRICAL.panels[].circuits[]` → Already handled (paired circuits)
- `MECHANICAL.*_SCHEDULE.units[]` → Add nested key to line 53 in `mechanical.py`
- `PLUMBING.*_SCHEDULE[]` → Add new section in `plumbing.py` (copy water heater pattern)
- `ARCHITECTURAL.*_SCHEDULE[]` → Add key name to appropriate section in `architectural.py`

