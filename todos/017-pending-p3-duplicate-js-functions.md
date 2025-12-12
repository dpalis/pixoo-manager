---
id: "017"
title: "Duplicate JavaScript functions in app.js"
status: pending
priority: p3
category: code-quality
source: code-simplicity-review
created: 2025-12-12
---

# Duplicate JavaScript Functions in app.js

## Problem

`app.js` (755 lines) has duplicated code:
- Time formatting function duplicated 3 times (~20 lines each)
- Message handling duplicated 3 times (~15 lines each)
- Total: ~80 lines of duplication

## Location

- `app/static/js/app.js`

## Example Duplication

```javascript
// In gifUpload()
formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// In mediaUpload() - identical
formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// In youtubeDownload() - identical
formatTime(seconds) { ... }
```

## Recommended Fix

Extract to shared utility object:

```javascript
// Shared utilities at top of app.js
const utils = {
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        const ms = Math.floor((seconds % 1) * 100);
        return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
    },

    showMessage(component, text, type = 'info') {
        component.message = text;
        component.messageType = type;
        setTimeout(() => component.message = '', 5000);
    }
};

// Usage in components
function gifUpload() {
    return {
        formatTime: utils.formatTime,
        showMessage(text, type) { utils.showMessage(this, text, type); },
        ...
    };
}
```

## Impact

- Severity: Nice-to-have
- Effect: Easier maintenance, consistent behavior
- Lines saved: ~60
