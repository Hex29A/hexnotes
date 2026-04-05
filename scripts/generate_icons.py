from PIL import Image, ImageDraw, ImageFont
import math
import os


def hex_vertices(cx, cy, r):
    """Return vertices of a regular hexagon centered at (cx, cy) with radius r."""
    verts = []
    for i in range(6):
        angle = math.radians(60 * i - 30)  # flat-top hexagon
        verts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return verts


def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    pad = size * 0.06
    s = size  # shorthand

    # --- Background: purple rounded rectangle ---
    corner_r = s // 6
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=corner_r,
        fill="#7c3aed",
    )

    # --- Hexagon outline (subtle, behind the note) ---
    hex_r = s * 0.38
    verts = hex_vertices(cx, cy, hex_r)
    hex_line_w = max(2, s // 64)
    for i in range(6):
        draw.line(
            [verts[i], verts[(i + 1) % 6]],
            fill=(255, 255, 255, 50),  # very faint white
            width=hex_line_w,
        )

    # --- Note/document shape ---
    # A page with a folded top-right corner
    note_left = cx - s * 0.20
    note_right = cx + s * 0.22
    note_top = cy - s * 0.28
    note_bottom = cy + s * 0.30
    fold_size = s * 0.10  # size of the corner fold

    # Page body (polygon without the folded corner)
    page_points = [
        (note_left, note_top),                        # top-left
        (note_right - fold_size, note_top),            # top-right before fold
        (note_right, note_top + fold_size),            # fold crease
        (note_right, note_bottom),                     # bottom-right
        (note_left, note_bottom),                      # bottom-left
    ]
    draw.polygon(page_points, fill=(255, 255, 255, 230))

    # Folded corner triangle (darker shade to show the fold)
    fold_points = [
        (note_right - fold_size, note_top),
        (note_right, note_top + fold_size),
        (note_right - fold_size, note_top + fold_size),
    ]
    draw.polygon(fold_points, fill=(200, 180, 240, 200))

    # Fold edge line
    fold_lw = max(1, s // 128)
    draw.line(
        [(note_right - fold_size, note_top),
         (note_right - fold_size, note_top + fold_size),
         (note_right, note_top + fold_size)],
        fill=(124, 58, 237, 150),
        width=fold_lw,
    )

    # --- Text lines on the note (simulating content) ---
    line_color = (124, 58, 237, 160)
    line_h = max(2, s // 80)
    margin_l = note_left + s * 0.05
    margin_r = note_right - s * 0.06
    line_y_start = note_top + fold_size + s * 0.04
    line_spacing = s * 0.065

    # 4 lines of "text", varying widths
    line_widths = [0.95, 0.75, 0.85, 0.55]
    for i, w in enumerate(line_widths):
        ly = line_y_start + i * line_spacing
        lx_end = margin_l + (margin_r - margin_l) * w
        draw.rounded_rectangle(
            [margin_l, ly, lx_end, ly + line_h],
            radius=line_h // 2,
            fill=line_color,
        )

    # --- Small "#" tag chip at bottom of note ---
    chip_y = note_bottom - s * 0.08
    chip_x = margin_l
    chip_w = s * 0.16
    chip_h = s * 0.045
    draw.rounded_rectangle(
        [chip_x, chip_y, chip_x + chip_w, chip_y + chip_h],
        radius=chip_h // 2,
        fill=(168, 85, 247, 180),
    )

    # Convert to RGB with dark background for PNG
    bg = Image.new("RGB", (size, size), "#0d0d0d")
    bg.paste(img, (0, 0), img)
    return bg


os.makedirs("static", exist_ok=True)
make_icon(192).save("static/icon-192.png")
make_icon(512).save("static/icon-512.png")
print("Icons generated.")
