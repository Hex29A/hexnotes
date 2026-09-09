"""Generate the PWA launcher icons (icon-192.png, icon-512.png).

Design: green "emalj" hexagon badge - a diagonal gradient fill, a thin
darker border, a soft gloss highlight, and the HexNotes "folded page"
glyph in white. Same geometry as static/favicon.svg and the app's
--accent token (see docs.29a.se/... ikonförslag, 2026-09-09).
Runs as a RUN step inside the Docker build.
"""

from PIL import Image, ImageDraw
import math
import os


GRAD_TOP = (0x37, 0xC1, 0x7E)     # #37C17E
GRAD_BOTTOM = (0x0E, 0x4A, 0x2C)  # #0E4A2C
BORDER = (0x0B, 0x3A, 0x22)       # #0B3A22

# Flat-top regular hexagon, centered at (50,50) in a 0-100 unit space,
# radius 44 - identical geometry to static/favicon.svg.
_HEX_VERTS = [(94, 50), (72, 88.1), (28, 88.1), (6, 50), (28, 11.9), (72, 11.9)]
_ROUND_R = 10


def _corner_points(verts, r):
    """For each vertex, the two points offset by r toward its neighbours -
    the endpoints of the quadratic curve that rounds that corner."""
    n = len(verts)
    out = []
    for i in range(n):
        px, py = verts[(i - 1) % n]
        vx, vy = verts[i]
        nx, ny = verts[(i + 1) % n]
        d1x, d1y = px - vx, py - vy
        l1 = math.hypot(d1x, d1y)
        d2x, d2y = nx - vx, ny - vy
        l2 = math.hypot(d2x, d2y)
        p_in = (vx + d1x / l1 * r, vy + d1y / l1 * r)
        p_out = (vx + d2x / l2 * r, vy + d2y / l2 * r)
        out.append((p_in, (vx, vy), p_out))
    return out


def _rounded_hex_polygon(scale, steps=8):
    """Sample the rounded hexagon outline as a fine polygon, scaled to `scale`px."""
    corners = _corner_points(_HEX_VERTS, _ROUND_R)
    pts = []
    for p_in, vertex, p_out in corners:
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * p_in[0] + 2 * (1 - t) * t * vertex[0] + t ** 2 * p_out[0]
            y = (1 - t) ** 2 * p_in[1] + 2 * (1 - t) * t * vertex[1] + t ** 2 * p_out[1]
            pts.append((x * scale / 100, y * scale / 100))
    return pts


def _hex_mask(size, supersample=4):
    big = size * supersample
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon(_rounded_hex_polygon(big), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def _diagonal_gradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            r = round(top[0] + (bottom[0] - top[0]) * t)
            g = round(top[1] + (bottom[1] - top[1]) * t)
            b = round(top[2] + (bottom[2] - top[2]) * t)
            px[x, y] = (r, g, b)
    return img


def make_icon(size):
    s = size
    mask = _hex_mask(s)
    grad = _diagonal_gradient(s, GRAD_TOP, GRAD_BOTTOM)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    # Thin darker border along the hex outline.
    outline = _rounded_hex_polygon(s)
    ImageDraw.Draw(img).line(
        outline + [outline[0]], fill=BORDER + (255,),
        width=max(2, round(s * 0.016)), joint="curve",
    )

    # Soft gloss highlight, upper-left, clipped to the hex silhouette.
    gloss = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).ellipse(
        [s * 0.10, s * 0.10, s * 0.58, s * 0.44], fill=(255, 255, 255, 90)
    )
    gloss.putalpha(Image.composite(gloss.split()[3], Image.new("L", (s, s), 0), mask))
    img.alpha_composite(gloss)

    # "Folded page" glyph - HexNotes' mark, in white. Supersampled for
    # crisp edges, like the hex mask above.
    ss = 4
    big = s * ss

    def p(x, y):
        return (x / 100 * big, y / 100 * big)

    glyph = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(glyph).polygon(
        [p(36, 30), p(58, 30), p(66, 38), p(66, 70), p(36, 70)], fill=(255, 255, 255, 255)
    )
    fold = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(fold).polygon([p(58, 30), p(66, 38), p(58, 38)], fill=(255, 255, 255, 140))
    glyph.alpha_composite(fold)
    glyph = glyph.resize((s, s), Image.LANCZOS)
    img.alpha_composite(glyph)

    # Flatten onto the app's own dark background - same choice the old
    # violet icon made, avoids transparent-PWA-icon quirks on install.
    bg = Image.new("RGB", (s, s), "#0d0d0d")
    bg.paste(img, (0, 0), img)
    return bg


os.makedirs("static", exist_ok=True)
make_icon(192).save("static/icon-192.png")
make_icon(512).save("static/icon-512.png")
print("Icons generated.")
