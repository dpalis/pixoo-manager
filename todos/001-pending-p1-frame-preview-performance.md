# Frame Preview Performance Critical Issue

## Status: pending
## Priority: P1 (Critical - Blocks Merge)
## Issue ID: 001
## Tags: performance, code-review, pr-117

---

## Problem Statement

The frame preview functionality for GIF editing creates severe I/O and CPU bottlenecks. Each slider movement triggers an HTTP request that opens the GIF file, performs sequential seek (O(n) complexity), converts to PNG, and sends response.

**Why it matters:** Can easily overload the server and cause noticeable UI lag during normal usage.

---

## Findings

### From performance-oracle agent:

1. **N+1 File Reads** (`app.js:1428-1431`):
   - `showFramePreview()` called on EVERY slider input event
   - Each call makes HTTP request to `/api/gif/frame/{id}/{num}`
   - No debounce implemented

2. **O(n) Seek per Frame** (`gif_converter.py:145-170`):
   - `Image.seek()` in PIL GIFs is sequential - must decode all previous frames
   - For frame 100, decodes frames 0-99 first
   - GIF file opened fresh for each request

3. **Cache Busting Defeats Browser Cache** (`app.js:1431`):
   ```javascript
   this.currentFramePreviewUrl = `/api/gif/frame/${this.uploadId}/${frameIndex}?t=${Date.now()}`;
   ```
   - `?t=${Date.now()}` ensures every request bypasses cache
   - Even same frame re-requested repeatedly

**Estimated impact:**
- 50+ requests/second when dragging slider fast
- 50-200ms per frame request
- CPU blocked processing parallel frame requests

---

## Proposed Solutions

### Option A: Add Debounce to Slider (Recommended)
- **Pros:** Quick fix, immediate improvement, low risk
- **Cons:** Slight delay in preview responsiveness
- **Effort:** Small (10 lines)
- **Risk:** Low

```javascript
// Add 200ms debounce
validateStartFrame: Alpine.debounce(function() {
    // existing logic
    this.showFramePreview(this.startFrame);
}, 200)
```

### Option B: Remove Cache Busting
- **Pros:** Browser caches frames, reduces server load
- **Cons:** May show stale frame if file changes (unlikely in this flow)
- **Effort:** Trivial (1 line)
- **Risk:** Low

### Option C: Server-Side Frame Cache (Future)
- **Pros:** Optimal performance, frames pre-extracted
- **Cons:** More complex, memory usage
- **Effort:** Medium
- **Risk:** Medium

---

## Recommended Action

Implement Option A + B before merge. Option C can be future enhancement.

---

## Technical Details

**Affected Files:**
- `app/static/js/app.js` (lines 1408-1431)
- `app/services/gif_converter.py` (lines 145-170)
- `app/routers/gif_upload.py` (lines 454-489)

**Acceptance Criteria:**
- [ ] Slider has 200-300ms debounce on frame preview
- [ ] Cache-busting query param removed from frame URL
- [ ] Manual test: drag slider rapidly, observe no lag

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | From PR #117 code review |

---

## Resources

- PR #117: https://github.com/dpalis/Pixoo-64/pull/117
- Performance oracle agent report
