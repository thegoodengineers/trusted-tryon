# Abhijeet: checks and size guide

## Rule for everyone
- Never name any AI assistant or chatbot used to build this: not in commits, co-author lines, comments, docs,
  Devpost text, screenshots or the video. `git log --format=%B | grep -i co-authored` must print nothing.
- Never commit the API key. It goes in your environment as `HTF_TRYON_API_KEY` (or a git-ignored `.env`).
- Every number we show comes from `results/` (re-run `python bench.py`) or a test. No made-up numbers.
- No photos of real people in the repo or the video unless it is you, you are 18+, you say so in your task
  file, and the photo is never committed.
- Branch `yourname/task` -> pull request into `main`. `python -m pytest -q` green before every push.

## Done (10 Nov)
- [x] Photo checks and result checks (`checks.py`), size guide (`fit.py`), 27 tests.

## To do
1. [ ] Once there's a key and 5+ live results: look at each one next to its product photo. Did our colour check agree
   with your eye? Write each case in `results/check-review.md` (garment, our verdict, your verdict). If thresholds
   need moving, change them in `checks.py` with the reason in a comment, and add a test.
2. [ ] Take 5 of your own phone photos (no people; e.g. a chair, a dark room, a blurry shot) and check the photo
   checks warn correctly. Add any miss as a test with a generated image (not the photo).
3. [ ] Size charts in `catalog.json` are realistic but invented. Compare with 2 real brands' public size charts and
   adjust ease ranges if ours are off; note the sources in the commit message.
