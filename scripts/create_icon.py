#!/usr/bin/env python3
"""
Generate Pixoo app icon - colorful pixel grid representing LED display.
"""

import os
import subprocess
from pathlib import Path
from PIL import Image

# Icon sizes required for macOS .icns
ICON_SIZES = [16, 32, 64, 128, 256, 512, 1024]

# 8x8 pixel art design - vibrant colors representing LED display
# Each value is an RGB tuple
PIXEL_ART = [
    # Row 0 - top
    [(255, 87, 87), (255, 138, 76), (255, 214, 92), (145, 232, 66), (66, 214, 232), (92, 138, 255), (176, 92, 255), (255, 92, 176)],
    # Row 1
    [(255, 138, 76), (255, 214, 92), (145, 232, 66), (66, 214, 232), (92, 138, 255), (176, 92, 255), (255, 92, 176), (255, 87, 87)],
    # Row 2
    [(255, 214, 92), (145, 232, 66), (66, 214, 232), (92, 138, 255), (176, 92, 255), (255, 92, 176), (255, 87, 87), (255, 138, 76)],
    # Row 3
    [(145, 232, 66), (66, 214, 232), (92, 138, 255), (176, 92, 255), (255, 92, 176), (255, 87, 87), (255, 138, 76), (255, 214, 92)],
    # Row 4
    [(66, 214, 232), (92, 138, 255), (176, 92, 255), (255, 92, 176), (255, 87, 87), (255, 138, 76), (255, 214, 92), (145, 232, 66)],
    # Row 5
    [(92, 138, 255), (176, 92, 255), (255, 92, 176), (255, 87, 87), (255, 138, 76), (255, 214, 92), (145, 232, 66), (66, 214, 232)],
    # Row 6
    [(176, 92, 255), (255, 92, 176), (255, 87, 87), (255, 138, 76), (255, 214, 92), (145, 232, 66), (66, 214, 232), (92, 138, 255)],
    # Row 7 - bottom
    [(255, 92, 176), (255, 87, 87), (255, 138, 76), (255, 214, 92), (145, 232, 66), (66, 214, 232), (92, 138, 255), (176, 92, 255)],
]


def create_base_icon(size: int = 1024) -> Image.Image:
    """
    Create the base icon at specified size.

    Uses nearest-neighbor scaling to preserve sharp pixel edges.
    Adds subtle rounded corners and shadow for modern macOS look.
    """
    # Create 8x8 base image from pixel art
    base = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    pixels = base.load()

    for y, row in enumerate(PIXEL_ART):
        for x, color in enumerate(row):
            pixels[x, y] = (*color, 255)

    # Scale up with nearest-neighbor to preserve sharp pixels
    scaled = base.resize((size, size), Image.Resampling.NEAREST)

    # Add rounded corners (macOS style)
    corner_radius = size // 5  # 20% of size
    mask = create_rounded_mask(size, corner_radius)

    # Apply mask
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(scaled, (0, 0), mask)

    return result


def create_rounded_mask(size: int, radius: int) -> Image.Image:
    """Create a rounded rectangle mask."""
    mask = Image.new("L", (size, size), 0)
    pixels = mask.load()

    for y in range(size):
        for x in range(size):
            # Check if pixel is inside rounded rectangle
            if is_inside_rounded_rect(x, y, size, size, radius):
                pixels[x, y] = 255

    return mask


def is_inside_rounded_rect(x: int, y: int, w: int, h: int, r: int) -> bool:
    """Check if point (x, y) is inside a rounded rectangle."""
    # Check corners
    if x < r and y < r:
        # Top-left corner
        return (x - r) ** 2 + (y - r) ** 2 <= r ** 2
    elif x >= w - r and y < r:
        # Top-right corner
        return (x - (w - r - 1)) ** 2 + (y - r) ** 2 <= r ** 2
    elif x < r and y >= h - r:
        # Bottom-left corner
        return (x - r) ** 2 + (y - (h - r - 1)) ** 2 <= r ** 2
    elif x >= w - r and y >= h - r:
        # Bottom-right corner
        return (x - (w - r - 1)) ** 2 + (y - (h - r - 1)) ** 2 <= r ** 2
    else:
        # Inside rectangle (not in corner regions)
        return True


def create_iconset(output_dir: Path) -> None:
    """Create .iconset directory with all required sizes."""
    iconset_dir = output_dir / "Pixoo.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for size in ICON_SIZES:
        # Standard resolution
        icon = create_base_icon(size)
        icon.save(iconset_dir / f"icon_{size}x{size}.png")
        print(f"  Created icon_{size}x{size}.png")

        # Retina resolution (2x) - only for sizes up to 512
        if size <= 512:
            icon_2x = create_base_icon(size * 2)
            icon_2x.save(iconset_dir / f"icon_{size}x{size}@2x.png")
            print(f"  Created icon_{size}x{size}@2x.png")

    return iconset_dir


def convert_to_icns(iconset_dir: Path, output_path: Path) -> bool:
    """Convert .iconset to .icns using macOS iconutil."""
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting to icns: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("iconutil not found - are you on macOS?")
        return False


def main():
    """Generate Pixoo app icon."""
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    resources_dir = project_dir / "resources"
    resources_dir.mkdir(exist_ok=True)

    print("Creating Pixoo icon...")

    # Create iconset
    print("\nGenerating icon sizes:")
    iconset_dir = create_iconset(resources_dir)

    # Convert to .icns
    icns_path = resources_dir / "Pixoo.icns"
    print(f"\nConverting to .icns...")

    if convert_to_icns(iconset_dir, icns_path):
        print(f"Icon created: {icns_path}")

        # Also save a preview PNG
        preview = create_base_icon(512)
        preview_path = resources_dir / "icon_preview.png"
        preview.save(preview_path)
        print(f"Preview saved: {preview_path}")

        return True
    else:
        print("Failed to create .icns - iconset preserved for manual conversion")
        return False


if __name__ == "__main__":
    main()
