"""Record every scene of video/script.md at 1280x720 for exactly its narration length (plus a short pause).

Cards come from video/scenes.html. App scenes drive the real app, which this script starts itself on the
labelled mock (fresh process, so the kurta's deliberate first-try colour fault shows the retry).
Run narrate.py first so the clip lengths are known. Output: video/renders/NN.webm and offsets.json.
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
APP = "http://localhost:8791"
SIZE = {"width": 1280, "height": 720}
PAUSE = 1.2


def lines():
    out = []
    for row in (HERE / "script.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            out.append((int(cells[0]), cells[1]))
    return out


def seconds(n):
    mp3 = HERE / "vo" / f"{n:02}.mp3"
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                                capture_output=True, text=True).stdout.strip())


def glide(page, selector, ms=1400, top=40):
    page.evaluate("""([s, ms, top]) => { const el = document.querySelector(s); if (!el) return;
        const y = el.getBoundingClientRect().top + scrollY - top, from = scrollY, t0 = performance.now();
        const step = t => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2;
          scrollTo(0, from + (y - from) * e); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }""", [selector, ms, top])
    page.wait_for_timeout(ms + 100)


def try_on(page, slow=True):
    page.goto(APP, wait_until="networkidle")
    page.wait_for_timeout(800 if slow else 0)
    page.check("#adult"); page.wait_for_timeout(500 if slow else 0)
    page.check("#consent"); page.wait_for_timeout(500 if slow else 0)
    page.set_input_files("#photo", str(ROOT / "static/models/photo-a.jpg")); page.wait_for_timeout(600 if slow else 0)
    page.click("#go")


def app_consent(page):
    page.goto(APP, wait_until="networkidle"); page.wait_for_timeout(1500)
    glide(page, "#tryHead", 1400, 200); page.wait_for_timeout(700)
    page.check("#adult"); page.wait_for_timeout(900)
    page.check("#consent"); page.wait_for_timeout(900)
    page.set_input_files("#photo", str(ROOT / "static/models/photo-a.jpg"))


def app_tryon(page):
    try_on(page)
    glide(page, "#tryHead", 900, 200)
    page.wait_for_selector("#label:not([hidden])", timeout=60000)


def done(page):
    try_on(page, slow=False)
    page.wait_for_selector("#label:not([hidden])", timeout=60000)
    page.evaluate("scrollTo(0, 0)")


def app_label(page):
    done(page); page.wait_for_timeout(600); glide(page, "#label", 1800)
    page.wait_for_timeout(5500); glide(page, ".tags", 1600, 120)


def app_compare(page):
    done(page); page.wait_for_timeout(600)
    for v in list(range(100, 0, -4)) + list(range(0, 61, 4)):
        page.evaluate("v => { const s = document.getElementById('slider'); s.value = v; s.dispatchEvent(new Event('input')); }", v)
        page.wait_for_timeout(70)


def app_fit(page):
    page.goto(APP, wait_until="networkidle"); glide(page, "#fitHead", 1200)
    for k, v in (("#chest", "92"), ("#waist", "84"), ("#hip", "96")):
        page.type(k, v, delay=140); page.wait_for_timeout(250)
    page.click("#fitForm button"); page.wait_for_timeout(800); glide(page, "#fitHead", 600)


APP_SCENES = {"consent": app_consent, "tryon": app_tryon, "label": app_label, "compare": app_compare, "fit": app_fit}


def main():
    (HERE / "renders").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "HTF_TRYON_API_KEY"} | {"HTF_MOCK_DELAY": "2.2"}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", "8791"], cwd=ROOT, env=env)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(APP); break
            except OSError:
                time.sleep(0.5)
        record()
    finally:
        server.terminate()


def record():
    offsets = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for n, scene in lines():
            kind, name = scene.split(":")
            length = seconds(n) + PAUSE
            ctx = browser.new_context(viewport=SIZE, record_video_dir=str(HERE / "renders" / "tmp"), record_video_size=SIZE)
            page = ctx.new_page()
            t0 = time.time()
            if kind == "card":
                page.goto((HERE / "scenes.html").resolve().as_uri() + f"?scene={name}"); page.wait_for_timeout(200)
                start = time.time() - t0
            else:
                start = time.time() - t0 + 0.2
                APP_SCENES[name](page)
            remaining = start + length - (time.time() - t0)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))
            video = page.video
            ctx.close()
            target = HERE / "renders" / f"{n:02}.webm"
            pathlib.Path(video.path()).replace(target)
            offsets[n] = round(start if kind == "card" else max(0.0, start - 0.2), 2)
            print(f"scene {n} {scene}: {length:.1f}s")
    (HERE / "renders" / "offsets.json").write_text(json.dumps(offsets, indent=1))


if __name__ == "__main__":
    main()
