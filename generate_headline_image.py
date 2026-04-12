"""
Generate a LinkedIn article headline image.
Output: docs/blog_images/headline_part2.png (1200 x 644 px)

Usage: python generate_headline_image.py
"""

from PIL import Image, ImageDraw, ImageFont
import textwrap

# ── Canvas ──────────────────────────────────────────────────────────────────
W, H = 1200, 400
img = Image.new("RGB", (W, H), "#0f172a")   # dark navy
draw = ImageDraw.Draw(img)

# ── Accent stripe (left edge) ───────────────────────────────────────────────
draw.rectangle([(0, 0), (6, H)], fill="#38bdf8")  # sky-blue

# ── Subtle grid lines (light) ───────────────────────────────────────────────
for x in range(0, W, 120):
    draw.line([(x, 0), (x, H)], fill="#1e293b", width=1)
for y in range(0, H, 80):
    draw.line([(0, y), (W, y)], fill="#1e293b", width=1)

# ── Fonts ───────────────────────────────────────────────────────────────────
F = "C:/Windows/Fonts/"
font_tag      = ImageFont.truetype(F + "Candarab.ttf", 20)
font_headline = ImageFont.truetype(F + "Candarab.ttf", 52)
font_sub      = ImageFont.truetype(F + "Candara.ttf",  26)
font_byline   = ImageFont.truetype(F + "Candara.ttf",  20)

# ── Tag pill ─────────────────────────────────────────────────────────────────
tag_text = "AGENTIC AI  ·  PART 2"
tag_x, tag_y = 54, 44
tw = draw.textlength(tag_text, font=font_tag)
pad = 12
draw.rounded_rectangle(
    [(tag_x - pad, tag_y - 6), (tag_x + tw + pad, tag_y + 26)],
    radius=6, fill="#0369a1"
)
draw.text((tag_x, tag_y), tag_text, font=font_tag, fill="#e0f2fe")

# ── Headline (wrapped) ──────────────────────────────────────────────────────
headline = "15 Patterns from Running an\nAI Agent in Production"
hl_x = 54
hl_y = 96
line_gap = 64
for line in headline.split("\n"):
    draw.text((hl_x, hl_y), line, font=font_headline, fill="#f8fafc")
    hl_y += line_gap

# ── Sub-headline ─────────────────────────────────────────────────────────────
sub = "What breaks. What it costs. What the courses don't cover."
draw.text((54, hl_y + 12), sub, font=font_sub, fill="#94a3b8")

# ── Divider ──────────────────────────────────────────────────────────────────
div_y = hl_y + 54
draw.line([(54, div_y), (W - 54, div_y)], fill="#1e3a5f", width=1)

# ── Pattern count badges ─────────────────────────────────────────────────────
badges = [
    ("Memory",   "#0369a1"),
    ("Control",  "#166534"),
    ("Security", "#9f1239"),
    ("Cost",     "#78350f"),
]
bx = 54
by = div_y + 18
for label, colour in badges:
    bw = draw.textlength(label, font=font_byline) + 22
    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + 30)],
        radius=5, fill=colour
    )
    draw.text((bx + 11, by + 5), label, font=font_byline, fill="#f1f5f9")
    bx += bw + 10

# ── Byline ───────────────────────────────────────────────────────────────────
draw.text((54, H - 40), "Sivakumar Suthram", font=font_byline, fill="#64748b")

# ── Bottom accent ─────────────────────────────────────────────────────────────
draw.rectangle([(0, H - 4), (W, H)], fill="#38bdf8")

# ── Save ─────────────────────────────────────────────────────────────────────
out = "docs/blog_images/headline_part2.png"
img.save(out, "PNG")
print(f"Saved: {out}  ({W}×{H}px)")
