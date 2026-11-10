"""The one place that talks to the try-on API.

Real API: Clothsy AI Try-on API by FabricVTON (https://clothsyai.fabricvton.com/docs/api).
  POST /images        upload a JPEG/PNG (<= 4 MB), get an img_ id valid 24 h. Free.
  POST /tryons        start a try-on (Idempotency-Key header, consent: true). 1 credit if it finishes.
  GET  /tryons/{id}   poll every 2-3 s until success or failed.
  GET  /account       credits left. Free.
We follow the docs' retry advice: retry 429/500/502/503 and timeouts with the SAME Idempotency-Key
(never charged twice), honour Retry-After, back off 1, 2, 4 s; never retry 400/401/402/403/413/422.

MockTryOn is a clearly labelled stand-in, used only by the tests and when HTF_TRYON_API_KEY is not set.
It pastes the garment onto the photo with Pillow. It is NOT a try-on model and every image it makes
carries a "MOCK" tag, so it can never be mistaken for a real result.
"""
import io
import os
import time
import uuid
from dataclasses import dataclass, field

import httpx
from PIL import Image, ImageDraw

BASE = "https://api.clothsyai.fabricvton.com/api/v1"
RETRYABLE = {429, 500, 502, 503}
AI_LABEL = b"compositeWithTrainedAlgorithmicMedia"  # IPTC DigitalSourceType the API writes into every result


class TryOnError(Exception):
    """An API error with the documented code, so the UI can explain it honestly."""

    def __init__(self, status, code, message):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


@dataclass
class Result:
    status: str  # success | failed
    image: bytes | None = None
    message: str = ""
    tryon_id: str = ""
    timings: dict = field(default_factory=dict)  # seconds per stage: upload, generate, download
    polls: int = 0
    retries: int = 0  # HTTP retries the client made (429/5xx/timeouts)


class ClothsyClient:
    mode = "live"

    def __init__(self, api_key, base=BASE, transport=None, sleep=time.sleep, poll_every=2.5, give_up_after=180):
        self.http = httpx.Client(base_url=base, headers={"Authorization": f"Bearer {api_key}"},
                                 timeout=30, transport=transport)
        self.sleep, self.poll_every, self.give_up_after = sleep, poll_every, give_up_after
        self.retries = 0

    def _call(self, method, path, attempts=4, **kw):
        for i in range(attempts):
            try:
                r = self.http.request(method, path, **kw)
            except httpx.TransportError:
                if i == attempts - 1:
                    raise TryOnError(0, "NETWORK", "Couldn't reach the try-on service.")
                self.retries += 1
                self.sleep(2 ** i)
                continue
            if r.status_code in RETRYABLE and i < attempts - 1:
                self.retries += 1
                self.sleep(float(r.headers.get("Retry-After", 2 ** i)))
                continue
            if r.status_code >= 400:
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                raise TryOnError(r.status_code, body.get("code", "HTTP_%d" % r.status_code), body.get("error", r.text[:200]))
            return r

    def account(self):
        return self._call("GET", "/account").json()

    def upload(self, data: bytes, content_type="image/jpeg"):
        ext = "png" if content_type == "image/png" else "jpg"
        r = self._call("POST", "/images", files={"file": (f"image.{ext}", data, content_type)})
        return r.json()["id"]

    def start(self, person_id, garment_id, title, idempotency_key):
        body = {"personImageId": person_id, "garmentImageId": garment_id, "title": title[:120], "consent": True}
        return self._call("POST", "/tryons", json=body, headers={"Idempotency-Key": idempotency_key}).json()

    def wait(self, tryon_id):
        polls, deadline = 0, time.monotonic() + self.give_up_after
        while True:
            try:
                body = self._call("GET", f"/tryons/{tryon_id}").json()
            except TryOnError as e:
                # The try-on keeps running (and is paid for) even if our connection drops, so keep polling
                # until the deadline instead of losing a result we already paid for.
                if e.code != "NETWORK" or time.monotonic() > deadline:
                    raise
                self.sleep(self.poll_every)
                continue
            polls += 1
            if body["status"] != "pending":
                return body, polls
            if time.monotonic() > deadline:
                return {"status": "failed", "message": "The try-on took too long. Please try again."}, polls
            self.sleep(self.poll_every)

    def run(self, person_id, garment_id, title, idempotency_key=None):
        """Start one try-on and wait for it. Images must already be uploaded (ids)."""
        self.retries = 0
        t0 = time.perf_counter()
        started = self.start(person_id, garment_id, title, idempotency_key or str(uuid.uuid4()))
        body, polls = self.wait(started["id"])
        t1 = time.perf_counter()
        res = Result(body["status"], message=body.get("message", ""), tryon_id=started["id"], polls=polls)
        if body["status"] == "success":
            res.image = self._call("GET", body["resultUrl"], attempts=6).content  # paid for: try hard; the URL lives 24 h
        res.timings = {"generate": t1 - t0, "download": time.perf_counter() - t1}
        res.retries = self.retries
        return res


class MockTryOn:
    """LABELLED MOCK. Not a try-on model: pastes the garment on the photo so the app runs without a key."""

    mode = "mock"

    def __init__(self, delay=0.0):
        self.delay = delay  # set >0 to make the UI's progress states visible in a demo
        self.images, self.retries = {}, 0
        self.fault_once = set()  # garment ids whose first try-on comes back with shifted colours (demo of the retry path)

    def account(self):
        return {"credits": None, "scope": "mock"}

    def upload(self, data: bytes, content_type="image/jpeg"):
        image_id = "mock_img_" + uuid.uuid4().hex
        self.images[image_id] = Image.open(io.BytesIO(data)).convert("RGB")
        return image_id

    def run(self, person_id, garment_id, title, idempotency_key=None):
        t0 = time.perf_counter()
        if self.delay:
            time.sleep(self.delay)
        person, garment = self.images[person_id].copy(), self.images[garment_id]
        g = garment.crop(_content_box(garment))
        w, h = person.size
        box = (int(w * 0.24), int(h * 0.22), int(w * 0.76), int(h * 0.22) + int(w * 0.52 * g.height / g.width))
        g = g.resize((box[2] - box[0], box[3] - box[1]))
        if garment_id in self.fault_once:
            self.fault_once.discard(garment_id)
            g = Image.merge("RGB", g.split()[::-1])  # swap red and blue: a deliberate colour fault
        person.paste(g, box[:2], _content_mask(g))
        d = ImageDraw.Draw(person)
        d.rectangle((0, 0, 130, 34), fill=(0, 0, 0))
        d.text((10, 10), "MOCK - not real", fill=(255, 255, 255))
        out = io.BytesIO()
        person.save(out, "PNG")
        return Result("success", out.getvalue(), tryon_id="mock_" + uuid.uuid4().hex,
                      timings={"generate": time.perf_counter() - t0, "download": 0.0})


def _content_mask(img):
    from checks import garment_mask  # one implementation, shared with the fidelity check

    small = img.convert("RGB").resize((256, max(1, round(256 * img.height / img.width))), Image.NEAREST)
    return Image.fromarray(garment_mask(small).astype("uint8") * 255).resize(img.size)


def _content_box(img):
    return _content_mask(img).getbbox() or (0, 0, *img.size)


def get_client():
    key = os.environ.get("HTF_TRYON_API_KEY", "").strip()
    return ClothsyClient(key) if key else MockTryOn(delay=float(os.environ.get("HTF_MOCK_DELAY", "1.5")))
