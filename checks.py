"""Honest checks around a try-on: is the photo usable (before we spend a credit), and does the result
keep the garment's colours, actually show the garment, and carry the AI label (after).

All checks are simple and explainable on purpose; each returns a sentence a shopper can read.
Colour difference is CIE76 Delta E in CIELAB (sRGB D65), the standard textbook formula.
"""
import io

import numpy as np
from PIL import Image, ImageOps

from tryon_client import AI_LABEL

MAX_SIDE = 1600  # the API docs suggest ~1600 px: well under the 4 MB limit
MIN_SHORT_SIDE = 400
# ponytail: thresholds picked on our own demo images and a few phone photos, not tuned on a dataset.
DARK, BRIGHT = 55, 215  # mean grey level
BLUR = 25.0  # variance of the Laplacian on a 512 px grey copy; below this the photo looks soft
DELTA_E = 14.0  # "same colour" for a shopper's eye under different light
FOUND_RATIO = 0.25  # a garment colour is present if, in the changed area, it covers >= 25% of its share of the product
CHANGED = 6.0  # mean absolute difference (0-255) below which the result is basically the original photo


def finding(fid, ok, text, level=None):
    return {"id": fid, "ok": ok, "level": level or ("pass" if ok else "fail"), "text": text}


def photo_check(data: bytes):
    """Returns (findings, clean_jpeg_or_None). A 'block' finding means: don't send it to the API."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return [finding("readable", False, "We couldn't read that file. Use a JPEG or PNG photo.", "block")], None
    img = ImageOps.exif_transpose(img).convert("RGB")
    out = []
    if min(img.size) < MIN_SHORT_SIDE:
        out.append(finding("size", False, f"The photo is too small ({img.width}x{img.height}). "
                           f"Use one at least {MIN_SHORT_SIDE} px on the short side.", "block"))
        return out, None
    out.append(finding("size", True, f"Big enough ({img.width}x{img.height})."))
    if img.height >= img.width:
        out.append(finding("framing", True, "Portrait framing, which suits a full-length try-on."))
    else:
        out.append(finding("framing", False, "Landscape photo. A full-length, portrait photo works best.", "warn"))
    grey = np.asarray(img.convert("L").resize((512, max(1, round(512 * img.height / img.width)))), dtype=float)
    mean = grey.mean()
    if mean < DARK:
        out.append(finding("light", False, "The photo is very dark. Try again in daylight.", "warn"))
    elif mean > BRIGHT:
        out.append(finding("light", False, "The photo is very bright or washed out.", "warn"))
    else:
        out.append(finding("light", True, "Lighting looks even."))
    lap = grey[1:-1, 2:] + grey[1:-1, :-2] + grey[2:, 1:-1] + grey[:-2, 1:-1] - 4 * grey[1:-1, 1:-1]
    if lap.var() < BLUR:
        out.append(finding("sharp", False, "The photo looks blurry. Hold still or clean the lens.", "warn"))
    else:
        out.append(finding("sharp", True, "Sharp enough."))
    scale = min(1.0, MAX_SIDE / max(img.size))
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)  # re-encoding drops EXIF, including GPS location
    return out, buf.getvalue()


def to_lab(rgb):
    """sRGB (0-255, ...x3) to CIELAB, D65."""
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]])
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def garment_mask(img, tol=24):
    """Garment pixels = everything not connected to the background at the image border.
    Background grows from the border through pixels close to the corner colour (a flood fill)."""
    px = np.asarray(img.convert("RGB"), dtype=int)
    similar = np.abs(px - px[0, 0]).max(-1) <= tol
    bg = np.zeros_like(similar)
    bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1] = similar[0, :], similar[-1, :], similar[:, 0], similar[:, -1]
    while True:
        grown = bg.copy()
        grown[1:] |= bg[:-1]
        grown[:-1] |= bg[1:]
        grown[:, 1:] |= bg[:, :-1]
        grown[:, :-1] |= bg[:, 1:]
        grown &= similar
        if (grown == bg).all():
            return ~bg
        bg = grown


def palette(img, k=6, min_share=0.10):
    """The garment's main colours: (rgb, share) for each colour covering at least min_share of it."""
    img = img.convert("RGB").resize((256, round(256 * img.height / img.width)), Image.NEAREST)  # no blended edge colours
    px = np.asarray(img)[garment_mask(img)]
    q = Image.fromarray(px.reshape(1, -1, 3).astype("uint8")).quantize(k, method=Image.Quantize.MEDIANCUT)
    counts = np.bincount(np.asarray(q).ravel(), minlength=k)
    pal = np.array(q.getpalette()[: 3 * k]).reshape(-1, 3)
    return [(pal[i].tolist(), counts[i] / counts.sum()) for i in np.argsort(-counts) if counts[i] / counts.sum() >= min_share]


def share_near(lab_pixels, rgb):
    target = to_lab(np.array(rgb, dtype=float))
    return float((np.linalg.norm(lab_pixels - target, axis=-1) < DELTA_E).mean())


def result_check(garment: bytes, person: bytes, result: bytes):
    """Returns {colour_score 0..1, findings, verdict_ok}."""
    g = Image.open(io.BytesIO(garment)).convert("RGB")
    r = Image.open(io.BytesIO(result)).convert("RGB")
    p = Image.open(io.BytesIO(person)).convert("RGB").resize(r.size)
    small = (256, round(256 * r.height / r.width))
    r_px, p_px = np.asarray(r.resize(small), float), np.asarray(p.resize(small), float)
    diff_px = np.abs(r_px - p_px).mean(-1)
    changed = diff_px > 30  # where the try-on differs from the shopper's photo: the garment area
    region = to_lab(r_px[changed]) if changed.any() else np.zeros((1, 3))
    colours = palette(g)
    found = [share_near(region, rgb) >= FOUND_RATIO * share for rgb, share in colours]
    weight = sum(s for _, s in colours) or 1
    score = sum(s for (_, s), f in zip(colours, found) if f) / weight
    missing = ["#%02x%02x%02x" % tuple(c) for (c, _), f in zip(colours, found) if not f]
    out = []
    if not missing:
        out.append(finding("colour", True, f"All {len(colours)} main colours of the product appear in the try-on."))
    else:
        out.append(finding("colour", False, f"{len(missing)} of the product's {len(colours)} main colours "
                           f"are missing from the try-on ({', '.join(missing)}).", "fail"))
    diff = float(diff_px.mean())
    if diff < CHANGED:
        out.append(finding("applied", False, "The try-on looks almost the same as your photo: "
                           "the garment may not have been placed.", "fail"))
    else:
        out.append(finding("applied", True, "The garment was placed on your photo."))
    if AI_LABEL in result:
        out.append(finding("label", True, "The image file is labelled as AI-generated (IPTC metadata)."))
    else:
        out.append(finding("label", False, "No AI label in the file (the mock never adds one). "
                           "We caption it as AI-generated on screen anyway.", "warn"))
    return {"colour_score": round(score, 3), "findings": out,
            "verdict_ok": all(f["ok"] for f in out if f["id"] in ("colour", "applied"))}


CANT_TELL = [
    "How it fits you. The picture is not drawn to scale, so use the size guide below.",
    "Fine print and logo detail. Zoom in and compare with the product photo yourself.",
    "How the fabric feels, stretches or drapes when you move.",
]
