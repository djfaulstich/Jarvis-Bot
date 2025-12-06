from pathlib import Path
from PIL import Image, ImageDraw

# Adjust this if your path is different
CARDS_DIR = Path(__file__).resolve().parent / "bot" / "PNG-cards-1.3"

# Use an existing card to detect size
sample_card = CARDS_DIR / "ace_of_spades.png"  # any card works
if not sample_card.exists():
    raise FileNotFoundError(f"Sample card not found: {sample_card}")

card_img = Image.open(sample_card).convert("RGBA")
w, h = card_img.size

# Create back image
back = Image.new("RGBA", (w, h), (181, 180, 141, 255))  # dark blue background
draw = ImageDraw.Draw(back)

# Border
margin = 8
draw.rectangle(
    [margin, margin, w - margin - 1, h - margin - 1],
    outline=(230, 230, 230, 255),
    width=3,
)

# Inner rounded rectangle
inner_margin = 20
draw.rounded_rectangle(
    [inner_margin, inner_margin, w - inner_margin - 1, h - inner_margin - 1],
    radius=20,
    outline=(200, 200, 200, 255),
    width=2,
    fill=(201, 48, 48, 255),
)

# Simple diamond pattern
step = 18
for y in range(inner_margin + step // 2, h - inner_margin, step):
    for x in range(inner_margin + step // 2, w - inner_margin, step):
        draw.ellipse(
            [x - 4, y - 4, x + 4, y + 4],
            fill=(255, 255, 255, 255),
        )

out_path = CARDS_DIR / "back.png"
back.save(out_path)
print(f"Saved card back to {out_path}")
