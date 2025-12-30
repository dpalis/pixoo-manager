# Video Crop State Not Persisted to SessionStorage

## Status: pending
## Priority: P2 (Important)
## Issue ID: 006
## Tags: bug, data-integrity, code-review, pr-117

---

## Problem Statement

The `saveState()` function saves GIF-specific state but NOT video crop state (`videoCropApplied`, `videoCropData`). If user reloads page after applying video crop but before converting, crop coordinates are lost.

**Why it matters:** User loses work on page reload during video editing workflow.

---

## Findings

### From pattern-recognition-specialist and data-integrity-guardian agents:

**Location:** `app/static/js/app.js` lines 666-673

```javascript
// GIF-specific state saved:
gifRawUploadId: this.gifRawUploadId,
gifCropApplied: this.gifCropApplied,
// ...

// MISSING:
// videoCropApplied: this.videoCropApplied,
// videoCropData: this.videoCropData,
```

**Inconsistency:**
- GIF state: fully persisted
- Video state: partially persisted (crop data missing)

---

## Proposed Solutions

### Option A: Add Video Crop State to saveState() (Recommended)
- **Pros:** Consistent with GIF handling, preserves user work
- **Cons:** Slightly larger sessionStorage usage
- **Effort:** Trivial (2 lines)
- **Risk:** Low

```javascript
saveState() {
    const state = {
        // existing properties...
        // Add:
        videoCropApplied: this.videoCropApplied,
        videoCropData: this.videoCropData,
    };
    sessionStorage.setItem('mediaUpload', JSON.stringify(state));
}
```

---

## Recommended Action

Fix in this PR.

---

## Technical Details

**Affected Files:**
- `app/static/js/app.js` (saveState function)

**Acceptance Criteria:**
- [ ] videoCropApplied and videoCropData saved to sessionStorage
- [ ] Test: upload video, apply crop, reload, crop should be preserved

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
