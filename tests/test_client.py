"""The real-API client against a fake Clothsy server (httpx.MockTransport), following the documented contract."""
import json

import httpx
import pytest

from tryon_client import ClothsyClient, MockTryOn, TryOnError


def make(handler):
    return ClothsyClient("clothsy_live_test", transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_upload_start_poll_download():
    seen = {"polls": 0, "keys": []}

    def handler(req):
        assert req.headers["Authorization"] == "Bearer clothsy_live_test"
        if req.url.path.endswith("/images"):
            return httpx.Response(201, json={"id": "img_abc", "expiresAt": "x"})
        if req.url.path.endswith("/tryons") and req.method == "POST":
            body = json.loads(req.content)
            assert body["consent"] is True and body["personImageId"] == "img_abc" and body["garmentImageId"] == "img_g"
            seen["keys"].append(req.headers["Idempotency-Key"])
            return httpx.Response(202, json={"id": "t1", "status": "pending", "pollUrl": "/api/v1/tryons/t1"})
        if req.url.path.endswith("/tryons/t1"):
            seen["polls"] += 1
            if seen["polls"] < 3:
                return httpx.Response(200, json={"id": "t1", "status": "pending"})
            return httpx.Response(200, json={"id": "t1", "status": "success", "resultUrl": "https://api.example/i/r.png"})
        if req.url.path == "/i/r.png":
            return httpx.Response(200, content=b"PNGDATA")
        raise AssertionError(req.url)

    c = make(handler)
    assert c.upload(b"jpeg") == "img_abc"
    r = c.run("img_abc", "img_g", "Kurta")
    assert r.status == "success" and r.image == b"PNGDATA" and r.polls == 3
    assert 8 <= len(seen["keys"][0]) <= 128


def test_429_is_retried_with_the_same_idempotency_key_and_retry_after():
    keys, waits = [], []

    def handler(req):
        if req.method == "POST":
            keys.append(req.headers["Idempotency-Key"])
            if len(keys) == 1:
                return httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "slow down", "code": "RATE_LIMITED"})
            return httpx.Response(202, json={"id": "t2", "status": "pending"})
        return httpx.Response(200, json={"id": "t2", "status": "failed", "resultUrl": None, "message": "did not finish"})

    c = ClothsyClient("k", transport=httpx.MockTransport(handler), sleep=waits.append)
    r = c.run("p", "g", "Tee")
    assert keys[0] == keys[1], "a retry must reuse the key so it is never charged twice"
    assert waits[0] == 7.0 and r.retries == 1
    assert r.status == "failed" and r.message == "did not finish" and r.image is None


@pytest.mark.parametrize("status,code", [(422, "PERSON_PHOTO_REJECTED"), (402, "INSUFFICIENT_CREDITS"), (403, "CONSENT_REQUIRED")])
def test_client_errors_are_not_retried_and_keep_their_code(status, code):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(status, json={"error": "no", "code": code})

    with pytest.raises(TryOnError) as e:
        make(handler).run("p", "g", "Tee")
    assert e.value.code == code and len(calls) == 1


def test_mock_is_labelled_and_needs_no_key():
    m = MockTryOn()
    assert m.mode == "mock"
    png = open("static/models/asha.png", "rb").read()
    r = m.run(m.upload(png, "image/png"), m.upload(open("static/garments/breton-tee.png", "rb").read(), "image/png"), "Tee")
    assert r.status == "success" and r.image[:4] == b"\x89PNG"


def test_a_network_drop_while_polling_does_not_lose_a_paid_result():
    state = {"gets": 0}

    def handler(req):
        if req.method == "POST":
            return httpx.Response(202, json={"id": "t9", "status": "pending"})
        if req.url.path.endswith("/tryons/t9"):
            state["gets"] += 1
            if state["gets"] <= 6:  # longer than one call's own retries: a real outage
                raise httpx.ConnectError("getaddrinfo failed")
            return httpx.Response(200, json={"id": "t9", "status": "success", "resultUrl": "https://api.example/i/x.png"})
        return httpx.Response(200, content=b"IMG")

    r = make(handler).run("p", "g", "Tee")
    assert r.status == "success" and r.image == b"IMG"
