# Demo video script

About 2:30, never sped up. `narrate.py`, `record.py` and `assemble.py` read the table below, so edit a line
here and rebuild. Every number comes from `results/` or a test run.

| # | scene | on screen | narration |
|---|---|---|---|
| 1 | card:hook | "It looked different on the website." | You order a kurta because it looked great online. It arrives, it isn't what you expected, and it goes back. |
| 2 | card:problem | What a try-on image is, and isn't | Virtual try-on helps, but the image is drawn by a model. It can get a colour wrong, and it is never drawn to scale, so it can't tell you if a size fits. Nobody tells the shopper that. |
| 3 | card:title | Trusted try-on | This is Trusted try-on: a product page where every try-on is checked against the product photo before you see it, and comes with an honest label. |
| 4 | app:consent | Product page, consent boxes, photo chosen | A shopper adds one photo. Nothing is sent until they confirm they are an adult, that it is their photo, and that they agree to it being processed. Here we use one of our own drawn figures, never a real person. |
| 5 | app:tryon | Steps tick by; the first result fails the colour check and is retried | Before a credit is spent, we check the photo: size, framing, light and sharpness. Then the try-on runs, and we check the result. This first one came back in the wrong colours, so we retried it once, and the second one matched. |
| 6 | app:label | The care label with the stamp | Every result gets a care label, like the one sewn into clothes. What we checked: the colours match, the garment was placed, the file is labelled as AI. What the picture can't tell you: fit, fine print, how fabric moves. And how long it took. |
| 7 | app:compare | Before and after slider | The result is always captioned as an AI-generated preview, and you can compare it with your own photo. |
| 8 | app:fit | Size guide with tape | Fit comes from the size chart, not the picture. Each garment says how much room its cut is meant to have. We check every size, suggest one, and say how sure we are and why. |
| 9 | card:api | How we use the Clothsy AI API | Under the hood is the Clothsy AI try-on API from FabricVTON. The photo is uploaded once and reused for every garment. Each try-on has an idempotency key, so a retry is never charged twice. Every error code becomes a plain sentence, and we read the API's AI label from each result. This recording runs on our labelled mock; with a key, the same code calls the live API. |
| 10 | card:proof | Tests, accessibility, latency | Twenty seven automated tests, including the API client against a fake server that follows the docs. Zero accessibility problems on our page at desktop and phone widths. And our own checks add well under a second around each try-on. |
| 11 | card:close | Trusted try-on, repo link | Trusted try-on. See it on you, and know what the picture can't tell you. Built by The Good Engineers. |
