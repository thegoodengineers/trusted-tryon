# Demo video script

About 2:30, never sped up. `narrate.py`, `record.py` and `assemble.py` read the table below, so edit a line
here and rebuild. Every number comes from `results/` or a test run.

| # | scene | on screen | narration |
|---|---|---|---|
| 1 | card:hook | "It looked different on the website." | You order a kurta because it looked great online. It arrives, it isn't what you expected, and it goes back. |
| 2 | card:problem | What a try-on image is, and isn't | Virtual try-on helps, but the image is drawn by a model. It can get a colour wrong, and it is never drawn to scale, so it can't tell you if a size fits. Nobody tells the shopper that. |
| 3 | card:title | Trusted try-on | This is Trusted try-on: a product page where every try-on is checked against the product photo before you see it, and comes with an honest label. |
| 4 | app:consent | Product page, consent boxes, photo chosen | A shopper adds one photo. Nothing is sent until they confirm they are an adult, that it is their photo, and that they agree to it being processed. Here, a free stock photo from Unsplash, credited on the page. |
| 5 | app:tryon | Steps tick by; the recorded live result appears | Before a credit is spent, we check the photo: size, framing, light and sharpness. Then the Clothsy AI API makes the try-on, about twenty seconds live, and we check the result against the product photo. This one was recorded live and is replayed, so no credit is spent twice. |
| 6 | app:label | The care label: swatches, checks, size tag, In words | Every result gets a care label, like the one sewn into clothes. The product's colours, found in your preview. What the picture can't tell you: fit, fine print, how fabric moves. Your size, and how long it took. And the whole result in words, so a blind shopper gets it too. |
| 7 | app:compare | Before and after slider | The result is always captioned as an AI-generated preview, and you can compare it with your own photo. |
| 8 | app:fit | Size guide with tape | Fit comes from the size chart, not the picture. Every size from extra small to four X L. We check each one, suggest a size, and say how sure we are and why. |
| 9 | card:api | How we use the Clothsy AI API | Under the hood is the Clothsy AI try-on API from FabricVTON. The photo is uploaded once and reused for every garment. Each try-on has an idempotency key, so a retry is never charged twice. Every error code becomes a plain sentence, and we read the API's AI label from each result. Every try-on in this video was made live by the API, recorded byte for byte, and replayed. |
| 10 | card:proof | Tests, accessibility, latency | On the live API: eight of eight try-ons made an image, in about twenty seconds at the median and twenty five at the ninety-fifth percentile, every one labelled as AI. Our check caught a wrong-colour version of every real result. Forty four tests, and zero accessibility problems. |
| 11 | card:close | Trusted try-on, repo link | Trusted try-on. See it on you, and know what the picture can't tell you. Built by The Good Engineers. |
