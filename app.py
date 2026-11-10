"""Trusted try-on: a product page whose try-on tells you what it can and can't show.

Privacy: shopper photos and results live only in this process's memory, for one session (30 minutes or
until "Forget my photo"). Nothing is written to disk. The API keeps uploaded photos up to 35 days and
deletes them itself (its docs); we say so on the page.
"""
import hashlib
import json
import os
import pathlib
import secrets
import statistics
import threading
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import checks
import fit
from tryon_client import MockTryOn, TryOnError, get_client

HERE = pathlib.Path(__file__).parent
CATALOG = {g["id"]: g for g in json.loads((HERE / "catalog.json").read_text())}
SESSION_TTL = 30 * 60
GARMENT_ID_TTL = 23 * 3600  # API image ids last 24 h
MAX_ATTEMPTS = int(os.environ.get("HTF_MAX_ATTEMPTS", "2"))  # 2 = one retry when our check fails; each finished attempt costs a credit
# Recorded live results for our own drawn sample figures (never a shopper's photo): saved byte for byte from the
# API the first time, then replayed for free and labelled as recorded. Judges and the demo never spend a credit twice.
RECORDED = HERE / "results/live"
REPLAY = os.environ.get("HTF_REPLAY", "1") != "0"
# For a hosted demo on our own key: at most this many live try-ons per server run (0 = no cap), so judges'
# testing can't use up the credits. Over the cap the page says so, and the size guide keeps working.
LIVE_BUDGET = int(os.environ.get("HTF_LIVE_BUDGET", "0"))
live_spent = [0]


def _sample_hashes():
    out = {}
    for f in sorted((HERE / "static/models").glob("*.png")):
        _, clean = checks.photo_check(f.read_bytes())
        out[hashlib.sha256(clean).hexdigest()] = f.stem
    return out


SAMPLES = _sample_hashes()


def recorded(sample, garment):
    meta, img = RECORDED / f"{sample}__{garment}.json", RECORDED / f"{sample}__{garment}.img"
    if not (meta.exists() and img.exists()):
        return None
    return {**json.loads(meta.read_text()), "image": img.read_bytes()}


def record(sample, garment, outcome):
    RECORDED.mkdir(parents=True, exist_ok=True)
    (RECORDED / f"{sample}__{garment}.img").write_bytes(outcome["image"])  # exact bytes: keeps the API's AI label
    meta = {k: v for k, v in outcome.items() if k != "image"} | {"recorded_at": time.strftime("%Y-%m-%d")}
    (RECORDED / f"{sample}__{garment}.json").write_text(json.dumps(meta, indent=1))

# What each documented API error means for the shopper. Codes: https://clothsyai.fabricvton.com/docs/api/errors
API_ERRORS = {
    "PERSON_PHOTO_REJECTED": "The try-on service needs a clear photo of exactly one adult. Try another photo of just you.",
    "IMAGE_REJECTED": "The try-on service can't use this photo. Try a different one.",
    "GARMENT_REJECTED": "This item can't be tried on virtually.",
    "DEMO_BUDGET": "This demo's live try-ons are used up for today. The size guide and the sample figures still work.",
    "INSUFFICIENT_CREDITS": "Try-on is paused for this store right now (no credits left). Use the size guide meanwhile.",
    "RATE_LIMITED": "Lots of try-ons right now. Try again in a minute.",
    "IMAGE_TOO_LARGE": "That photo is too large. Use one under 4 MB.",
    "UNSUPPORTED_IMAGE": "Use a JPEG or PNG photo.",
}

app = FastAPI(title="Trusted try-on")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
client = get_client()
# Our sample figures are flat drawings. The live API rightly refuses them (PERSON_PHOTO_REJECTED: not a photo of
# one adult), so in live mode they go to the labelled stand-in; only real photos reach the API.
DRAWINGS = {"asha", "ravi"}
stand_in = MockTryOn(delay=float(os.environ.get("HTF_MOCK_DELAY", "1.5")))


def engine_for(sample):
    return stand_in if client.mode == "live" and sample in DRAWINGS else client
lock = threading.Lock()
sessions, jobs, garment_ids, history = {}, {}, {}, []  # ponytail: in-process memory; one worker only
# The same photo (by SHA-256 of its cleaned bytes) shares one entry: one upload, one result per garment.
# So a shopper who adds the same photo again, or a demo replayed within 30 minutes, never waits twice.
# sessions[sid] points at the shared entry; "Forget my photo" removes the entry and every session using it.
photos = {}


