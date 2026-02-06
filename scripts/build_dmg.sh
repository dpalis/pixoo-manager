#!/bin/bash
#
# Build styled DMG for Pixoo Manager
#
# Creates a professional DMG installer with:
# - Custom dark background with arrow
# - Proper icon positioning
# - Applications folder link
# - Volume icon
#
# Prerequisites:
#   - py2app installed in .venv
#   - Python 3.10+
#   - create-dmg (brew install create-dmg)
#
# Usage:
#   ./scripts/build_dmg.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Pixoo"
VOLUME_NAME="Pixoo Manager"
VERSION=$(source .venv/bin/activate && python3 -c "from app.__version__ import __version__; print(__version__)")
DMG_NAME="${APP_NAME}-${VERSION}"
DMG_FINAL="${DMG_NAME}.dmg"
BUILD_DIR="build"
DIST_DIR="dist"
BACKGROUND_IMG="resources/dmg/background.png"
VOLUME_ICON="resources/Pixoo.icns"

# DMG Window settings
WINDOW_WIDTH=660
WINDOW_HEIGHT=400
ICON_SIZE=128
APP_ICON_X=165
APP_ICON_Y=180
APPS_ICON_X=495
APPS_ICON_Y=180

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building ${APP_NAME} v${VERSION}${NC}"
echo -e "${GREEN}========================================${NC}"

# Step 0: Check for create-dmg
echo -e "\n${YELLOW}Step 0: Checking dependencies...${NC}"
if ! command -v create-dmg &> /dev/null; then
    echo -e "${RED}Error: create-dmg not found.${NC}"
    echo "Install with: brew install create-dmg"
    exit 1
fi
echo "create-dmg found."

# Step 1: Clean previous builds
echo -e "\n${YELLOW}Step 1: Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR"
rm -f "${DMG_FINAL}"
echo "Done."

# Step 2: Generate DMG background if needed
echo -e "\n${YELLOW}Step 2: Checking DMG background...${NC}"
if [ ! -f "$BACKGROUND_IMG" ]; then
    echo "Generating background images..."
    source .venv/bin/activate && python3 scripts/create_dmg_background.py
fi
echo "Done."

# Step 3: Build .app with py2app
echo -e "\n${YELLOW}Step 3: Building .app with py2app...${NC}"
source .venv/bin/activate && python3 setup.py py2app 2>&1 | grep -E "(copying|Done|error)" | tail -5
echo "Done."

# Step 4: Verify .app was created
echo -e "\n${YELLOW}Step 4: Verifying .app...${NC}"
APP_PATH="$DIST_DIR/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: ${APP_PATH} not found.${NC}"
    exit 1
fi
echo "Found: $APP_PATH"

# Garantir permissão de execução do ffmpeg bundled
FFMPEG_BUNDLED="$APP_PATH/Contents/Resources/bin/ffmpeg"
if [ -f "$FFMPEG_BUNDLED" ]; then
    chmod +x "$FFMPEG_BUNDLED"
    echo "ffmpeg permissions set: +x"
fi

# Step 5: Create DMG with create-dmg
echo -e "\n${YELLOW}Step 5: Creating styled DMG...${NC}"

# Remove existing DMG if present
rm -f "$DMG_FINAL"

# Create a temporary symlink to Applications
TEMP_APPS_LINK=$(mktemp -d)/Applications
ln -s /Applications "$TEMP_APPS_LINK"

# Build DMG arguments (using symlink instead of app-drop-link to avoid border)
DMG_ARGS=(
    --volname "$VOLUME_NAME"
    --background "$BACKGROUND_IMG"
    --window-pos 200 120
    --window-size $WINDOW_WIDTH $WINDOW_HEIGHT
    --icon-size $ICON_SIZE
    --icon "${APP_NAME}.app" $APP_ICON_X $APP_ICON_Y
    --hide-extension "${APP_NAME}.app"
    --add-file "Applications" "$TEMP_APPS_LINK" $APPS_ICON_X $APPS_ICON_Y
)

# Add volume icon if exists
if [ -f "$VOLUME_ICON" ]; then
    DMG_ARGS+=(--volicon "$VOLUME_ICON")
    echo "Using volume icon: $VOLUME_ICON"
fi

# Create the DMG
# Note: create-dmg returns error code 2 when codesigning fails (expected for unsigned apps)
# We check if the DMG was created successfully instead
set +e
create-dmg "${DMG_ARGS[@]}" "$DMG_FINAL" "$APP_PATH"
CREATE_DMG_EXIT=$?
set -e

if [ ! -f "$DMG_FINAL" ]; then
    echo -e "${RED}Error: DMG creation failed.${NC}"
    exit 1
fi

# Exit code 2 = codesigning failed (expected for unsigned apps)
if [ $CREATE_DMG_EXIT -ne 0 ] && [ $CREATE_DMG_EXIT -ne 2 ]; then
    echo -e "${YELLOW}Warning: create-dmg returned exit code $CREATE_DMG_EXIT${NC}"
fi

echo "Done."

# Step 6: Set DMG file icon (for Finder)
echo -e "\n${YELLOW}Step 6: Setting DMG file icon...${NC}"
if command -v fileicon &> /dev/null; then
    if [ -f "$VOLUME_ICON" ]; then
        fileicon set "$DMG_FINAL" "$VOLUME_ICON"
        echo "DMG icon set from $VOLUME_ICON"
    else
        echo "Warning: Volume icon not found, skipping DMG icon"
    fi
else
    echo "Warning: fileicon not installed. Install with: brew install fileicon"
fi
echo "Done."

# Summary
DMG_SIZE=$(du -h "$DMG_FINAL" | cut -f1)
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}DMG:${NC} $DMG_FINAL"
echo -e "${CYAN}Size:${NC} $DMG_SIZE"
echo ""
echo "To test:"
echo "  open $DMG_FINAL"
echo ""
echo "To distribute:"
echo "  Upload to GitHub Releases"
echo -e "${GREEN}========================================${NC}"
