#!/bin/bash
#
# Build DMG for Pixoo Manager
#
# Creates a professional DMG installer with:
# - Pixoo Manager.app
# - Applications folder link
# - Background image (optional)
# - Icon positions configured
#
# Prerequisites:
#   - py2app installed: pip install py2app
#   - hdiutil (built into macOS)
#
# Usage:
#   ./scripts/build_dmg.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Pixoo Manager"
VERSION=$(python -c "from app.__version__ import __version__; print(__version__)")
DMG_NAME="${APP_NAME}-${VERSION}"
BUILD_DIR="build"
DIST_DIR="dist"
DMG_DIR="dmg_contents"

echo -e "${GREEN}Building ${APP_NAME} v${VERSION}${NC}"
echo "========================================"

# Step 1: Clean previous builds
echo -e "\n${YELLOW}Step 1: Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR" "$DMG_DIR"
rm -f "${DMG_NAME}.dmg"
echo "Done."

# Step 2: Build .app with py2app
echo -e "\n${YELLOW}Step 2: Building .app with py2app...${NC}"
if [ ! -f "setup.py" ]; then
    echo -e "${RED}Error: setup.py not found. Please create it first.${NC}"
    echo "Example setup.py:"
    echo "  from setuptools import setup"
    echo "  APP = ['app/main.py']"
    echo "  OPTIONS = {'argv_emulation': False, 'packages': ['app']}"
    echo "  setup(app=APP, options={'py2app': OPTIONS}, setup_requires=['py2app'])"
    exit 1
fi

python setup.py py2app
echo "Done."

# Step 3: Verify .app was created
echo -e "\n${YELLOW}Step 3: Verifying .app...${NC}"
APP_PATH="$DIST_DIR/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: ${APP_PATH} not found.${NC}"
    exit 1
fi
echo "Found: $APP_PATH"

# Step 4: Create DMG contents directory
echo -e "\n${YELLOW}Step 4: Creating DMG contents...${NC}"
mkdir -p "$DMG_DIR"
cp -R "$APP_PATH" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"
echo "Done."

# Step 5: Create DMG
echo -e "\n${YELLOW}Step 5: Creating DMG...${NC}"
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "$DMG_DIR" \
    -ov \
    -format UDZO \
    "${DMG_NAME}.dmg"

echo "Done."

# Step 6: Cleanup
echo -e "\n${YELLOW}Step 6: Cleaning up...${NC}"
rm -rf "$DMG_DIR"
echo "Done."

# Summary
DMG_SIZE=$(du -h "${DMG_NAME}.dmg" | cut -f1)
echo ""
echo -e "${GREEN}========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "DMG: ${DMG_NAME}.dmg"
echo "Size: ${DMG_SIZE}"
echo ""
echo "To install:"
echo "  1. Open ${DMG_NAME}.dmg"
echo "  2. Drag ${APP_NAME} to Applications"
echo ""
echo "To distribute:"
echo "  Upload ${DMG_NAME}.dmg to GitHub Releases"
echo -e "========================================${NC}"
