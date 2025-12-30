# No Tests for New Crop Functionality

## Status: pending
## Priority: P3 (Nice-to-Have)
## Issue ID: 010
## Tags: testing, code-quality, code-review, pr-117

---

## Problem Statement

PR #117 adds significant new functionality (crop for GIFs and videos) with +782 lines of code, but includes NO tests. The `tests/` directory was not modified.

**Why it matters:** From `compounding-knowledge/principles/architecture-five-concepts.md`:
> "Projeto >1000 linhas tem testes para funcionalidades críticas"

The project is >1000 lines and these are critical features.

---

## Findings

### From compounding-knowledge principles:

The principle states:
- ✅ BOM: Projeto >1000 linhas tem testes para funcionalidades críticas
- ❌ RUIM: Projeto >2000 linhas sem testes, mudanças quebram sem avisar

**Current state:**
- Project has existing tests in `tests/` directory
- PR #117 adds 4 new endpoints and 3 new service functions
- Zero tests added for new functionality

### New functionality needing tests:

**Endpoints:**
- `POST /api/gif/upload-raw`
- `GET /api/gif/first-frame/{upload_id}`
- `GET /api/gif/frame/{upload_id}/{frame_num}`
- `POST /api/gif/crop-and-convert`

**Service functions:**
- `get_first_frame()`
- `get_frame_by_index()`
- `crop_frame()`
- `convert_gif()` with crop parameters
- `convert_video_to_gif()` with crop parameters

---

## Proposed Solutions

### Option A: Add Tests in Follow-up PR (Recommended)
- **Pros:** Doesn't block this PR, can be done in parallel
- **Cons:** Temporary gap in coverage
- **Effort:** Medium
- **Risk:** Low

### Option B: Add Minimal Tests in This PR
- **Pros:** Immediate coverage
- **Cons:** Delays merge
- **Effort:** Medium
- **Risk:** Low

---

## Recommended Action

Create follow-up issue/PR for tests. Not blocking for merge.

---

## Technical Details

**Affected Files:**
- `tests/test_gif_upload.py` - needs new test cases
- `tests/test_gif_converter.py` - needs new test cases
- `tests/test_video_converter.py` - needs crop test cases

**Minimum Test Cases:**
- [ ] Upload raw GIF returns first frame URL
- [ ] Get frame by index returns correct frame
- [ ] Crop with valid coordinates succeeds
- [ ] Crop with invalid coordinates returns 400
- [ ] Video crop applies correctly

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From compounding-knowledge principles |

---

## Resources

- Principle: `~/Coding/compounding-knowledge/principles/architecture-five-concepts.md`
- Existing tests: `tests/test_gif_upload.py`, `tests/test_gif_converter.py`
