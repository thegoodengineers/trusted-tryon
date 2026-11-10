# Chirag: lead, API key, numbers, final submission

Deadline: **25 Nov 2026, 5:00 PM IST** on Devpost. Code freeze **23 Nov, 9 PM IST**. Submit by **24 Nov, 9 PM IST**.

## Rule for everyone
- Never name any AI assistant or chatbot used to build this: not in commits, co-author lines, comments, docs,
  Devpost text, screenshots or the video. `git log --format=%B | grep -i co-authored` must print nothing.
- Never commit the API key. It goes in your environment as `HTF_TRYON_API_KEY` (or a git-ignored `.env`).
- Every number we show comes from `results/` (re-run `python bench.py`) or a test. No made-up numbers.
- No photos of real people in the repo or the video unless it is you, you are 18+, you say so in your task
  file, and the photo is never committed.
- Branch `yourname/task` -> pull request into `main`. `python -m pytest -q` green before every push.

## Done (10 Nov)
- [x] Found the API: Clothsy AI Try-on API (FabricVTON's own), docs and sign-up in the parent `README.md`.
- [x] App end to end on the labelled mock; real client written to the docs and tested against a fake server.
- [x] One-command live check: `python scripts/live_check.py --n 6` (fails loudly without a key).
- [x] Repo public, CI green (tests, mock benchmark, axe-core 0 problems in two states at 3 widths).
- [x] Devpost text draft (`docs/DEVPOST.md`), video script and generated draft video, screenshots.

## Needs you (a person)
1. [ ] **Get the API key (15 min).** https://app.clothsyai.fabricvton.com/login -> sign in with Google ->
   Developer API -> Create API key. Copy it at once (shown once). Then in PowerShell:
   `$env:HTF_TRYON_API_KEY="clothsy_live_..."`. Check: `python -m uvicorn app:app --port 8790`, the header
   must say "live, Clothsy AI, 20 credits left".
2. [ ] **Ask for credits.** Email hackthefashion@fabricvton.com and contact@fabricvton.com: we're a registered
   team, 20 free credits, need ~100 for the latency report and judges' testing. Ask for a **key with its own
   allowance for judges** (the API supports keys with `scope: "key"`), and ask them to confirm Clothsy AI is the required API.
3. [x] Key set and checked (10 Nov): 20 credits. The API refuses our drawn figures (`PERSON_PHOTO_REJECTED`), no credit used.
4. [x] Real numbers (10 Nov): 8 of 8 live try-ons on credited Unsplash sample photos, p50 19.79 s, p95 24.76 s
   (`results/LATENCY.md`). 9 credits used, 11 left. Keep at least 4 for judges' testing.
5. [ ] **Submit on Devpost** (the draft is already started). Paste `docs/DEVPOST.md`, upload
   `docs/screenshots/`, add the YouTube link from Ayush. Submit at least an hour early.
