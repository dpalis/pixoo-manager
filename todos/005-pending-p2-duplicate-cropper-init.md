# Duplicate Cropper Initialization Code

## Status: pending
## Priority: P2 (Important)
## Issue ID: 005
## Tags: code-quality, duplication, code-review, pr-117

---

## Problem Statement

Three nearly identical Cropper initialization functions exist in `app.js`. All use the same Cropper options but differ only by the `$refs` target element.

**Why it matters:** Code duplication makes maintenance harder and increases risk of inconsistency.

---

## Findings

### From code-simplicity-reviewer and pattern-recognition-specialist agents:

**Locations:**
- `app.js:886-895` - `initCropper()` (image)
- `app.js:952-962` - `initGifCropper()` (GIF)
- `app.js:1064-1069` - inside `extractVideoFrame()` (video)

All use identical options:
```javascript
{
    aspectRatio: 1,
    viewMode: 1,
    autoCropArea: 0.8,
    responsive: true
}
```

**Estimated LOC reduction:** 20 lines

---

## Proposed Solutions

### Option A: Single Parameterized Function (Recommended)
- **Pros:** DRY, single source of truth for cropper config
- **Cons:** Minor refactoring
- **Effort:** Small
- **Risk:** Low

```javascript
const CROPPER_CONFIG = {
    aspectRatio: 1,
    viewMode: 1,
    autoCropArea: 0.8,
    responsive: true
};

initCropperFor(refName) {
    const image = this.$refs[refName];
    if (!image || this.cropper) return;
    this.cropper = new Cropper(image, CROPPER_CONFIG);
}
```

Then replace:
- `initCropper()` -> `initCropperFor('cropImage')`
- `initGifCropper()` -> `initCropperFor('gifCropImage')`
- Video: `initCropperFor('videoCropImage')`

---

## Recommended Action

Refactor in this PR or as immediate follow-up.

---

## Technical Details

**Affected Files:**
- `app/static/js/app.js`

**Acceptance Criteria:**
- [ ] Single function for cropper initialization
- [ ] All three use cases work correctly
- [ ] Test: image crop, GIF crop, video crop all function

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