def expire():
    now = time.time()
    with lock:
        for sha in [h for h, v in photos.items() if now - v["created"] > SESSION_TTL]:
            photos.pop(sha)
        for sid in [s for s, v in sessions.items() if v["sha"] not in photos]:
            sessions.pop(sid)
        for jid in [j for j, v in jobs.items() if now - v["created"] > SESSION_TTL]:
            jobs.pop(jid)


def garment_api_id(gid, eng):
    """Upload each product image once and reuse its id for 23 h (uploads are free, ids last 24 h)."""
    cached = garment_ids.get((eng.mode, gid))
    if cached and time.time() - cached[1] < GARMENT_ID_TTL:
        return cached[0]
    api_id = eng.upload((HERE / f"static/garments/{gid}.png").read_bytes(), "image/png")
    garment_ids[(eng.mode, gid)] = (api_id, time.time())
    if eng.mode == "mock" and gid == "block-print-kurta":
        eng.fault_once.add(api_id)  # MOCK ONLY: first kurta try-on comes back with wrong colours, to show the retry
    return api_id


@app.get("/")
def home():
    return FileResponse(HERE / "static/index.html")


@app.head("/")
def home_head():
    return Response()


@app.get("/api/status")
def status():
    try:
        credits = client.account().get("credits")
    except TryOnError:
        credits = None
    times = [h["total"] for h in history if not h["cached"]]
    return {"mode": client.mode, "credits": credits, "tryons": len(history), "recorded": len(list(RECORDED.glob("*.json"))),
            "median_seconds": round(statistics.median(times), 2) if times else None}


@app.get("/api/catalog")
def catalog():
    return list(CATALOG.values())


class FitAsk(BaseModel):
    garment: str
    body: dict = {}


@app.post("/api/fit")
def fit_guide(ask: FitAsk):
    if ask.garment not in CATALOG:
        raise HTTPException(404, "No such product.")
    return fit.recommend(CATALOG[ask.garment], ask.body)


@app.post("/api/photo")
async def photo(photo: UploadFile = File(...), consent: str = Form(""), adult: str = Form("")):
    if consent != "true" or adult != "true":
        raise HTTPException(400, "Tick both boxes first: you're 18 or over, it's your photo, and you agree to it being processed.")
    expire()
    findings, clean = checks.photo_check(await photo.read())
    if clean is None:
        raise HTTPException(422, {"message": findings[-1]["text"], "findings": findings})
    sha = hashlib.sha256(clean).hexdigest()
    sid = secrets.token_urlsafe(16)
    if sha in photos:  # same photo already uploaded on this server in the last 30 minutes: reuse it
        with lock:
            sessions[sid] = photos[sha]
        return {"session": sid, "findings": findings, "upload_seconds": 0.0, "reused": True}
    t0 = time.perf_counter()
    try:
        eng = engine_for(SAMPLES.get(sha))
        person_id = eng.upload(clean, "image/jpeg")
    except TryOnError as e:
        raise HTTPException(502, {"message": API_ERRORS.get(e.code, "The try-on service is unavailable. Try again shortly."), "findings": findings})
    with lock:
        photos[sha] = {"created": time.time(), "sha": sha, "photo": clean, "person_id": person_id, "results": {},
                       "sample": SAMPLES.get(sha), "engine": eng}
        sessions[sid] = photos[sha]
    return {"session": sid, "findings": findings, "upload_seconds": round(time.perf_counter() - t0, 3), "reused": False}


