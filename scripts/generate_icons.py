"""Generate the PWA launcher icons (icon-192.png, icon-512.png).

Design: violet vertical gradient on a rounded square, with a white "H"
monogram built from geometric bars (no font dependency — letterforms drawn
as rounded rectangles render identically in any build environment).
Runs as a RUN step inside the Docker build.
"""

from PIL import Image, ImageDraw
import os


GRADIENT_TOP = (139, 92, 246)     # #8b5cf6
GRADIENT_BOTTOM = (91, 33, 182)   # #5b21b6
ACCENT = (216, 180, 254)          # #d8b4fe — soft highlight


def rounded_mask(size, radius, supersample=4):
    """Anti-aliased rounded-rectangle alpha mask."""
    big = size * supersample
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=radius * supersample, fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def vertical_gradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def make_icon(size):
    s = size
    # Background: gradient clipped to a rounded square. The monogram stays
    # well inside the 80% safe zone, so the icon works as maskable too.
    radius = int(s / 4.4)
    grad = vertical_gradient(s, GRADIENT_TOP, GRADIENT_BOTTOM)
    mask = rounded_mask(s, radius)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    # "H" monogram — two vertical bars + crossbar, all rounded.
    # Drawn supersampled for crisp edges at small sizes.
    ss = 4
    big = s * ss
    glyph = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(glyph)

    bar_w = big * 0.13
    bar_h = big * 0.50
    gap = big * 0.175          # horizontal distance from center to each bar center
    cx, cy = big / 2, big / 2
    r = bar_w / 2

    left_x = cx - gap
    right_x = cx + gap
    top_y = cy - bar_h / 2
    bottom_y = cy + bar_h / 2

    white = (255, 255, 255, 255)
    d.rounded_rectangle([left_x - bar_w / 2, top_y, left_x + bar_w / 2, bottom_y], radius=r, fill=white)
    d.rounded_rectangle([right_x - bar_w / 2, top_y, right_x + bar_w / 2, bottom_y], radius=r, fill=white)
    # Crossbar
    cross_h = bar_w * 0.92
    d.rounded_rectangle([left_x, cy - cross_h / 2, right_x, cy + cross_h / 2], radius=cross_h / 2, fill=white)

    glyph = glyph.resize((s, s), Image.LANCZOS)
    img.alpha_composite(glyph)

    # Flatten onto near-black so the PNG has no transparency surprises
    bg = Image.new("RGB", (s, s), "#0d0d0d")
    bg.paste(img, (0, 0), img)
    return bg


os.makedirs("static", exist_ok=True)
make_icon(192).save("static/icon-192.png")
make_icon(512).save("static/icon-512.png")
print("Icons generated.")
