"""Screenshots of the finished try-on state at 1440, 1024 and 400 px, plus an axe-core run on that state
(the a11y check in CI only sees the page as first loaded).

  python tools/screenshots.py http://localhost:8790 --axe path/to/axe.min.js
Writes docs/screenshots/*.png and prints the axe violation count; exits 1 if any.
"""
import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs/screenshots"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--axe", help="axe.min.js to inject (e.g. from node_modules/axe-core)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width, height in ((1440, 1000), (1024, 900), (400, 860)):
            page = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.goto(f"{args.base}/?demo=1")
            page.wait_for_selector("#label:not([hidden])", timeout=60000)
            page.wait_for_timeout(500)
            page.screenshot(path=OUT / f"tryon-{width}.png", full_page=True)
            page.screenshot(path=OUT / f"tryon-{width}-top.png")
            if args.axe:
                page.add_script_tag(path=args.axe)
                v = page.evaluate("async () => (await axe.run(document)).violations.map(x => [x.id, x.nodes.length])")
                print(width, "axe violations:", v)
                bad += len(v)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"horizontal scroll at {width}"
        page = b.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(args.base)
        page.wait_for_selector("#title:not(:empty)")
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "product-page.png")
        b.close()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
