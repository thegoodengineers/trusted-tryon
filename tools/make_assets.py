"""Draw our own demo images: five garment product shots and two shopper figures.

Everything here is a flat, non-photoreal illustration we generated, so no real person's image and no
third-party product photo is used anywhere in the demo. Licence: same as the repo (MIT).
Run: python tools/make_assets.py  (writes static/garments/*.png and static/models/*.png)
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 768, 1024
BG = (255, 255, 255)


def tee_shape(d, fill, long_sleeves=False, length=0.0, outline=None):
    """A front-view top on a plain background. length > 0 makes it a kurta/dress."""
    body_bottom = 820 + int(length * 180)
    sleeve = [(170, 250), (90, 470 if long_sleeves else 380), (175, 500 if long_sleeves else 410), (225, 330)]
    d.polygon([(230, 180), (320, 150), (384, 190), (448, 150), (538, 180), (598, 250), (560, 330),
               (545, 330), (560, body_bottom), (208, body_bottom), (223, 330), (208, 330), (170, 250)],
              fill=fill, outline=outline)
    d.polygon(sleeve, fill=fill, outline=outline)
    d.polygon([(768 - x, y) for x, y in sleeve], fill=fill, outline=outline)
    d.ellipse((330, 150, 438, 225), fill=BG)  # neckline


def mask_of(img):
    m = Image.new("L", img.size, 0)
    px, mp = img.load(), m.load()
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y] != BG:
                mp[x, y] = 255
    return m


def patterned(shape_fn, pattern_fn, base):
    """Draw the garment shape, then paint a pattern clipped to it."""
    img = Image.new("RGB", (W, H), BG)
    shape_fn(ImageDraw.Draw(img), base)
    m = mask_of(img)
    pat = Image.new("RGB", (W, H), base)
    pattern_fn(ImageDraw.Draw(pat))
    img.paste(pat, (0, 0), m)
    return img


def font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def stripes(d):
    for y in range(140, 1000, 44):
        d.rectangle((0, y, W, y + 20), fill=(27, 42, 94))


def block_print(d):
    for row, y in enumerate(range(170, 1000, 90)):
        for x in range(150 + (row % 2) * 45, 640, 90):
            d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=(176, 38, 38))
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(27, 66, 48))
            for dx, dy in ((0, -34), (34, 0), (0, 34), (-34, 0)):
                d.ellipse((x + dx - 5, y + dy - 5, x + dx + 5, y + dy + 5), fill=(176, 38, 38))


def dots(d):
    for row, y in enumerate(range(160, 1010, 60)):
        for x in range(120 + (row % 2) * 30, 660, 60):
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(255, 255, 255))


def denim(d):
    for x in range(0, W, 6):
        d.line((x, 0, x, H), fill=(52, 78, 128), width=2)


GARMENTS = {
    "breton-tee": lambda: patterned(lambda d, c: tee_shape(d, c, outline=(150, 150, 160)), stripes, (250, 238, 212)),
    "block-print-kurta": lambda: patterned(lambda d, c: tee_shape(d, c, long_sleeves=True, length=0.9),
                                           block_print, (232, 178, 52)),
    "polka-wrap-dress": lambda: patterned(lambda d, c: tee_shape(d, c, length=0.95), dots, (190, 30, 45)),
}


def denim_jacket():
    img = patterned(lambda d, c: tee_shape(d, c, long_sleeves=True), denim, (64, 92, 145))
    d = ImageDraw.Draw(img)
    d.line((384, 225, 384, 820), fill=(30, 45, 80), width=6)  # placket
    for y in range(280, 800, 90):
        d.ellipse((396, y, 416, y + 20), fill=(196, 160, 90))  # copper buttons
    for x0 in (250, 430):  # chest pockets with copper stitching
        d.rectangle((x0, 300, x0 + 90, 390), outline=(214, 150, 60), width=4)
    return img


GARMENTS["denim-jacket"] = denim_jacket


def logo_sweatshirt():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    tee_shape(d, (31, 107, 74), long_sleeves=True)
    d.text((384, 420), "TGE", font=font(150), fill=(255, 255, 255), anchor="mm")
    d.text((384, 520), "EST. 2026", font=font(40), fill=(232, 185, 35), anchor="mm")
    return img


GARMENTS["logo-sweatshirt"] = logo_sweatshirt

# Two shopper figures: different skin tones and builds. Torso boxes are used by the mock try-on.
MODELS = {
    "asha": {"skin": (141, 85, 54), "hair": (30, 22, 20), "shirt": (150, 160, 170), "width": 1.0},
    "ravi": {"skin": (198, 134, 96), "hair": (45, 35, 30), "shirt": (120, 130, 110), "width": 1.18},
}


def figure(skin, hair, shirt, width):
    img = Image.new("RGB", (W, H), (226, 230, 236))
    d = ImageDraw.Draw(img)
    cx, half = 384, int(115 * width)
    d.rectangle((cx - 70, 760, cx - 18, 1000), fill=(48, 52, 70))  # legs
    d.rectangle((cx + 18, 760, cx + 70, 1000), fill=(48, 52, 70))
    d.rounded_rectangle((cx - half, 250, cx + half, 780), 60, fill=shirt)  # torso in own clothes
    d.rounded_rectangle((cx - half - 55, 270, cx - half + 5, 650), 30, fill=shirt)  # arms
    d.rounded_rectangle((cx + half - 5, 270, cx + half + 55, 650), 30, fill=shirt)
    d.ellipse((cx - half - 52, 630, cx - half + 2, 690), fill=skin)  # hands
    d.ellipse((cx + half - 2, 630, cx + half + 52, 690), fill=skin)
    d.rectangle((cx - 28, 200, cx + 28, 260), fill=skin)  # neck
    d.ellipse((cx - 75, 60, cx + 75, 230), fill=skin)  # head
    d.chord((cx - 80, 45, cx + 80, 200), 180, 360, fill=hair)
    return img


def main():
    (ROOT / "static/garments").mkdir(parents=True, exist_ok=True)
    (ROOT / "static/models").mkdir(parents=True, exist_ok=True)
    for name, make in GARMENTS.items():
        make().save(ROOT / f"static/garments/{name}.png", optimize=True)
    for name, spec in MODELS.items():
        figure(**spec).save(ROOT / f"static/models/{name}.png", optimize=True)
    print("wrote", len(GARMENTS), "garments and", len(MODELS), "figures")


if __name__ == "__main__":
    main()
