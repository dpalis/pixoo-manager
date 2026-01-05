#!/bin/bash
#
# Build styled DMG for Pixoo Manager
#
# Creates a professional DMG installer with:
# - Custom dark background with arrow
# - Proper icon positioning
# - Applications folder link
#
# Prerequisites:
#   - py2app installed in .venv
#   - Python 3.10+
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
DMG_TEMP="${DMG_NAME}-temp.dmg"
DMG_FINAL="${DMG_NAME}.dmg"
BUILD_DIR="build"
DIST_DIR="dist"
DMG_DIR="dmg_contents"
BACKGROUND_IMG="resources/dmg/background.png"

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

# Step 1: Clean previous builds
echo -e "\n${YELLOW}Step 1: Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR" "$DMG_DIR"
rm -f "${DMG_NAME}.dmg" "${DMG_TEMP}"
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

# Step 5: Create temporary DMG contents
echo -e "\n${YELLOW}Step 5: Creating DMG contents...${NC}"
mkdir -p "$DMG_DIR/.background"
cp -R "$APP_PATH" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"
cp "$BACKGROUND_IMG" "$DMG_DIR/.background/background.png"
echo "Done."

# Step 6: Calculate DMG size
echo -e "\n${YELLOW}Step 6: Calculating DMG size...${NC}"
SIZE=$(du -sm "$DMG_DIR" | cut -f1)
SIZE=$((SIZE + 20))  # Add 20MB buffer
echo "Size: ${SIZE}MB"

# Step 7: Create temporary read-write DMG
echo -e "\n${YELLOW}Step 7: Creating temporary DMG...${NC}"
hdiutil create -srcfolder "$DMG_DIR" -volname "$VOLUME_NAME" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW -size ${SIZE}m "$DMG_TEMP"
echo "Done."

# Step 8: Mount and style the DMG
echo -e "\n${YELLOW}Step 8: Styling DMG window...${NC}"
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "$DMG_TEMP" | \
    grep -E '^/dev/' | sed 1q | awk '{print $1}')
MOUNT_POINT="/Volumes/$VOLUME_NAME"

echo "Mounted at: $MOUNT_POINT"
sleep 2  # Wait for mount

# Apply Finder view settings via AppleScript
echo "Applying Finder settings..."
osascript <<EOF
tell application "Finder"
    tell disk "$VOLUME_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {100, 100, $((100 + WINDOW_WIDTH)), $((100 + WINDOW_HEIGHT))}

        set theViewOptions to icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to $ICON_SIZE
        set background picture of theViewOptions to file ".background:background.png"

        set position of item "$APP_NAME.app" of container window to {$APP_ICON_X, $APP_ICON_Y}
        set position of item "Applications" of container window to {$APPS_ICON_X, $APPS_ICON_Y}

        close
        open

        update without registering applications
        delay 2
    end tell
end tell
EOF

# Sync and wait
sync
sleep 3

# Unmount
echo "Unmounting..."
hdiutil detach "$DEVICE" -quiet
echo "Done."

# Step 9: Convert to compressed final DMG
echo -e "\n${YELLOW}Step 9: Creating final DMG...${NC}"
hdiutil convert "$DMG_TEMP" -format UDZO -imagekey zlib-level=9 -o "$DMG_FINAL"
rm -f "$DMG_TEMP"
echo "Done."

# Step 10: Cleanup
echo -e "\n${YELLOW}Step 10: Cleaning up...${NC}"
rm -rf "$DMG_DIR"
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
