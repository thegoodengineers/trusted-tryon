"""End to end through the web API, on the mock (no key)."""
import time

import pytest
from fastapi.testclient import TestClient

import app as server

PHOTO = open("static/models/ravi.png", "rb").read()


@pytest.fixture
def web(monkeypatch):
    from tryon_client import MockTryOn
    monkeypatch.setattr(server, "client", MockTryOn())
    server.garment_ids.clear()
    return TestClient(server.app)


def upload(web, consent="true", adult="true", data=PHOTO):
    return web.post("/api/photo", files={"photo": ("p.png", data, "image/png")}, data={"consent": consent, "adult": adult})


def finish(web, sid, garment):
    job = web.post("/api/tryon", json={"session": sid, "garment": garment}).json()["job"]
    for _ in range(100):
        j = web.get(f"/api/tryon/{job}").json()
        if j["done"]:
            return job, j
        time.sleep(0.05)
    raise AssertionError("try-on never finished")


def test_nothing_is_sent_without_consent(web):
    assert upload(web, consent="false").status_code == 400
    assert upload(web, adult="false").status_code == 400
    assert server.client.images == {}


def test_unusable_photo_is_refused_before_spending_a_credit(web):
    r = upload(web, data=b"nope")
    assert r.status_code == 422 and server.client.images == {}


def test_full_flow_cache_and_forget(web):
    assert web.get("/api/status").json()["mode"] == "mock"
    sid = upload(web).json()["session"]
    job, j = finish(web, sid, "breton-tee")
    assert j["verdict"] == "shown" and len(j["attempts"]) == 1 and j["cant_tell"]
    assert web.get(f"/api/tryon/{job}/image").content[:4] == b"\x89PNG"
    _, again = finish(web, sid, "breton-tee")
    assert again["cached"] is True
    assert web.delete(f"/api/session/{sid}").status_code == 200
    assert web.get(f"/api/photo/{sid}").status_code == 410
    assert web.get(f"/api/tryon/{job}").status_code == 410


def test_mock_colour_fault_is_caught_and_retried(web):
    sid = upload(web).json()["session"]
    _, j = finish(web, sid, "block-print-kurta")
    assert j["verdict"] == "retried"
    assert [a["ok"] for a in j["attempts"]] == [False, True]


def test_api_error_becomes_an_honest_message(web, monkeypatch):
    from tryon_client import TryOnError

    def refuse(*a, **k):
        raise TryOnError(422, "PERSON_PHOTO_REJECTED", "no")
    sid = upload(web).json()["session"]
    monkeypatch.setattr(server.client, "run", refuse)
    _, j = finish(web, sid, "denim-jacket")
    assert "exactly one adult" in j["error"]["message"]


def test_fit_endpoint(web):
    r = web.post("/api/fit", json={"garment": "denim-jacket", "body": {"chest": 96, "waist": 88}}).json()
    assert r["size"] and r["confidence"] in ("high", "medium", "low")
