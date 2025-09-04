### Overview
- We audited prompt usage, identified legacy/specialized prompt code that’s no longer used, and produced a PRD to simplify to a single GENERAL prompt and reduce code bloat.
- We assessed the metadata repair step and aligned the plan with your Azure AI Search schema and ingestion strategy.

### Key Findings
- **Prompt selection today**: `templates/prompt_registry.py` always returns the GENERAL prompt, making specialized prompt modules redundant.
- **Redundant modules**: `templates/prompts/architectural.py`, `electrical.py`, `mechanical.py`, `plumbing.py`, plus legacy selection layers in `templates/prompt_templates.py` and `templates/prompt_types.py`.
- **Runtime usage**: `services/ai_service.py` uses the registry to get a system message; also runs an optional second AI call (`repair_metadata`) to patch `DRAWING_METADATA` using `titleblock_text` when available.
- **Tests**: Some tests reference specialized prompts and legacy selection APIs and will need removal/replacement.

### Metadata Repair — What it does and whether you need it
- **What it does**: A small second-pass AI call on `titleblock_text` to fill/overwrite `DRAWING_METADATA` fields like sheet_number, sheet_title, revision, project.
- **When to keep**: If you want consistent, filterable fields without maintaining regex rules across varied projects, keep it as a fallback (only if fields are missing/low-confidence).
- **When to remove**: If you reliably derive those fields deterministically (filename/path + regex on title block), you can remove it or make it optional.

### Azure AI Search Alignment
- **Schema**: Minimal structured fields (`id`, `project`, `sheet_number`, `sheet_title`, `discipline`, `drawing_type`, `level`, `revision`, `source_file`), full `content` indexed, full `raw_json` stored (not indexed), embeddings in `vector`.
- **Approach**: Simple “extract everything” GENERAL prompt; no schema enforcement.
- **Integration**: Use `select_fields` for lightweight retrieval; rely on `content` for semantic/keyword queries; `source_file` for PDF retrieval.

### PRD Deliverable (Created)
- Added `PRD-prompt-simplification.md` at repo root outlining:
  - Goals, non-goals, current state, target architecture.
  - Proposed removals (specialized prompts, registry/decorators, legacy APIs).
  - Service updates to import `GENERAL_PROMPT` (and optional `METADATA_REPAIR_PROMPT`) directly.
  - Tests/docs updates, risks/mitigations, rollout and commit plan.
  - Optional config gating for metadata repair.

### Proposed Refactor (High level)
- **Keep**: `templates/prompts/general.py` exporting `GENERAL_PROMPT`; optionally `templates/prompts/metadata.py` exporting `METADATA_REPAIR_PROMPT`.
- **Remove**: Specialized prompt modules, `prompt_registry`, `prompt_templates`, `prompt_types`, and unused room templates if unreferenced.
- **Update**: `services/ai_service.py` to import constants directly; remove legacy references; slim tests to general-prompt smoke tests; update docs.

### Commit Plan (semantic prefixes)
- feat: use GENERAL_PROMPT constant in ai_service
- refactor: remove prompt registry and specialized prompt modules
- refactor: delete prompt_templates and prompt_types
- test: remove specialized prompt tests; add general prompt smoke test
- docs: update README and dev-handover
- chore: remove unused room templates (if confirmed unused)

### File Created
- `PRD-prompt-simplification.md` (root) with full details, scope, and acceptance criteria.

If you want, I can start a new branch and implement the edits per the PRD, leaving metadata repair as a configurable fallback.