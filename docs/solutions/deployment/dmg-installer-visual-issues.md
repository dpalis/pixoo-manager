---
title: Fix DMG Installer Visual Issues on macOS
tags:
  - macos
  - packaging
  - dmg
  - create-dmg
  - finder
  - branding
  - color-theory
category: deployment
symptoms:
  - Applications folder icon not rendering in DMG window
  - Dark text labels invisible on dark background
  - Arrow color mismatched with brand identity
  - Unwanted border/outline around Applications symlink
root_cause: |
  1. macOS Tahoe bug where Finder fails to render alias icons
  2. Dark background causes Finder to render unreadable dark labels
  3. create-dmg --app-drop-link creates drop-target with visible border
modules_affected:
  - scripts/build_dmg.sh
  - scripts/create_dmg_background.py
difficulty: medium
time_to_fix: 2-3 hours
prevented_by:
  - Test DMG on target macOS versions before release
  - Use light backgrounds for Finder compatibility
  - Extract real system icons instead of drawing custom ones
---

# Fix DMG Installer Visual Issues on macOS

## Problem

The Pixoo Manager DMG installer had multiple visual issues:

1. **Applications icon invisible** - macOS Tahoe bug prevents alias icon rendering
2. **Labels unreadable** - Dark background + Finder's dark labels = invisible text
3. **Generic arrow** - Gray arrow didn't match brand colors (cyan/magenta)
4. **Border around icon** - `--app-drop-link` adds unwanted dashed border

## Root Cause

### 1. macOS Tahoe Icon Bug
The Finder in macOS Tahoe (26.x) fails to render icons for aliases/symlinks in DMG windows. This is a known bug with no fix from Apple.

### 2. Finder Label Color Logic
Finder automatically chooses label color based on background brightness:
- Dark background → Dark labels (unreadable on dark)
- Light background → Dark labels (readable)

### 3. create-dmg Drop Target
The `--app-drop-link` flag creates a "drop target" with a dashed border, which looks unprofessional.

## Solution

### 1. Light Background Color

```python
# create_dmg_background.py
BG_COLOR = (232, 237, 242)  # Light blue-gray #E8EDF2
```

**Why this color?**
- Harmonizes with cyan brand color (same color family, desaturated)
- Light enough for Finder to use dark, readable labels
- Professional, neutral appearance

### 2. Brand-Complementary Arrow

```python
ARROW_COLOR = (255, 107, 53)  # Neon orange #FF6B35
```

**Color theory:**
- Orange is complementary to cyan on the color wheel
- Creates visual contrast and draws attention
- Matches brand energy (vibrant, modern)

### 3. Extract Real macOS Icon

```bash
# Extract the real Applications folder icon from macOS
sips -s format png --resampleWidth 128 \
  /System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ApplicationsFolderIcon.icns \
  --out resources/dmg/applications_icon.png
```

Then embed in background:

```python
icon_path = script_dir.parent / "resources" / "dmg" / "applications_icon.png"
if icon_path.exists():
    apps_icon = Image.open(icon_path).convert("RGBA")
    icon_size = int(128 * scale)
    apps_icon = apps_icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    img.paste(apps_icon, (paste_x, paste_y), apps_icon)
```

### 4. Symlink Instead of Drop-Link

```bash
# build_dmg.sh - Create symlink manually
TEMP_APPS_LINK=$(mktemp -d)/Applications
ln -s /Applications "$TEMP_APPS_LINK"

DMG_ARGS=(
    # ... other args ...
    --add-file "Applications" "$TEMP_APPS_LINK" $APPS_ICON_X $APPS_ICON_Y
)
```

**Why?**
- `--add-file` with a symlink works like `--app-drop-link`
- No dashed border around the icon
- Same drag-and-drop functionality

## Prevention

1. **Test on target macOS** - Visual bugs vary by OS version
2. **Use light backgrounds** - Finder compatibility is better
3. **Use system icons** - Don't draw custom folder icons
4. **Avoid --app-drop-link** - Use symlink + --add-file instead

## Related

- [create-dmg GitHub](https://github.com/create-dmg/create-dmg)
- [macOS App Distribution Guide](../../../compounding-knowledge/patterns/macos-app-distribution.md)
- Issue: create-dmg returns exit code 2 for unsigned apps (expected, not an error)

## Files Changed

- `scripts/create_dmg_background.py` - Colors and icon embedding
- `scripts/build_dmg.sh` - Symlink approach
- `resources/dmg/applications_icon.png` - Extracted system icon
