# Every image we use, where it came from, and its licence

| File | What | Source | Licence |
|---|---|---|---|
| `static/garments/*.png` (5) | Product shots: kurta, Breton tee, wrap dress, denim jacket, logo sweatshirt | Drawn by our code, `tools/make_assets.py` | MIT (this repo) |
| `static/models/photo-a.jpg`, `photo-b.jpg`, `photo-c.jpg` | Sample shoppers | Unsplash: McFollis (1, 2), Devin Santiago (3); see `assets/CREDITS.md` | [Unsplash License](https://unsplash.com/license) |
| `results/live/*.img` | Try-on results made from the sample shoppers | Clothsy AI API, 10 Nov 2026; kept byte for byte (they carry the API's AI label) | Generated from the photos above |
| `static/models/asha.png`, `ravi.png` | Flat drawn figures, used only by tests (the live API refuses drawings) | Drawn by our code, `tools/make_assets.py` | MIT (this repo) |
| `docs/screenshots/*.png` | Screenshots of our own app | `tools/screenshots.py` | MIT (this repo) |
| `static/fonts/Archivo.ttf` | Typeface | Omnibus-Type via google/fonts | SIL Open Font License 1.1 (`static/fonts/OFL.txt`) |
| "TGE" logo on the sweatshirt | Our team's initials, drawn as text | `tools/make_assets.py` | MIT |

The only photos of real people are the three credited Unsplash stock photos. A team member's own photo may
be used for testing only with their written OK in `tasks/<name>.md`, and must never be committed. Design references in `design/refs/` are other people's work,
kept locally for reference only and git-ignored (see `design/REFS.md`).
