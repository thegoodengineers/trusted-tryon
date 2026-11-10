# Trusted try-on

[![tests](https://github.com/thegoodengineers/trusted-tryon/actions/workflows/test.yml/badge.svg)](https://github.com/thegoodengineers/trusted-tryon/actions/workflows/test.yml)

**See it on you, and know what the picture can't tell you.** A product page with a virtual try-on that
checks every result against the product photo before you see it, retries or holds back a result that
doesn't match, and answers "will it fit?" from the size chart instead of the picture.

Built for [HackTheFashion Global'26](https://hackthefashion-global26.devpost.com/), **Try-On Commerce** track,
by Chirag, Bhumika, Ayush and Abhijeet (The Good Engineers). Try-on by the
[Clothsy AI Try-on API](https://clothsyai.fabricvton.com/docs/api) from FabricVTON.

![A real try-on from the Clothsy AI API: a sample shopper in our block-print kurta, with the care label below](docs/screenshots/tryon-1440-top.png)

## Real results from the Clothsy AI API (10 Nov 2026)
Measured by `python scripts/live_check.py --sample photo-a,photo-c --n 8` ([`results/LATENCY.md`](results/LATENCY.md)):

| Live try-ons | Made an image | p50, click to checked result | p95 | AI label in the file | Cached repeat |
|---|---|---|---|---|---|
| 8 (2 sample photos x 4 garments) | **8 of 8** | **19.79 s** | **24.76 s** | 8 of 8 | 0.0109 s (median) |

- Our colour check passed 6 and held back 2 at the time. Both held-back images were in fact right (navy stripes
  over a black sweater; a red dress whose re-rendered arms diluted the measure). So we added a second,
  person-only test. Now all 8 real results pass, and a wrong-colour version of every one is held back
  ([`results/RECHECK.md`](results/RECHECK.md), `tests/test_live_recorded.py`). The thresholds were set on these
  same 8 images, so treat that as a first calibration, not a benchmark.
- The API refused our drawn figures (8 of 8, `PERSON_PHOTO_REJECTED`, no credit used), as its safety rule says.
  One accepted try-on was lost to a network drop mid-poll (1 credit). The client now keeps polling through outages.
- Credits: 20 at the start, **9 used** (8 measured + 1 lost), 11 left. The results are kept byte for byte in
  `results/live/`, so the demo, the screenshots and the video replay them without spending again.

**Sample shoppers are free-licence stock photos with credit**: three photos from Unsplash under the
[Unsplash License](https://unsplash.com/license), by [McFollis](https://unsplash.com/@thisismcfollis) (sample
photos 1 and 2) and [Devin Santiago](https://unsplash.com/@ydcphotography) (sample photo 3). Details, links and
checksums: [`assets/CREDITS.md`](assets/CREDITS.md).

## Why it matters
- Shoppers return clothes when the item turns out different from what they expected. A try-on that
  shows the wrong colour, or looks like it fits when the size is wrong, adds to that problem.
- A try-on image is drawn by a model. It shows colour and style on you. It is not drawn to scale, so it
  can't show fit, and nobody tells the shopper that.
- So every result here comes with a **care label**: the product's colours found or missing, what we checked,
  what the picture can't tell you, your size, how long it took, and a stamp: *Checked*, *Checked twice*
  (first try was off, retried) or *Held back*.
- **For everyone:** sizes XS to 4XL with the same fit guidance, and every result described in words for
  screen-reader users, linked to the image and announced when ready.

## For judges, start here
- **One click, no photo needed:** run it (below) and open `http://localhost:8790/?demo=1`. Sample photo 1 is
  tried on with the kurta, and you see the real Clothsy AI result, replayed with no key needed. The size guide is
  filled in too.
- **Without a key**, sample photos replay the recorded live results. Any other photo gets a clearly labelled
  mock (the header says *mock*, and every mock image is stamped "MOCK - not real"). Set `HTF_TRYON_API_KEY`
  and the same code calls the real API.
- **Live in one command:** `python scripts/live_check.py --sample photo-a,photo-c --n 8` (or `--photo <a
  consenting adult's photo, outside the repo>`). It checks the key and credits, runs the try-ons through the full
  pipeline, writes `results/`, prints p50/p95, and exits non-zero on any problem.
- **Tests:** 44 pytest tests, including our check against the 8 real API results,, including the real-API client against a fake server that follows the documented
  contract (retry 429 with `Retry-After` and the same `Idempotency-Key`, no retry on 4xx, poll until done).
- **Accessibility:** 0 axe-core problems on our page, as first loaded and with a finished try-on, at 1440,
  1024 and 400 px (checked in CI with our own Ctrl+A11y tool).
- **Latency:** `results/LATENCY.md`, written only by `bench.py` and `scripts/live_check.py`.

## How it uses the try-on API
All API calls live in [`tryon_client.py`](tryon_client.py).
1. **Before spending a credit**, the photo is checked here: readable, big enough, framing, light, blur.
   It's shrunk to 1600 px and re-saved, which removes location data. Nothing is sent without two ticks:
   18 or over and it's your photo; agree to processing.
2. `POST /images` uploads your photo **once per visit**; every garment reuses the id. Product images are
   uploaded once and their ids reused for 23 hours (they last 24).
3. `POST /tryons` with a fresh `Idempotency-Key`, `consent: true` and the product title; then
   `GET /tryons/{id}` every 2.5 s. Network errors, 429 and 5xx are retried with the same key (never charged
   twice), honouring `Retry-After`; 4xx are not retried.
4. **Fidelity check** on the result ([`checks.py`](checks.py)): the product's main colours (median-cut
   palette of the garment) must appear in the area that changed (CIE76 Delta E < 14 in CIELAB); the result
   must differ from your photo (the API can return your own photo when no garment was placed); and we look
   for the API's machine-readable AI label (IPTC `compositeWithTrainedAlgorithmicMedia`) in the file.
5. **One retry** if the colours don't match, keeping the better result. If it still fails, the result is
   *held back*: blurred, with an honest reason and a "Show it anyway" button.
6. Every documented error code becomes a plain sentence (`PERSON_PHOTO_REJECTED` -> "needs a clear photo of
   exactly one adult"; `INSUFFICIENT_CREDITS` -> try-on paused, size guide still works).
7. `GET /account` shows credits left in the header.
8. The same photo (matched by its SHA-256) is uploaded once and each garment is generated once: adding the same
   photo again, or replaying the demo, comes back from memory instantly. Forget my photo clears all of it.

## Fit from the size chart ([`fit.py`](fit.py))
Each product has a size chart and the room ("ease") it is designed to have at chest, waist and hip: a wrap
dress sits close, a denim jacket is roomy. We compare your measurements with every size, pick the one that
has the designed room for the most measurements, and say how sure we are: *high* (all of 2+ measurements
match), *medium* (only chest given), *low* (no size fits everything, and which measurement is off). The tape
under it shows where you land.

## Privacy and images
- Shopper photos and results live only in the server's memory for the visit (30 minutes, or **Forget my
  photo**). Never written to disk here. The API keeps uploads up to 35 days, then deletes them (its docs).
- Every result is captioned "AI-generated try-on. The real fit may differ." and its alt text says so.
- **Images:** the product shots are our own drawings ([`tools/make_assets.py`](tools/make_assets.py)). The sample
  shoppers are **free-licence stock photos from Unsplash, with credit** ([`assets/CREDITS.md`](assets/CREDITS.md)).
  Try-on results in `results/live/` were made from them by the Clothsy AI API. Font: Archivo (SIL OFL).

## Run it
```
git clone https://github.com/thegoodengineers/trusted-tryon.git
cd trusted-tryon
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app:app --port 8790
```
Open http://localhost:8790 (or `/?demo=1`). For the real API, get a key (below) and before starting:
`$env:HTF_TRYON_API_KEY="clothsy_live_..."` (PowerShell) or `export HTF_TRYON_API_KEY=...`.

**Getting a key:** sign in at https://app.clothsyai.fabricvton.com/login, open **Developer API**, click
**Create API key** (shown once). New accounts get 20 free credits; one credit per finished try-on, failed
ones refunded. Never commit the key.

## Measuring latency
```
python bench.py            # mock: our pipeline only
python bench.py --real --n 1   # live API: each round tries 5 garments on 2 figures (up to 20 credits)
```
Appends to `results/latency.csv` (wall time, attempts, verdict, colour score, cached-repeat time, polls,
retries, commit, machine) and rewrites `results/LATENCY.md`.

## Known limits (honest status)
- **Small live sample:** 8 live try-ons, 2 photos, 4 garments. That is enough to show the pipeline works on the
  real API and to calibrate our check, not to benchmark the API. CI never has a key and always runs on the mock.
- The Unsplash License covers use of the photos but doesn't document a model release. We use them only as
  clearly credited sample shoppers ([`assets/CREDITS.md`](assets/CREDITS.md)).
- **Hosted testing on our key costs credits:** each live try-on of a judge's own photo costs 1 credit (2 if our
  check retries). Set `HTF_LIVE_BUDGET` to cap live try-ons per server run; over the cap the page says so and
  the size guide keeps working. Sample figures never spend a credit.
- The colour check catches wrong colours and "nothing placed", not smeared prints or broken logos. The care
  label says so and asks the shopper to compare the zoom with the product photo.
- Thresholds (blur, light, Delta E) are set on our own images and a few phone photos, not a dataset.
- We can't verify age; we ask, and the API itself rejects photos that don't clearly show one adult.
- In-memory sessions: one server process. Fine for a demo; a real store would use a shared store.
- The mock makes the kurta's first try-on after each server start come back with wrong colours on purpose,
  so the retry path can be seen without a key.

## Layout
`app.py` web API and job runner · `tryon_client.py` Clothsy client and labelled mock · `checks.py` photo and
result checks · `fit.py` size guidance · `catalog.json` products and size charts · `static/` page ·
`bench.py` latency · `tests/` · `tools/` asset drawing and screenshots · `docs/` submission kit ·
`design/` references and vibe · `tasks/` who does what.

MIT licence.