@app.get("/api/photo/{sid}")
def photo_image(sid: str):
    s = sessions.get(sid) or _gone()
    return Response(s["photo"], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.delete("/api/session/{sid}")
def forget(sid: str):
    with lock:
        entry = sessions.pop(sid, None)
        if entry:
            photos.pop(entry["sha"], None)
            gone = {s for s, v in sessions.items() if v is entry} | {sid}
            for s in gone:
                sessions.pop(s, None)
        else:
            gone = {sid}
        for jid in [j for j, v in jobs.items() if v["session"] in gone]:
            jobs.pop(jid)
    return {"forgotten": True}


class TryAsk(BaseModel):
    session: str
    garment: str


@app.post("/api/tryon")
def start(ask: TryAsk):
    s = sessions.get(ask.session) or _gone()
    if ask.garment not in CATALOG:
        raise HTTPException(404, "No such product.")
    jid = uuid.uuid4().hex
    job = {"created": time.time(), "session": ask.session, "garment": ask.garment, "steps": [], "done": False}
    with lock:
        jobs[jid] = job
    rec = REPLAY and s.get("sample") and recorded(s["sample"], ask.garment)
    if ask.garment in s["results"]:  # same photo, same garment: answer from memory
        job.update(s["results"][ask.garment], cached=True, done=True)
        history.append({"total": 0.0, "cached": True})
    elif rec:  # our sample figure, already tried on live: replay the recorded result, no credit spent
        job.update(rec, cached=True, replay=True, done=True)
        history.append({"total": 0.0, "cached": True})
    else:
        threading.Thread(target=run_job, args=(job, s), daemon=True).start()
    return {"job": jid}


@app.get("/api/tryon/{jid}")
def poll(jid: str):
    job = jobs.get(jid) or _gone()
    return {k: v for k, v in job.items() if k not in ("image",)}


@app.get("/api/tryon/{jid}/image")
def result_image(jid: str):
    job = jobs.get(jid) or _gone()
    if not job.get("image"):
        raise HTTPException(404, "No image for this try-on.")
    return Response(job["image"], media_type="image/png" if job["image"][:4] == b"\x89PNG" else "image/jpeg",
                    headers={"Cache-Control": "no-store"})


def _gone():
    raise HTTPException(410, "This session has ended and your photo is gone. Add your photo again.")


def step(job, text, state="running"):
    if job["steps"] and job["steps"][-1]["state"] == "running":
        job["steps"][-1]["state"] = "done"
    job["steps"].append({"text": text, "state": state})


def run_job(job, s):
    g = CATALOG[job["garment"]]
    garment_bytes = (HERE / f"static/garments/{g['id']}.png").read_bytes()
    t0 = time.perf_counter()
    attempts, best = [], None
    try:
        step(job, "Preparing the product image")
        eng = s["engine"]
        gid = garment_api_id(g["id"], eng)
        for n in range(1, MAX_ATTEMPTS + 1):
            step(job, "Generating your try-on" if n == 1 else "Result didn't match the product. Trying once more")
            if eng.mode == "live" and LIVE_BUDGET:
                with lock:
                    if live_spent[0] >= LIVE_BUDGET:
                        raise TryOnError(429, "DEMO_BUDGET", "live budget used")
                    live_spent[0] += 1
            res = eng.run(s["person_id"], gid, g["title"])
            if res.status != "success":
                attempts.append({"n": n, "status": "failed", "message": res.message, **_t(res)})
                continue
            step(job, "Checking the result against the product photo")
            c = checks.result_check(garment_bytes, s["photo"], res.image)
            attempts.append({"n": n, "status": "success", "colour_score": c["colour_score"], "ok": c["verdict_ok"], **_t(res)})
            if best is None or c["colour_score"] > best[1]["colour_score"]:
                best = (res, c)
            if c["verdict_ok"]:
                break
    except TryOnError as e:
        job["error"] = {"code": e.code, "message": API_ERRORS.get(e.code, "The try-on service is unavailable. Try again shortly.")}
    total = time.perf_counter() - t0
    if job["steps"]:
        job["steps"][-1]["state"] = "done"
    outcome = {"attempts": attempts, "total_seconds": round(total, 2), "mode": s["engine"].mode, "cant_tell": checks.CANT_TELL,
               "drawing_in_live": s["engine"] is stand_in and client.mode == "live"}
    if best:
        res, c = best
        verdict = "shown" if c["verdict_ok"] and len(attempts) == 1 else "retried" if c["verdict_ok"] else "held back"
        outcome.update(image=res.image, findings=c["findings"], colour_score=c["colour_score"], verdict=verdict,
                       swatches=c["swatches"], description=checks.describe(g, c, verdict))
    elif "error" not in job:
        job["error"] = {"code": "FAILED", "message": attempts[-1].get("message") or "The try-on didn't finish. No credit was used."}
    job.update(outcome, done=True)
    if best:
        s["results"][job["garment"]] = {k: v for k, v in outcome.items()}
        if s["engine"].mode == "live" and s.get("sample"):
            record(s["sample"], job["garment"], outcome)
    history.append({"total": total, "cached": False})


def _t(res):
    return {"seconds": round(sum(res.timings.values()), 2), "polls": res.polls, "http_retries": res.retries}
