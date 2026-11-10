"""Our check against the real Clothsy AI results we recorded (results/live/), no API calls: every real result
passes, and the same image with a wrong-colour garment is held back."""
import io
import pathlib
import sys

import pytest

import checks

sys.path.insert(0, "tools")
from recheck_live import wrong_colour  # noqa: E402

RECORDED = sorted(pathlib.Path("results/live").glob("*.img"))


@pytest.mark.parametrize("img", RECORDED, ids=[p.stem for p in RECORDED])
def test_real_result_passes_and_its_wrong_colour_twin_is_held_back(img):
    sample, garment = img.stem.split("__")
    _, photo = checks.photo_check(next(pathlib.Path("static/models").glob(f"{sample}.*")).read_bytes())
    product = pathlib.Path(f"static/garments/{garment}.png").read_bytes()
    result = img.read_bytes()
    real = checks.result_check(product, photo, result)
    assert real["verdict_ok"] and {f["id"]: f["ok"] for f in real["findings"]}["label"]  # API's AI label is in the file
    twin = io.BytesIO()
    wrong_colour(result, photo).save(twin, "JPEG", quality=92)
    assert not checks.result_check(product, photo, twin.getvalue())["verdict_ok"]
