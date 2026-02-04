#!/usr/bin/env python3
"""
Generate DMG background image for Pixoo Manager.

Uses the real macOS Applications folder icon extracted from the system.
"""

from PIL import Image, ImageDraw
from pathlib import Path

# DMG dimensions (standard)
WIDTH = 660
HEIGHT = 400

# Colors
BG_COLOR = (232, 237, 242)    # Light blue-gray #E8EDF2 - harmonizes with cyan
ARROW_COLOR = (255, 107, 53)  # Neon orange #FF6B35 - complementary to cyan


def draw_arrow(img, start_x, end_x, y, scale=1):
    """Draw arrow pointing right."""
    draw = ImageDraw.Draw(img)

    thickness = int(4 * scale)
    head_size = int(16 * scale)

    body_end = end_x - head_size
    draw.rectangle(
        [start_x, y - thickness // 2, body_end, y + thickness // 2],
        fill=ARROW_COLOR
    )

    draw.polygon(
        [
            (body_end, y - head_size // 2),
            (end_x, y),
            (body_end, y + head_size // 2),
        ],
        fill=ARROW_COLOR
    )

    return img


def create_dmg_background(scale=1):
    """Create DMG background with real macOS Applications icon."""
    w, h = WIDTH * scale, HEIGHT * scale

    img = Image.new('RGB', (w, h), BG_COLOR)

    # Icon positions
    left_icon_x = int(165 * scale)
    right_icon_x = int(495 * scale)
    icons_y = int(180 * scale)

    # Load real macOS Applications folder icon
    script_dir = Path(__file__).parent
    icon_path = script_dir.parent / "resources" / "dmg" / "applications_icon.png"

    if icon_path.exists():
        apps_icon = Image.open(icon_path).convert("RGBA")
        # Scale icon to match (128px at 1x)
        icon_size = int(128 * scale)
        apps_icon = apps_icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

        # Position (centered at right_icon_x, icons_y)
        paste_x = right_icon_x - icon_size // 2
        paste_y = icons_y - icon_size // 2

        # Paste with transparency
        img.paste(apps_icon, (paste_x, paste_y), apps_icon)

    # Arrow between icons
    arrow_start = left_icon_x + int(70 * scale)
    arrow_end = right_icon_x - int(70 * scale)
    img = draw_arrow(img, arrow_start, arrow_end, icons_y, scale)

    return img


def main():
    """Generate DMG background images."""
    import os

    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resources_dir = os.path.join(output_dir, "resources", "dmg")
    os.makedirs(resources_dir, exist_ok=True)

    print("Generating 1x background (660x400)...")
    bg_1x = create_dmg_background(scale=1)
    bg_1x_path = os.path.join(resources_dir, "background.png")
    bg_1x.save(bg_1x_path, "PNG", dpi=(72, 72))
    print(f"  Saved: {bg_1x_path}")

    print("Generating 2x background (1320x800)...")
    bg_2x = create_dmg_background(scale=2)
    bg_2x_path = os.path.join(resources_dir, "background@2x.png")
    bg_2x.save(bg_2x_path, "PNG", dpi=(144, 144))
    print(f"  Saved: {bg_2x_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
