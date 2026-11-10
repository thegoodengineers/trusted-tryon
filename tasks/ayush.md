# Ayush: video and screenshots

## Rule for everyone
- Never name any AI assistant or chatbot used to build this: not in commits, co-author lines, comments, docs,
  Devpost text, screenshots or the video. `git log --format=%B | grep -i co-authored` must print nothing.
- Never commit the API key. It goes in your environment as `HTF_TRYON_API_KEY` (or a git-ignored `.env`).
- Every number we show comes from `results/` (re-run `python bench.py`) or a test. No made-up numbers.
- No photos of real people in the repo or the video unless it is you, you are 18+, you say so in your task
  file, and the photo is never committed.
- Branch `yourname/task` -> pull request into `main`. `python -m pytest -q` green before every push.

## Done (10 Nov)
- [x] Video pipeline in `video/` (script.md -> narrate.py -> record.py -> assemble.py), a first full draft built on the mock.
- [x] Screenshots in `docs/screenshots/` from `tools/screenshots.py`.

## To do
1. [ ] Watch `docs/demo-video-draft.mp4` (2:30, built on the mock) (rebuild: `cd video; python narrate.py; python record.py; python assemble.py`).
   It must be 1-3 minutes. Note anything that drags.
2. [ ] After Chirag runs the live benchmark: record one **live** try-on (sample figure, not a real person) and swap it
   in for scene 5, and change the narration on scene 9 to say it's live. Update the proof card numbers only from `results/LATENCY.md`.
3. [ ] **Upload to YouTube** (public or unlisted-but-public per rules: Devpost needs public). Title: "Trusted try-on:
   HackTheFashion Global'26". No music unless it is licensed for it. Send the link to Chirag.
4. [ ] If the API rejects our drawn garments: find 3 product photos with a clear licence (our own shots are best), record
   source and licence in `docs/IMAGES.md`.
