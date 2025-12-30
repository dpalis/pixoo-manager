# Video Crop Coordinates Not Validated

## Status: pending
## Priority: P1 (Critical - Blocks Merge)
## Issue ID: 002
## Tags: security, data-integrity, code-review, pr-117

---

## Problem Statement

Video crop coordinates are passed directly to MoviePy without server-side validation. Unlike GIF which validates in the router (lines 507-517), video has no such protection. This can cause runtime errors or corrupted output.

**Why it matters:** Invalid crop coordinates can cause MoviePy exceptions or produce unexpected results.

---

## Findings

### From security-sentinel agent:
- `ConvertRequest` model accepts optional crop coordinates without validation
- No bounds checking against video dimensions

### From architecture-strategist agent:
- Inconsistency: GIF validates crop, video doesn't
- Same validation logic should apply to both

### From data-integrity-guardian agent:
- MoviePy may throw exception or produce incorrect result
- Partial file may be left on disk if conversion fails mid-way

**Code location:** `app/routers/media_upload.py` lines 79-88, 359-368

```python
class ConvertRequest(BaseModel):
    id: str
    start: float
    end: float
    # No validation for these:
    crop_x: int | None = None
    crop_y: int | None = None
    crop_width: int | None = None
    crop_height: int | None = None
```

---

## Proposed Solutions

### Option A: Add Validation in Router (Recommended)
- **Pros:** Consistent with GIF implementation, early failure
- **Cons:** Slight code duplication (but can be extracted later)
- **Effort:** Small
- **Risk:** Low

```python
# In convert_video or convert_video_sync, before calling service:
if request.crop_x is not None:
    metadata = upload["metadata"]
    if request.crop_x < 0 or request.crop_y < 0:
        raise HTTPException(status_code=400, detail="Coordenadas nao podem ser negativas")
    if request.crop_x + request.crop_width > metadata.width:
        raise HTTPException(status_code=400, detail="Crop excede largura do video")
    if request.crop_y + request.crop_height > metadata.height:
        raise HTTPException(status_code=400, detail="Crop excede altura do video")
```

### Option B: Extract Shared Validation Function
- **Pros:** DRY, consistent validation for GIF and video
- **Cons:** More refactoring
- **Effort:** Medium
- **Risk:** Low

---

## Recommended Action

Implement Option A before merge. Option B can be refactoring follow-up.

---

## Technical Details

**Affected Files:**
- `app/routers/media_upload.py`

**Acceptance Criteria:**
- [ ] Crop coordinates validated against video dimensions
- [ ] Returns 400 error for out-of-bounds values
- [ ] Test: send crop coordinates exceeding video size, verify 400 response

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
- Reference: GIF validation at `gif_upload.py:507-517`
