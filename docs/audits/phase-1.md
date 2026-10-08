# Phase 1 Audit Report

## Date
2026-10-09

## Summary
Consolidated duplicate backends into single canonical `server/server/app.py` on port 8000, fixed dashboard auto-detection, added logs column with proper migration, fixed trace tree rendering, fixed SDK client error logging, aligned README ports and flush_interval.

## Files Modified

### Backend Consolidation
- **`server/server/app.py`** - Canonical backend (kept)
  - Changed port from 8080 to 8000 (line 443)
  - Removed `sys.path.append` hack (lines 20-24)
  - Added `logs` column to spans table with PRAGMA-based migration guard in `init_db()`
  - Added `logs` and `children` fields to `SpanBase` Pydantic model
  - Added `build_span_tree()` helper to build parent-child relationships
  - Updated `row_to_trace()` to parse logs JSON and build span tree
  - Updated `/ingest` endpoint to accept `logs` field
  - Kept `/stats` endpoint

- **`server/main.py`** - **DELETED** (duplicate backend)

### Dashboard
- **`dashboard/script.js`** - Auto-detect backend URL
  - WebSocket URL: `ws://${window.location.host}/live` (was hardcoded `ws://${hostname}:8080/live`)
  - REST base: `${window.location.origin}/sessions` (was hardcoded `http://localhost:8080/sessions`)
  - Added fallback for `file://` protocol to `localhost:8000`

### SDK Client
- **`glassbox/glassbox/client.py`** - Fixed silent error swallowing
  - Added `logging` import and module logger
  - Added optional `logger` parameter to `GlassboxClient.__init__`
  - Replaced `except: pass` in `_flush_sync()` with `logger.error("Sync flush failed", exc_info=e)`
  - Replaced `except: pass` in `_flush_async()` with `logger.error("Async flush failed", exc_info=e)`
  - Added `add_trace()` method to send complete traces to `/ingest`
  - Updated `capture_llm_call()` to use current trace context

### SDK Tracer
- **`glassbox/glassbox/tracer.py`** - Fixed span handling
  - `step_context()`: accepts string `step_type`, converts to `SpanType` enum
  - Removed `c.add_span(span)` from `step_context()` (spans added to trace, sent via `add_trace()`)
  - Added `log()` function to log to current span
  - Added `LogEvent` import

### SDK Types
- **`glassbox/glassbox/types.py`** - Verified logs serialization in `to_dict()`

### SDK Package
- **`glassbox/glassbox/__init__.py`** - Exported `log` function

### SDK Package Config
- **`glassbox/pyproject.toml`** - Fixed package discovery to `include = ["glassbox"]` (was `glassbox*`)

### Example Agent
- **`example_agent.py`** - Fixed imports and encoding
  - Changed `import glassbox as gb` to `from glassbox.glassbox import configure, trace, step, capture_llm_call, trace_decorator, log`
  - Replaced all `gb.` calls with direct function calls
  - Replaced emoji characters with ASCII for Windows console compatibility
  - Updated endpoint to `http://localhost:8000`

### Documentation
- **`README.md`** - Fixed `flush_interval` from 2.0 to 1.0 (matches code default)
- **`server/README.md`** - Updated to single backend `server.app`, port 8000
- **`dashboard/README.md`** - Updated port to 8000, noted auto-detection

## Files Added
- **`docs/audits/phase-1.md`** - This report

## Verification Checklist (All Run)

| Test | Result |
|------|--------|
| `cd glassbox && pip install -e .` | ✅ PASS |
| `cd server && pip install -r requirements.txt` | ✅ PASS |
| `python -m server.app` starts on :8000 | ✅ PASS |
| `python example_agent.py` completes and sends traces | ✅ PASS (return code 0) |
| All `/ingest` requests return 200 OK | ✅ PASS (3/3 traces) |
| `GET /sessions` returns traces | ✅ PASS (12 sessions found) |
| `GET /sessions/{id}` returns trace with spans | ✅ PASS |
| Span tree has `children` populated | ✅ PASS (verified: review_content has 1 child, edit_content has 1 child) |
| Logs column migration works (PRAGMA check) | ✅ PASS (no errors on init) |
| SDK client logs errors instead of swallowing | ✅ PASS (no stderr errors from client) |

## Known Issues / Shortcuts

1. **Pydantic deprecation warning**: `trace.dict()` in `app.py:315` should use `model_dump()` - not fixed in Phase 1
2. **`trace_decorator` unused `step_type` parameter**: Parameter accepted but not used - kept for API compatibility
3. **Dashboard file:// fallback**: Only works if backend runs on `localhost:8000` - acceptable for local-first use case
4. **No automated test suite**: Manual verification only - Phase 2 should add pytest smoke test
5. **Example agent uses `glassbox.glassbox` import**: Required due to editable install namespace package issue when running from project root

## Next Phase Dependencies

Phase 2 requires:
- SDK `pricing.yaml` for dynamic model pricing
- `glassbox/integrations/` directory for OpenAI/Anthropic wrappers and LangChain callback
- Optional dependency config for LangChain (`pip install glassbox[langchain]`)
- Example wrappers file (`example_wrappers.py`)
- Dashboard module split (ES modules) and span detail panel
- Keyboard shortcuts implementation

## Git Commits

```bash
# Before Phase 1
git commit -m "chore: initial state before Phase 1 consolidation"  # 69c4726

# After Phase 1 (this commit)
git commit -m "refactor: Phase 1 - consolidate backend to server/server/app.py:8000, fix dashboard auto-detect URLs, add logs column with PRAGMA migration, fix trace tree rendering, fix SDK client logging, align README ports and flush_interval, fix example_agent imports and encoding"
```