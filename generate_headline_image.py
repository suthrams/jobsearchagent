"""
Generate a LinkedIn article banner image.
Output: docs/blog_images/headline_part2.png (1200 x 400 px)

Usage: python generate_headline_image.py
"""

from PIL import Image, ImageDraw, ImageFont

# ── Canvas ───────────────────────────────────────────────────────────────────
W, H = 1200, 400
img = Image.new("RGB", (W, H), "#0f172a")
draw = ImageDraw.Draw(img)

# ── Accent stripe (left edge) ────────────────────────────────────────────────
draw.rectangle([(0, 0), (6, H)], fill="#38bdf8")

# ── Subtle grid lines ────────────────────────────────────────────────────────
for x in range(0, W, 120):
    draw.line([(x, 0), (x, H)], fill="#1e293b", width=1)
for y in range(0, H, 80):
    draw.line([(0, y), (W, y)], fill="#1e293b", width=1)

# ── Fonts ────────────────────────────────────────────────────────────────────
F = "C:/Windows/Fonts/"
font_tag      = ImageFont.truetype(F + "Candarab.ttf", 18)
font_headline = ImageFont.truetype(F + "Candarab.ttf", 46)
font_sub      = ImageFont.truetype(F + "Candara.ttf",  22)
font_byline   = ImageFont.truetype(F + "Candara.ttf",  18)
font_connect  = ImageFont.truetype(F + "Candara.ttf",  16)

# ── Tag pill ─────────────────────────────────────────────────────────────────
tag_text = "AGENTIC AI  .  PART 2"
tag_x, tag_y = 54, 38
tw = draw.textlength(tag_text, font=font_tag)
draw.rounded_rectangle(
    [(tag_x - 12, tag_y - 5), (tag_x + tw + 12, tag_y + 22)],
    radius=5, fill="#0369a1"
)
draw.text((tag_x, tag_y), tag_text, font=font_tag, fill="#e0f2fe")

# ── Headline ─────────────────────────────────────────────────────────────────
headline = "Designed. Built. Shipped.\nWhat building an AI agent from scratch\nactually teaches you."
hl_y = 82
for line in headline.split("\n"):
    draw.text((54, hl_y), line, font=font_headline, fill="#f8fafc")
    hl_y += 56

# ── Sub-headline ─────────────────────────────────────────────────────────────
sub = "15 patterns from supporting my own job search with an agentic AI system -- running in production on my laptop."
draw.text((54, hl_y + 6), sub, font=font_sub, fill="#94a3b8")

# ── Divider ──────────────────────────────────────────────────────────────────
div_y = hl_y + 38
draw.line([(54, div_y), (W - 54, div_y)], fill="#1e3a5f", width=1)

# ── Badges ───────────────────────────────────────────────────────────────────
badges = [
    ("Architecture", "#0369a1"),
    ("Distributed Systems", "#166534"),
    ("AI Adoption",  "#6b21a8"),
    ("Security",     "#9f1239"),
]
bx = 54
by = div_y + 14
for lbl, colour in badges:
    bw = draw.textlength(lbl, font=font_byline) + 20
    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + 26)],
        radius=4, fill=colour
    )
    draw.text((bx + 10, by + 4), lbl, font=font_byline, fill="#f1f5f9")
    bx += bw + 10

# ── Byline + connect nudge ───────────────────────────────────────────────────
draw.text((54, H - 44), "Sivakumar Suthram", font=font_byline, fill="#64748b")
connect_text = "linkedin.com/in/sivakumar-suthram"
draw.text((54, H - 22), connect_text, font=font_connect, fill="#38bdf8")

# ── Bottom accent ─────────────────────────────────────────────────────────────
draw.rectangle([(0, H - 4), (W, H)], fill="#38bdf8")

# ── Save ─────────────────────────────────────────────────────────────────────
out = "docs/blog_images/headline_part2.png"
img.save(out, "PNG")
print(f"Saved: {out}  ({W}x{H}px)")
