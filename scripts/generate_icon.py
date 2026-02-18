#!/usr/bin/env python3
"""Generate the CursorHub menu bar icon as a template PNG.

Creates a @2x (36x36) icon with a cursor-arrow + hub design.
macOS uses template images: black shapes on transparent background,
automatically adapted for light/dark mode.
"""

from PIL import Image, ImageDraw


def draw_icon(size=36):
    """Draw the CursorHub icon at the given size.
    
    Design: A bold cursor/pointer arrow with 3 small hub dots
    arranged to the upper-left. Clean and readable at 18px.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    s = size / 36.0
    black = (0, 0, 0, 255)

    # --- Cursor arrow (main element, lower-right area) ---
    # Classic macOS-style pointer arrow, bold and clean
    tip_x, tip_y = 11 * s, 4 * s  # top-left tip of arrow
    
    arrow = [
        (tip_x, tip_y),                           # tip (pointing up-left)
        (tip_x, tip_y + 22 * s),                  # down the left edge
        (tip_x + 5.5 * s, tip_y + 17 * s),       # notch left
        (tip_x + 10 * s, tip_y + 25 * s),        # bottom-right tail
        (tip_x + 14 * s, tip_y + 22 * s),        # tail outer edge
        (tip_x + 9 * s, tip_y + 14.5 * s),       # notch right
        (tip_x + 16 * s, tip_y + 11 * s),        # right point
    ]
    
    draw.polygon(arrow, fill=black)

    # --- Hub dots (3 dots in upper-left, representing the "hub") ---
    dot_r = 2.2 * s
    
    # Dot 1 — top-left
    cx, cy = 4 * s, 4 * s
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=black)

    # Dot 2 — left-center  
    cx, cy = 3 * s, 13 * s
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=black)

    # Dot 3 — top-center
    cx, cy = 13 * s, 1.5 * s
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=black)

    return img


def main():
    import os

    out_dir = os.path.join(os.path.dirname(__file__), "..", "src", "cursorhub", "resources")
    os.makedirs(out_dir, exist_ok=True)

    # @2x for retina (36x36) — this is what rumps will use
    icon_2x = draw_icon(36)
    icon_2x.save(os.path.join(out_dir, "icon.png"), "PNG")
    print("Saved icon.png (36x36 @2x)")

    # @1x (18x18)
    icon_1x = draw_icon(18)
    icon_1x.save(os.path.join(out_dir, "icon_18.png"), "PNG")
    print("Saved icon_18.png (18x18 @1x)")

    print("Done!")


if __name__ == "__main__":
    main()
