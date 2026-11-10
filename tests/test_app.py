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
    monkeypatch.setattr(server, "REPLAY", False)
    for store in (server.garment_ids, server.photos, server.sessions, server.jobs):
        store.clear()
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


def test_same_photo_never_waits_twice_and_forget_clears_it(web):
    first = upload(web).json()
    _, j = finish(web, first["session"], "denim-jacket")
    assert j["verdict"] == "shown"
    second = upload(web).json()  # same photo again, a new visit
    assert second["reused"] is True and len(server.client.images) == 2  # photo + garment uploaded once each
    _, again = finish(web, second["session"], "denim-jacket")
    assert again["cached"] is True
    web.delete(f"/api/session/{second['session']}")
    assert web.get(f"/api/photo/{first['session']}").status_code == 410  # forget removes every session of that photo
    assert upload(web).json()["reused"] is False


def test_live_check_fails_loudly_without_a_key():
    import os
    import subprocess
    import sys
    env = {k: v for k, v in os.environ.items() if k != "HTF_TRYON_API_KEY"}
    r = subprocess.run([sys.executable, "scripts/live_check.py"], env=env, capture_output=True, text=True)
    assert r.returncode == 2 and "HTF_TRYON_API_KEY is not set" in r.stderr


def test_live_results_for_sample_figures_are_recorded_and_replayed_free(web, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "RECORDED", tmp_path)
    monkeypatch.setattr(server, "REPLAY", True)
    monkeypatch.setattr(server, "DRAWINGS", set())  # treat ravi as a consenting photo sample, not a drawing
    monkeypatch.setattr(server.client, "mode", "live")  # pretend the result came from the API
    sid = upload(web).json()["session"]  # ravi.png is one of our drawn sample figures
    _, j = finish(web, sid, "breton-tee")
    assert (tmp_path / "ravi__breton-tee.img").read_bytes()[:4] == b"\x89PNG"
    web.delete(f"/api/session/{sid}")
    calls = []
    monkeypatch.setattr(server.client, "run", lambda *a, **k: calls.append(1))
    sid = upload(web).json()["session"]
    _, again = finish(web, sid, "breton-tee")
    assert again["replay"] is True and again["recorded_at"] and not calls
    other = upload(web, data=open("static/models/asha.png", "rb").read()).json()["session"]
    assert server.sessions[other]["sample"] == "asha"


def test_a_shoppers_own_photo_is_never_recorded(web, monkeypatch, tmp_path):
    from PIL import Image
    import io
    monkeypatch.setattr(server, "RECORDED", tmp_path)
    monkeypatch.setattr(server.client, "mode", "live")
    b = io.BytesIO()
    Image.open("static/models/ravi.png").rotate(3).save(b, "PNG")  # any photo that isn't a sample figure
    sid = upload(web, data=b.getvalue()).json()["session"]
    finish(web, sid, "breton-tee")
    assert list(tmp_path.iterdir()) == []


def test_in_live_mode_drawn_figures_use_the_labelled_stand_in(web, monkeypatch):
    calls = []
    monkeypatch.setattr(server.client, "mode", "live")
    monkeypatch.setattr(server.client, "run", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(server, "stand_in", MockTryOnFast())
    sid = upload(web).json()["session"]
    _, j = finish(web, sid, "denim-jacket")
    assert not calls and j["mode"] == "mock" and j["drawing_in_live"] is True


def MockTryOnFast():
    from tryon_client import MockTryOn
    return MockTryOn()


def test_live_budget_stops_spending_and_says_so(web, monkeypatch):
    monkeypatch.setattr(server.client, "mode", "live")
    monkeypatch.setattr(server, "LIVE_BUDGET", 1)
    monkeypatch.setattr(server, "live_spent", [1])
    from PIL import Image
    import io
    b = io.BytesIO()
    Image.open("static/models/ravi.png").rotate(3).save(b, "PNG")
    sid = upload(web, data=b.getvalue()).json()["session"]
    _, j = finish(web, sid, "breton-tee")
    assert j["error"]["code"] == "DEMO_BUDGET" and "size guide" in j["error"]["message"]
