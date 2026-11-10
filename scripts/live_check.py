"""One command once the Clothsy AI key is set: prove the live API works through our whole pipeline, and
measure it.

  $env:HTF_TRYON_API_KEY="clothsy_live_..."      (PowerShell)   or   export HTF_TRYON_API_KEY=...
  python scripts/live_check.py --photo D:/photos/me-full-length.jpg --n 6

The live API only accepts a photo of one real adult: it refuses our drawn sample figures with
PERSON_PHOTO_REJECTED, at no cost. So --photo must be a full-length photo of a team member who is 18+ and
agrees, kept OUTSIDE the repo. It is never copied, saved or committed, and results/ only says "own-photo".

Checks the key and the credits first (free calls), then runs N try-ons of that photo across our garments
(1 credit each; with --retry, 2 if our check retries), each pair again from the cache (free), and a fresh
round once every garment has been tried. Appends to results/latency.csv, rewrites results/LATENCY.md, prints
p50/p95. Exit code: 0 all good, 1 some try-ons errored, 2 no key or no photo, 3 key refused or too few credits.
"""
import argparse
import itertools
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fail(code, msg):
    print("\n" + "=" * 72 + f"\nLIVE CHECK FAILED: {msg}\n" + "=" * 72, file=sys.stderr)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="live try-ons to run (1 credit each)")
    ap.add_argument("--photo", help="photo of a consenting adult (18+), outside the repo; required")
    ap.add_argument("--retry", action="store_true", help="let our check retry a failed result (up to 2 credits each)")
    args = ap.parse_args()
    # Default: one attempt per try-on, so N try-ons cost at most N credits and the verdicts measure first-try accuracy.
    os.environ["HTF_MAX_ATTEMPTS"] = "2" if args.retry else "1"
    if not os.environ.get("HTF_TRYON_API_KEY", "").strip():
        fail(2, "HTF_TRYON_API_KEY is not set. Get a key at https://app.clothsyai.fabricvton.com/login -> "
                "Developer API -> Create API key. Never commit it.")
    if not args.photo or not os.path.isfile(args.photo):
        fail(2, "--photo is required: a full-length photo of a team member who is 18+ and agrees, kept outside the repo. "
                "The live API refuses our drawn sample figures (PERSON_PHOTO_REJECTED).")
    if pathlib.Path(args.photo).resolve().is_relative_to(ROOT):
        fail(2, "keep the photo outside the repo so it can never be committed")
    import bench
    from tryon_client import TryOnError

    server = bench.load_app(real=True)
    if server.client.mode != "live":
        fail(2, "the app did not pick the live client")
    try:
        account = server.client.account()
    except TryOnError as e:
        fail(3, f"the API refused the key ({e.code}: {e.message})")
    credits = account.get("credits")
    print(f"Key accepted. Credits left: {credits} (scope: {account.get('scope')}).")
    need = args.n * (2 if args.retry else 1)
    if credits is not None and credits < need:
        fail(3, f"only {credits} credits; this run can use up to {need}. Lower --n, or ask contact@fabricvton.com for more.")
    pairs = list(itertools.islice(itertools.cycle([(args.photo, g) for g in server.CATALOG]), args.n))
    rows, per_round = [], len(server.CATALOG)
    for i in range(0, len(pairs), per_round):  # each round forgets the photo, so every try-on is measured cold
        rows += bench.run(server, pairs[i:i + per_round])
    bench.write(rows)
    walls = [r["wall_s"] for r in rows]
    errors = [r for r in rows if r["verdict"] not in ("shown", "retried", "held back")]
    walls = [r["wall_s"] for r in rows if r not in errors] or [0]
    print(f"Live: {len(rows)} try-ons, p50 {bench.pct(walls, 50):.2f} s, p95 {bench.pct(walls, 95):.2f} s, "
          f"{len(errors)} errors. Credits now: {server.client.account().get('credits')}.")
    if errors:
        fail(1, "some try-ons errored: " + ", ".join(f"{r['garment']}={r['verdict']}" for r in errors))


if __name__ == "__main__":
    main()
