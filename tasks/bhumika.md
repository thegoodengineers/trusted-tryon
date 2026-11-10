# Bhumika: design and the page

## Rule for everyone
- Never name any AI assistant or chatbot used to build this: not in commits, co-author lines, comments, docs,
  Devpost text, screenshots or the video. `git log --format=%B | grep -i co-authored` must print nothing.
- Never commit the API key. It goes in your environment as `HTF_TRYON_API_KEY` (or a git-ignored `.env`).
- Every number we show comes from `results/` (re-run `python bench.py`) or a test. No made-up numbers.
- No photos of real people in the repo or the video unless it is you, you are 18+, you say so in your task
  file, and the photo is never committed.
- Branch `yourname/task` -> pull request into `main`. `python -m pytest -q` green before every push.

## Done (10 Nov)
- [x] Design references logged in `design/REFS.md`, vibe in `design/VIBE.md`, tokens in `static/theme.css`.
- [x] Page passes axe-core with 0 problems as loaded and with a finished try-on, at 1440/1024/400 px.

## To do
1. [ ] Mobbin needs a sign-in: make a free account, look at 3 real size-guide and product-page flows, add them to
   `design/REFS.md`, and say what we should borrow. Change `static/page.css` only if it clearly helps.
2. [ ] Phone pass at 400 px: `python tools/screenshots.py http://localhost:8790` and look at `docs/screenshots/tryon-400.png`.
   Fix anything cramped. The check must stay at 0 (CI runs it).
3. [ ] Read every sentence on the page as a first-time shopper. Anything unclear: rewrite in plain words.
4. [ ] Optional, only with your written OK here: try the live API on a photo of yourself (18+) once Chirag has
   the key; tell us if the care label made sense on a real result. Never commit the photo.
