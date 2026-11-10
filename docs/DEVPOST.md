# Devpost submission text

Paste each block into the matching Devpost field. Numbers marked {FILL} come from `results/LATENCY.md`
after `python bench.py --real` has run with a key; never type a number that a script didn't produce.

## Project name
Trusted try-on

## Elevator pitch (200 characters max)
A virtual try-on that checks every result against the product photo, retries or holds back a bad one, and
tells you what the picture can't: fit comes from the size chart.

## Track
Try-On Commerce. A product-page try-on plus fit and size guidance, built to cut "it looked different"
returns.

## About the project

### Inspiration
Shoppers send clothes back when the thing that arrives isn't what they expected. Virtual try-on should
help, but a try-on image is drawn by a model: it can get a colour wrong, it can quietly hand back your own
photo, and it is never drawn to scale, so a great-looking image says nothing about whether size M fits.
Nobody tells the shopper any of that. FabricVTON lists the same problems as open research (fabric
fidelity through warping, fast enough inference for a live store), so we built the layer a store needs
around the model: trust.

### What it does
A product page (a demo store with five garments) where you add your own photo once and try on anything.
1. **Before a credit is spent**, your photo is checked: readable, big enough, portrait, lit, sharp. It is
   shrunk and re-saved, which strips location data. Nothing leaves the page until you tick that you're 18
   or over and it's your photo, and that you agree to it being processed.
2. **Every result is checked against the product photo** before you see it: are the product's main colours
   there, was the garment actually placed, does the file carry the API's AI-generated label.
3. A result that fails is **retried once**; if it still fails it is **held back**: blurred, with the reason
   and a "Show it anyway" button. Never a silent bad image.
4. Every result comes with a **care label**, like the one sewn into clothes: what we checked, what the
   picture can't tell you (fit, fine print detail, how fabric moves), how long it took, and a stamp:
   Checked, Checked twice, or Held back.
5. **Will it fit?** answered from the garment's size chart and the room each cut is designed to have, not
   from the picture: a suggested size, a confidence level with the reason, and a tape showing where you land.
6. Your photo lives in server memory for the visit only, never on disk here; "Forget my photo" deletes it
   and every result at once.

### How we built it, and how we use the try-on API
Python (FastAPI), plain HTML/CSS/JS, Pillow and NumPy. All API calls are in one module, `tryon_client.py`,
using the Clothsy AI Try-on API as documented:
- `POST /images` uploads the shopper photo **once per visit**; every garment reuses the id. Product images are
  uploaded once and reused for 23 hours.
- `POST /tryons` with a fresh `Idempotency-Key`, `consent: true` and the product title (the docs say the
  title improves placement), then `GET /tryons/{id}` every 2.5 s with progress shown step by step.
- Retries exactly as the docs advise: network errors, 429 and 5xx retried with **the same Idempotency-Key**
  (never charged twice) and the server's `Retry-After`; 400/402/403/413/422 never retried.
- Every documented error code becomes a sentence a shopper understands: `PERSON_PHOTO_REJECTED` asks for a
  clear photo of one adult; `INSUFFICIENT_CREDITS` pauses try-on but keeps the size guide working.
- Our fidelity check reads the API's **machine-readable AI label** (IPTC DigitalSourceType) in each result,
  and the page captions every image as AI-generated, as the API docs ask.
- `GET /account` shows credits left.
- Our checks drive **extra, deliberate API calls**: a failed colour check triggers one retry with a new key.

The colour check: a median-cut palette of the garment, then each main colour must cover enough of the area
that changed between your photo and the result, using CIE76 Delta E in CIELAB.

27 automated tests, including the real-API client against a fake server that follows the documented
contract. GitHub Actions runs the tests, the latency benchmark and an accessibility check: 0 axe-core
problems on our page, as first loaded and with a finished try-on, at desktop, tablet and phone widths.

### Latency and accuracy
`bench.py` runs the full pipeline (upload, try-on, check, retry, cache) and writes every try-on to
`results/latency.csv`.
- Live API: median {FILL} s from click to checked result, p90 {FILL} s; {FILL} of {FILL} shown first time,
  {FILL} retried and passed, {FILL} held back.
- A repeat of the same photo and garment on one visit comes back from memory in {FILL} s.
- Our own overhead around the API (mock run, measured): median 0.44 s for 30 try-ons, including the checks.

### Challenges
The Devpost pages never named the API, so we found the organiser's public developer API ourselves and built
to its documentation. Measuring "is this the same garment" honestly is hard; we kept to checks we can
explain in one sentence, and the label says plainly what we don't check.

### Accomplishments
A try-on that is allowed to say "this one isn't good enough" and "the picture can't tell you if it fits",
and still feels fast.

### What we learned
The most useful sentence on a try-on page is what the image can't tell you.

### What's next
Print and logo checks on the garment region; per-store thresholds from real return data; a Shopify block.

### Built with
python, fastapi, pillow, numpy, httpx, javascript, html, css, clothsy-ai-api, github-actions, axe-core

## Links
- Code: https://github.com/thegoodengineers/trusted-tryon (MIT)
- Video: {FILL YouTube link}
- Testing access: run locally (README, 4 commands). No login. `/?demo=1` runs the whole story with our own
  drawn sample figure. Without a key it runs on a clearly labelled mock; with `HTF_TRYON_API_KEY` it calls
  the real API.

## New or existing project
New. Started 10 Nov 2026, after the submission period opened (6 Nov). Every commit is in the repo history.
