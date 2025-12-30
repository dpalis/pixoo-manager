# Orphan Uploads After Crop Operation

## Status: pending
## Priority: P1 (Critical - Blocks Merge)
## Issue ID: 003
## Tags: data-integrity, resource-leak, code-review, pr-117

---

## Problem Statement

When `crop-and-convert` executes successfully, the original raw upload is not cleaned up. The file remains on disk for 1 hour (TTL), wasting disk space.

**Why it matters:** With repeated crop operations on large GIFs, disk space can be exhausted.

---

## Findings

### From data-integrity-guardian agent:

**Location:** `app/routers/gif_upload.py` lines 519-542

```python
gif_uploads.set(new_upload_id, {
    "path": output_path,
    "metadata": new_metadata,
    "converted": True,
    "cropped_from": request.id  # Reference exists, but original not cleaned
})
# MISSING: gif_uploads.delete(request.id)
```

**Corruption Scenario:**
1. User uploads 50MB GIF
2. User applies crop
3. Original GIF (50MB) remains on disk for 1 hour
4. If user repeats 10x, 500MB of orphan files

### Related Issues:
- Conversion failure also leaves raw upload orphaned (lines 556-559)
- User abandoning workflow (clicking X) leaves files orphaned
- `clearFile()` in JS doesn't notify server to delete

---

## Proposed Solutions

### Option A: Delete Original After Successful Crop (Recommended)
- **Pros:** Immediate disk savings, simple fix
- **Cons:** User can't "undo" to original (but this isn't a feature anyway)
- **Effort:** Trivial (1 line)
- **Risk:** Low

```python
# After creating new upload successfully:
gif_uploads.delete(request.id)  # Cleans file and entry
```

### Option B: Add Client-Side Cleanup on Abandon
- **Pros:** Cleans up when user cancels/changes file
- **Cons:** More complex, needs DELETE endpoint call
- **Effort:** Small
- **Risk:** Low

### Option C: Shorter TTL for Raw Uploads
- **Pros:** Reduces window for orphans
- **Cons:** May be too aggressive, user might step away
- **Effort:** Trivial
- **Risk:** Medium

---

## Recommended Action

Implement Option A before merge. Consider Option B as follow-up.

---

## Technical Details

**Affected Files:**
- `app/routers/gif_upload.py` (line ~542)

**Acceptance Criteria:**
- [ ] After successful crop-and-convert, original upload is deleted
- [ ] Verify temp file removed from disk
- [ ] Test: upload, crop, check disk - original file should be gone

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
