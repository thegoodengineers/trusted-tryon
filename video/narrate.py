"""One narration clip per script line: video/vo/NN.mp3 (free neural voice via edge-tts)."""
import asyncio
import pathlib
import sys

import edge_tts

HERE = pathlib.Path(__file__).parent
VOICE = next((a for a in sys.argv[1:] if not a.startswith("--")), "en-US-AndrewNeural")


def lines():
    """Rows of the script table: (number, scene, narration)."""
    out = []
    for row in (HERE / "script.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            out.append((int(cells[0]), cells[1], cells[3]))
    return out


async def main():
    (HERE / "vo").mkdir(exist_ok=True)
    for n, _, text in lines():
        out = HERE / "vo" / f"{n:02}.mp3"
        if out.exists() and out.stat().st_size > 2000 and "--redo" not in sys.argv:
            continue  # already made; pass --redo after editing the script
        for attempt in range(4):  # the free voice service sometimes returns nothing; try again
            try:
                await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(out))
                break
            except edge_tts.exceptions.NoAudioReceived:
                await asyncio.sleep(2 + attempt * 2)
        else:
            raise SystemExit(f"line {n}: the voice service returned no audio four times; run again later")
        print("voice", n)


if __name__ == "__main__":
    asyncio.run(main())
