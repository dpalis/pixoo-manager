#!/bin/bash
#
# Smoke test para o .app bundled
#
# Verifica que o app abre, inicia o servidor, e responde HTTP.
# IMPORTANTE: Usa o executável do BUNDLE, não o Python do sistema.
#
# Usage:
#   ./scripts/smoke_test.sh
#
# Prerequisites:
#   - Build completo (python setup.py py2app)
#   - dist/Pixoo.app existente
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_NAME="Pixoo"
APP_PATH="dist/${APP_NAME}.app/Contents/MacOS/${APP_NAME}"
TIMEOUT=15
PORT=8000
PID=""

cleanup() {
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        wait "$PID" 2>/dev/null
    fi
}
trap cleanup EXIT

echo -e "${GREEN}=== Smoke Test: ${APP_NAME}.app ===${NC}"
echo ""

# 1. Verifica que o bundle existe
echo -n "1. Bundle exists... "
if [ ! -f "$APP_PATH" ]; then
    echo -e "${RED}FAIL${NC}"
    echo "   Bundle not found at $APP_PATH"
    echo "   Run 'python setup.py py2app' first."
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# 2. Verifica que ffmpeg bundled é executável (se existir)
echo -n "2. ffmpeg permissions... "
FFMPEG="dist/${APP_NAME}.app/Contents/Resources/bin/ffmpeg"
if [ -f "$FFMPEG" ]; then
    if [ ! -x "$FFMPEG" ]; then
        echo -e "${RED}FAIL${NC}"
        echo "   ffmpeg exists but is not executable: $FFMPEG"
        exit 1
    fi
    echo -e "${GREEN}OK (present + executable)${NC}"
else
    echo -e "${YELLOW}SKIP (not bundled)${NC}"
fi

# 3. Lança o app em background com env headless
echo -n "3. Starting app (headless)... "
PIXOO_HEADLESS=true "$APP_PATH" &
PID=$!
sleep "$TIMEOUT"

# Verifica que o processo ainda está rodando
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}FAIL${NC}"
    echo "   App crashed during startup."
    CRASH_LOG="$HOME/.pixoo_manager/crash.log"
    if [ -f "$CRASH_LOG" ]; then
        echo ""
        echo "--- Crash Log ---"
        cat "$CRASH_LOG"
    fi
    exit 1
fi
echo -e "${GREEN}OK (PID: $PID)${NC}"

# 4. Verifica que o servidor responde HTTP
echo -n "4. HTTP response... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}OK (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "   Expected HTTP 200 or 302, got $HTTP_CODE"
    CRASH_LOG="$HOME/.pixoo_manager/crash.log"
    if [ -f "$CRASH_LOG" ]; then
        echo ""
        echo "--- Crash Log ---"
        cat "$CRASH_LOG"
    fi
    exit 1
fi

# 5. Verifica referências a libs externas ao bundle
echo -n "5. External lib references... "
LEAKS=$(find "dist/${APP_NAME}.app" \( -name "*.so" -o -name "*.dylib" \) 2>/dev/null | \
    xargs otool -L 2>/dev/null | \
    grep -v "@executable_path" | grep -v "@rpath" | \
    grep -v "@loader_path" | grep -v "/usr/lib" | \
    grep -v "/System" | grep -v ":" | grep -v "^$" || true)

if [ -n "$LEAKS" ]; then
    echo -e "${YELLOW}WARNING${NC}"
    echo "   External library references found (may cause crash on other machines):"
    echo "$LEAKS" | head -10
else
    echo -e "${GREEN}OK (self-contained)${NC}"
fi

echo ""
echo -e "${GREEN}=== Smoke test passed ===${NC}"
