---
id: "013"
title: "Missing test coverage for critical modules"
status: pending
priority: p2
category: testing
source: pattern-recognition-specialist-review
created: 2025-12-12
---

# Missing Test Coverage for Critical Modules

## Problem

Several critical modules have no test coverage:
- `video_converter.py` - 0% coverage
- `youtube_downloader.py` - 0% coverage
- `file_utils.py` - 0% coverage
- All routers - 0% coverage

Current coverage estimate: ~35% (46 tests, only 3 service files tested)

## Location

- `tests/` - missing test files

## Missing Test Files

```
tests/
├── test_gif_converter.py     # EXISTS
├── test_pixoo_connection.py  # EXISTS
├── test_pixoo_upload.py      # EXISTS
├── test_video_converter.py   # MISSING
├── test_youtube_downloader.py # MISSING
├── test_file_utils.py        # MISSING
├── test_routers/             # MISSING
│   ├── test_connection.py
│   ├── test_gif_upload.py
│   ├── test_media_upload.py
│   └── test_youtube.py
└── conftest.py               # EXISTS
```

## Priority Test Areas

1. **video_converter.py** - Complex logic, FFmpeg integration
2. **youtube_downloader.py** - External API, error handling
3. **file_utils.py** - File operations, cleanup logic
4. **Router integration tests** - API contract validation

## Recommended Fix

Add test files for missing modules:

```python
# tests/test_video_converter.py
import pytest
from app.services.video_converter import convert_video, extract_frames

class TestConvertVideo:
    def test_converts_mp4_to_gif(self, sample_video):
        result = convert_video(sample_video)
        assert result.suffix == '.gif'

    def test_respects_max_duration(self, long_video):
        with pytest.raises(ValueError, match="exceeds maximum"):
            convert_video(long_video, max_duration=10)
```

## Impact

- Severity: Important
- Effect: Bugs may reach production, refactoring is risky
