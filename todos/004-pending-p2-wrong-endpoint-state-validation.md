# Wrong Endpoint Used for GIF Raw Upload Validation

## Status: pending
## Priority: P2 (Important)
## Issue ID: 004
## Tags: bug, data-integrity, code-review, pr-117

---

## Problem Statement

When restoring state from sessionStorage, the code validates `gifRawUploadId` using an endpoint that doesn't exist for raw uploads (`/api/gif/preview/`). The correct endpoint is `/api/gif/first-frame/`.

**Why it matters:** State validation always fails for raw GIF uploads, causing loss of user work on page reload.

---

## Findings

### From data-integrity-guardian agent:

**Location:** `app/static/js/app.js` lines 703-711

```javascript
// Validate gifRawUploadId (GIF before crop)
if (state.gifRawUploadId && !state.uploadId) {
    const response = await fetch(`/api/gif/preview/${state.gifRawUploadId}`, { method: 'HEAD' });
    // PROBLEM: raw uploads don't have preview! Should use /api/gif/first-frame/
    if (!response.ok) {
        console.log('GIF raw upload expirado, limpando estado local');
        sessionStorage.removeItem('mediaUpload');
        return;
    }
}
```

**Impact:** Local state always considered invalid for raw GIFs, even when upload still exists on server.

---

## Proposed Solutions

### Option A: Use Correct Endpoint (Recommended)
- **Pros:** Simple fix, correct behavior
- **Cons:** None
- **Effort:** Trivial (1 line)
- **Risk:** Low

```javascript
const response = await fetch(`/api/gif/first-frame/${state.gifRawUploadId}`, { method: 'HEAD' });
```

---

## Recommended Action

Fix before merge.

---

## Technical Details

**Affected Files:**
- `app/static/js/app.js` (line 705)

**Acceptance Criteria:**
- [ ] Use `/api/gif/first-frame/{id}` for raw upload validation
- [ ] Test: upload GIF raw, reload page, state should be preserved

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
