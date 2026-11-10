"""Cut each recorded scene to its narration, add the voice, join everything: video/build/final.mp4.
Never sped up. Optional background music: put a CC-BY track at video/music.mp3; it is ducked under the voice."""
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
PAUSE = 1.2


def seconds(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout.strip())


def main():
    build = HERE / "build"; build.mkdir(exist_ok=True)
    offsets = json.loads((HERE / "renders" / "offsets.json").read_text())
    parts = []
    for n in sorted(int(k) for k in offsets):
        vo = HERE / "vo" / f"{n:02}.mp3"
        clip = HERE / "renders" / f"{n:02}.webm"
        length = seconds(vo) + PAUSE
        out = build / f"{n:02}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(offsets[str(n)]), "-i", str(clip), "-i", str(vo),
                        "-t", f"{length:.2f}", "-map", "0:v", "-map", "1:a", "-af", "apad",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
                        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(out)], check=True)
        parts.append(out)
    listing = build / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    joined = build / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(joined)], check=True)
    final = build / "final.mp4"
    music = HERE / "music.mp3"
    if music.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
                        "-filter_complex", "[1:a]volume=0.12[m];[0:a][m]sidechaincompress=threshold=0.05:ratio=8[d];[0:a][d]amix=2:duration=first,loudnorm",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(final)], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-af", "loudnorm",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(final)], check=True)
    print(f"{final} · {seconds(final):.1f} seconds")


if __name__ == "__main__":
    main()
