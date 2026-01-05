#!/usr/bin/env python3
"""
Generate professional DMG background image for Pixoo Manager.

Creates a 660x400 (and 1320x800 @2x) background with:
- Dark theme matching app identity
- Subtle gradient
- Arrow indicating drag-to-install
- Clean, minimal design
"""

from PIL import Image, ImageDraw, ImageFilter
import math

# DMG dimensions (standard)
WIDTH = 660
HEIGHT = 400

# Colors (matching Pixoo Manager dark theme)
BG_DARK = (13, 13, 13)        # #0D0D0D
BG_LIGHTER = (26, 26, 26)     # #1A1A1A
ACCENT_RED = (239, 68, 68)    # #EF4444 (Pixoo red)
ACCENT_PINK = (236, 72, 153)  # #EC4899 (secondary)
TEXT_SECONDARY = (115, 115, 115)  # #737373


def create_gradient_background(width, height, scale=1):
    """Create dark background with subtle radial gradient."""
    w, h = width * scale, height * scale
    img = Image.new('RGB', (w, h), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Create subtle radial gradient from center
    center_x, center_y = w // 2, h // 2
    max_dist = math.sqrt(center_x**2 + center_y**2)

    for y in range(h):
        for x in range(w):
            dist = math.sqrt((x - center_x)**2 + (y - center_y)**2)
            factor = 1 - (dist / max_dist) * 0.3  # Subtle gradient
            r = int(BG_DARK[0] + (BG_LIGHTER[0] - BG_DARK[0]) * factor * 0.5)
            g = int(BG_DARK[1] + (BG_LIGHTER[1] - BG_DARK[1]) * factor * 0.5)
            b = int(BG_DARK[2] + (BG_LIGHTER[2] - BG_DARK[2]) * factor * 0.5)
            img.putpixel((x, y), (r, g, b))

    return img


def create_simple_background(width, height, scale=1):
    """Create simple dark background with accent line."""
    w, h = width * scale, height * scale
    img = Image.new('RGB', (w, h), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Subtle bottom accent line (gradient red to pink)
    line_y = h - (8 * scale)
    for x in range(w):
        progress = x / w
        r = int(ACCENT_RED[0] + (ACCENT_PINK[0] - ACCENT_RED[0]) * progress)
        g = int(ACCENT_RED[1] + (ACCENT_PINK[1] - ACCENT_RED[1]) * progress)
        b = int(ACCENT_RED[2] + (ACCENT_PINK[2] - ACCENT_RED[2]) * progress)
        for dy in range(3 * scale):
            if line_y + dy < h:
                img.putpixel((x, line_y + dy), (r, g, b))

    return img


def draw_arrow(img, start_x, end_x, y, scale=1):
    """Draw a stylized arrow pointing right."""
    draw = ImageDraw.Draw(img)

    # Arrow parameters
    arrow_width = 3 * scale
    head_size = 12 * scale

    # Gradient from red to pink
    total_width = end_x - start_x

    # Draw arrow body (line)
    for x in range(start_x, end_x - head_size):
        progress = (x - start_x) / total_width
        r = int(ACCENT_RED[0] + (ACCENT_PINK[0] - ACCENT_RED[0]) * progress)
        g = int(ACCENT_RED[1] + (ACCENT_PINK[1] - ACCENT_RED[1]) * progress)
        b = int(ACCENT_RED[2] + (ACCENT_PINK[2] - ACCENT_RED[2]) * progress)
        for dy in range(-arrow_width // 2, arrow_width // 2 + 1):
            img.putpixel((x, y + dy), (r, g, b))

    # Draw arrow head (triangle)
    head_x = end_x - head_size
    for i in range(head_size):
        progress = (head_x + i - start_x) / total_width
        r = int(ACCENT_RED[0] + (ACCENT_PINK[0] - ACCENT_RED[0]) * progress)
        g = int(ACCENT_RED[1] + (ACCENT_PINK[1] - ACCENT_RED[1]) * progress)
        b = int(ACCENT_RED[2] + (ACCENT_PINK[2] - ACCENT_RED[2]) * progress)

        # Triangle width decreases as we go right
        tri_half_height = int(head_size * (1 - i / head_size) * 0.8)
        for dy in range(-tri_half_height, tri_half_height + 1):
            px, py = head_x + i, y + dy
            if 0 <= px < img.width and 0 <= py < img.height:
                img.putpixel((px, py), (r, g, b))

    return img


def create_dmg_background(scale=1):
    """Create the complete DMG background."""
    w, h = WIDTH * scale, HEIGHT * scale

    # Start with simple dark background
    img = create_simple_background(WIDTH, HEIGHT, scale)

    # Icon positions (these match where hdiutil places icons)
    # Left icon (app) at ~165px, right icon (Applications) at ~495px
    # Icons are centered at y ~200px
    left_icon_x = 165 * scale
    right_icon_x = 495 * scale
    icons_y = 180 * scale

    # Draw arrow between icon positions
    arrow_start = left_icon_x + (70 * scale)  # After app icon
    arrow_end = right_icon_x - (70 * scale)   # Before Applications icon
    arrow_y = icons_y + (20 * scale)          # Slightly below center

    img = draw_arrow(img, arrow_start, arrow_end, arrow_y, scale)

    return img


def main():
    """Generate DMG background images."""
    import os

    # Output directory
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resources_dir = os.path.join(output_dir, "resources", "dmg")
    os.makedirs(resources_dir, exist_ok=True)

    # Generate 1x (72 DPI)
    print("Generating 1x background (660x400)...")
    bg_1x = create_dmg_background(scale=1)
    bg_1x_path = os.path.join(resources_dir, "background.png")
    bg_1x.save(bg_1x_path, "PNG", dpi=(72, 72))
    print(f"  Saved: {bg_1x_path}")

    # Generate 2x for Retina (144 DPI)
    print("Generating 2x background (1320x800)...")
    bg_2x = create_dmg_background(scale=2)
    bg_2x_path = os.path.join(resources_dir, "background@2x.png")
    bg_2x.save(bg_2x_path, "PNG", dpi=(144, 144))
    print(f"  Saved: {bg_2x_path}")

    # Create multi-resolution TIFF for best compatibility
    print("Creating multi-resolution TIFF...")
    tiff_path = os.path.join(resources_dir, "background.tiff")
    bg_1x.save(tiff_path, "TIFF", dpi=(72, 72))
    print(f"  Saved: {tiff_path}")

    print("\nDone! Background images created in resources/dmg/")


if __name__ == "__main__":
    main()
