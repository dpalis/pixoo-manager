# MoviePy gc.collect() Missing After VideoFileClip

## Status: pending
## Priority: P2 (Important)
## Issue ID: 009
## Tags: memory-leak, moviepy, pattern-violation, code-review, pr-117

---

## Problem Statement

The `video_converter.py` uses `VideoFileClip` but does NOT call `gc.collect()` after the context manager exits. This violates the documented pattern in `compounding-knowledge/patterns/moviepy-resource-leak.md`.

**Why it matters:** Memory leaks and locked temp files in long-running server.

---

## Findings

### From compounding-knowledge pattern:

The `moviepy-resource-leak.md` pattern explicitly states:

> MoviePy internamente usa FFmpeg via subprocess e mantém referências a frames em memória. O context manager (`__exit__`) chama `.close()`, mas:
> 1. O garbage collector do Python não coleta imediatamente
> 2. Subprocessos FFmpeg podem permanecer ativos
> 3. Buffers internos não são liberados até próximo ciclo de GC

**Required pattern:**
```python
try:
    with VideoFileClip(str(path)) as clip:
        # operations
finally:
    gc.collect()  # CRITICAL: Force garbage collection
```

**Current code in `video_converter.py:208-299`:**
```python
try:
    with VideoFileClip(str(path)) as clip:
        # ... processing ...
    # MISSING: gc.collect()
except VideoTooLongError:
    raise
```

---

## Proposed Solutions

### Option A: Add gc.collect() in finally block (Recommended)
- **Pros:** Follows established pattern, fixes memory leak
- **Cons:** None
- **Effort:** Trivial
- **Risk:** None

```python
import gc

def convert_video_to_gif(...):
    try:
        with VideoFileClip(str(path)) as clip:
            # existing code
    except VideoTooLongError:
        raise
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"Erro ao converter video: {e}")
    finally:
        gc.collect()  # Always cleanup MoviePy resources
```

---

## Recommended Action

Fix in this PR. This is a known pattern from previous debugging.

---

## Technical Details

**Affected Files:**
- `app/services/video_converter.py` (lines 208-299)
- Also check: `get_video_info()` and `extract_video_segment()`

**Acceptance Criteria:**
- [ ] `import gc` at top of file
- [ ] `gc.collect()` in finally block of `convert_video_to_gif()`
- [ ] Same for `get_video_info()` and `extract_video_segment()`

---

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-29 | Finding created | Pattern violation from compounding-knowledge |

---

## Resources

- Pattern: `~/Coding/compounding-knowledge/patterns/moviepy-resource-leak.md`
- Original discovery: PR #108
