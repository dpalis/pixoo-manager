---
id: "023"
title: "Phase 6 (packaging) not implemented"
status: pending
priority: p3
category: feature
source: git-history-analyzer-review
created: 2025-12-12
---

# Phase 6 Packaging Not Implemented

## Problem

Per CLAUDE.md, Phase 6 was planned for `.app` packaging but the feature branch was never created. The application can only run via `python -m app.main`.

## Reference

From CLAUDE.md:
```markdown
### Branches planejadas
...
6. `feature/phase6-packaging` - Empacotamento .app
```

## Current State

- No packaging configuration (setup.py, pyproject.toml for packaging)
- No PyInstaller/py2app spec files
- Users must have Python environment configured

## Recommended Implementation

### Option 1: PyInstaller (cross-platform)

```python
# pixoo-manager.spec
a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/templates', 'app/templates'),
        ('app/static', 'app/static'),
    ],
    hiddenimports=['uvicorn.logging', 'uvicorn.protocols.http'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, ...)
app = BUNDLE(exe, name='Pixoo Manager.app', ...)
```

### Option 2: py2app (Mac-specific)

```python
# setup.py
from setuptools import setup

APP = ['app/main.py']
DATA_FILES = [('templates', ['app/templates/*']), ...]
OPTIONS = {
    'argv_emulation': True,
    'packages': ['uvicorn', 'fastapi', 'PIL', 'moviepy'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

## Impact

- Severity: Nice-to-have (usability feature)
- Effect: Easier distribution to non-technical users
