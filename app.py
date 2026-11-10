"""Trusted try-on: a product page whose try-on tells you what it can and can't show.

Privacy: shopper photos and results live only in this process's memory, for one session (30 minutes or
until "Forget my photo"). Nothing is written to disk. The API keeps uploaded photos up to 35 days and
deletes them itself (its docs); we say so on the page.
"""
import json
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
from tryon_client import TryOnError, get_client

HERE = pathlib.Path(__file__).parent
CATALOG = {g["id"]: g for g in json.loads((HERE / "catalog.json").read_text())}
SESSION_TTL = 30 * 60
GARMENT_ID_TTL = 23 * 3600  # API image ids last 24 h
MAX_ATTEMPTS = 2  # one retry when the result fails our check; each attempt costs a credit if it finishes

# What each documented API error means for the shopper. Codes: https://clothsyai.fabricvton.com/docs/api/errors
API_ERRORS = {
    "PERSON_PHOTO_REJECTED": "The try-on service needs a clear photo of exactly one adult. Try another photo of just you.",
    "IMAGE_REJECTED": "The try-on service can't use this photo. Try a different one.",
    "GARMENT_REJECTED": "This item can't be tried on virtually.",
    "INSUFFICIENT_CREDITS": "Try-on is paused for this store right now (no credits left). Use the size guide meanwhile.",
    "RATE_LIMITED": "Lots of try-ons right now. Try again in a minute.",
    "IMAGE_TOO_LARGE": "That photo is too large. Use one under 4 MB.",
    "UNSUPPORTED_IMAGE": "Use a JPEG or PNG photo.",
}

app = FastAPI(title="Trusted try-on")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
client = get_client()
lock = threading.Lock()
sessions, jobs, garment_ids, history = {}, {}, {}, []  # ponytail: in-process memory; one worker only


def expire():
    now = time.time()
    with lock:
        for sid in [s for s, v in sessions.items() if now - v["created"] > SESSION_TTL]:
            sessions.pop(sid)
        for jid in [j for j, v in jobs.items() if now - v["created"] > SESSION_TTL]:
            jobs.pop(jid)


def garment_api_id(gid):
    """Upload each product image once and reuse its id for 23 h (uploads are free, ids last 24 h)."""
    cached = garment_ids.get(gid)
    if cached and time.time() - cached[1] < GARMENT_ID_TTL:
        return cached[0]
    api_id = client.upload((HERE / f"static/garments/{gid}.png").read_bytes(), "image/png")
    garment_ids[gid] = (api_id, time.time())
    if client.mode == "mock" and gid == "block-print-kurta":
        client.fault_once.add(api_id)  # MOCK ONLY: first kurta try-on comes back with wrong colours, to show the retry
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
    return {"mode": client.mode, "credits": credits, "tryons": len(history),
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
    t0 = time.perf_counter()
    try:
        person_id = client.upload(clean, "image/jpeg")
    except TryOnError as e:
        raise HTTPException(502, {"message": API_ERRORS.get(e.code, "The try-on service is unavailable. Try again shortly."), "findings": findings})
    sid = secrets.token_urlsafe(16)
    with lock:
        sessions[sid] = {"created": time.time(), "photo": clean, "person_id": person_id, "results": {}}
    return {"session": sid, "findings": findings, "upload_seconds": round(time.perf_counter() - t0, 3)}


@app.get("/api/photo/{sid}")
def photo_image(sid: str):
    s = sessions.get(sid) or _gone()
    return Response(s["photo"], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.delete("/api/session/{sid}")
def forget(sid: str):
    with lock:
        sessions.pop(sid, None)
        for jid in [j for j, v in jobs.items() if v["session"] == sid]:
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
    if ask.garment in s["results"]:  # same photo, same garment: answer from this session's cache
        job.update(s["results"][ask.garment], cached=True, done=True)
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
        gid = garment_api_id(g["id"])
        for n in range(1, MAX_ATTEMPTS + 1):
            step(job, "Generating your try-on" if n == 1 else "Result didn't match the product. Trying once more")
            res = client.run(s["person_id"], gid, g["title"])
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
    outcome = {"attempts": attempts, "total_seconds": round(total, 2), "mode": client.mode, "cant_tell": checks.CANT_TELL}
    if best:
        res, c = best
        verdict = "shown" if c["verdict_ok"] and len(attempts) == 1 else "retried" if c["verdict_ok"] else "held back"
        outcome.update(image=res.image, findings=c["findings"], colour_score=c["colour_score"], verdict=verdict)
    elif "error" not in job:
        job["error"] = {"code": "FAILED", "message": attempts[-1].get("message") or "The try-on didn't finish. No credit was used."}
    job.update(outcome, done=True)
    if best:
        s["results"][job["garment"]] = {k: v for k, v in outcome.items()}
    history.append({"total": total, "cached": False})


def _t(res):
    return {"seconds": round(sum(res.timings.values()), 2), "polls": res.polls, "http_retries": res.retries}
