import io
import json

import pytest
from PIL import Image

import checks
import fit
from tryon_client import AI_LABEL, MockTryOn

GARMENTS = ["block-print-kurta", "breton-tee", "polka-wrap-dress", "denim-jacket", "logo-sweatshirt"]
CATALOG = {g["id"]: g for g in json.load(open("catalog.json"))}


def png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


@pytest.mark.parametrize("who", ["asha", "ravi"])
@pytest.mark.parametrize("gid", GARMENTS)
def test_colour_check_passes_a_faithful_result_and_fails_a_colour_fault(who, gid):
    person, garment = open(f"static/models/{who}.png", "rb").read(), open(f"static/garments/{gid}.png", "rb").read()
    m = MockTryOn()
    p, g = m.upload(person, "image/png"), m.upload(garment, "image/png")
    assert checks.result_check(garment, person, m.run(p, g, gid).image)["verdict_ok"]
    m.fault_once.add(g)
    assert not checks.result_check(garment, person, m.run(p, g, gid).image)["verdict_ok"]


def test_result_identical_to_photo_is_flagged_as_not_applied():
    person, garment = open("static/models/asha.png", "rb").read(), open("static/garments/breton-tee.png", "rb").read()
    f = {x["id"]: x for x in checks.result_check(garment, person, person)["findings"]}
    assert not f["applied"]["ok"]


def test_ai_label_is_detected_in_the_file_bytes():
    person, garment = open("static/models/asha.png", "rb").read(), open("static/garments/breton-tee.png", "rb").read()
    f = {x["id"]: x for x in checks.result_check(garment, person, person + b"<x>" + AI_LABEL)["findings"]}
    assert f["label"]["ok"]


def test_photo_checks_block_tiny_and_unreadable_and_warn_on_dark():
    assert checks.photo_check(b"not an image")[1] is None
    assert checks.photo_check(png(Image.new("RGB", (200, 300))))[1] is None
    findings, clean = checks.photo_check(png(Image.new("RGB", (600, 900), (10, 10, 10))))
    assert clean is not None and any(f["id"] == "light" and f["level"] == "warn" for f in findings)


def test_photo_is_shrunk_and_exif_dropped():
    img = Image.new("RGB", (2400, 3200), (120, 120, 120))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    b = io.BytesIO()
    img.save(b, "JPEG", exif=exif)
    _, clean = checks.photo_check(b.getvalue())
    out = Image.open(io.BytesIO(clean))
    assert max(out.size) == checks.MAX_SIDE and not out.getexif()


def test_fit_recommends_and_explains():
    kurta = CATALOG["block-print-kurta"]
    r = fit.recommend(kurta, {"chest": 92, "waist": 84, "hip": 96})
    assert r["size"] == "M" and r["confidence"] == "high" and all(x["state"] == "as designed" for x in r["rows"])
    assert fit.recommend(kurta, {"waist": 80})["confidence"] == "none"
    assert fit.recommend(kurta, {"chest": 92})["confidence"] == "medium"
    dress = CATALOG["polka-wrap-dress"]
    low = fit.recommend(dress, {"chest": 84, "waist": 90, "hip": 92})  # waist far bigger than the cut allows
    assert low["confidence"] == "low" and "waist" in low["why"]


def test_every_garment_runs_xs_to_4xl_and_the_edge_is_said_plainly():
    for g in CATALOG.values():
        assert list(g["chart"]) == ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"]
    big = fit.recommend(CATALOG["breton-tee"], {"chest": 112, "waist": 104})
    assert big["size"] == "2XL" and big["confidence"] == "high"
    beyond = fit.recommend(CATALOG["polka-wrap-dress"], {"chest": 150, "waist": 130})
    assert beyond["size"] == "4XL" and "only goes from XS to 4XL" in beyond["why"]


def test_description_names_colours_and_never_claims_fit():
    person, garment = open("static/models/asha.png", "rb").read(), open("static/garments/block-print-kurta.png", "rb").read()
    m = MockTryOn()
    c = checks.result_check(garment, person, m.run(m.upload(person), m.upload(garment), "k").image)
    assert [w["name"] for w in c["swatches"]] == ["mustard", "brick red"]
    text = checks.describe(CATALOG["block-print-kurta"], c, "shown")
    assert "AI-generated preview" in text and "mustard and brick red" in text and "can't show fit" in text
    m2 = MockTryOn()
    g2 = m2.upload(garment)
    m2.fault_once.add(g2)
    bad = checks.result_check(garment, person, m2.run(m2.upload(person), g2, "k").image)
    assert "Missing from the preview" in checks.describe(CATALOG["block-print-kurta"], bad, "held back")
