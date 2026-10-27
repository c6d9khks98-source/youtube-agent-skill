#!/usr/bin/env python3
"""reel.py - put one effect on one vertical clip.

    python3 reel.py list
    python3 reel.py broken-reality pour.mp4 -o reel.mp4 --handle yourcafe --caption "careful, it's hot"
    python3 reel.py messages talk.mp4 -o reel.mp4 --text "how did you edit this??" --text "which app is this"
    python3 reel.py toggles talk.mp4 -o reel.mp4 --text "One clip" --text "One command" --text "Zero editing apps"

Every clip is scaled and cropped to 1080x1920 first. The effects are HTML pages in effects/, drawn
frame by frame by render.cjs, so the look is edited in HTML and CSS, not in this file.

Unlike the other tools in this pack this one is not pure Python: it shells out to ffmpeg and to
Node with Playwright, because it makes video. It tells you which one is missing.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
FIT = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=%d,format=yuv420p" % FPS

EFFECTS = {
    "broken-reality": "The clip's white backdrop becomes a feed post; the pour runs out of the post, over the like row and caption. Needs a clip shot on plain white.",
    "messages": "Notification banners pop in at the top, one per --text. Social proof as a visual: 'how did you edit this??'.",
    "toggles": "A settings card whose switches flip on one by one, one per --text. A three-beat list without a cut.",
}

def need(tool):
    if not shutil.which(tool):
        sys.exit("reel.py needs %s on PATH" % tool)

def duration(clip):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True).stdout
    return float(out.strip())

def render(effect, params, seconds, tmp):
    need("node")
    pj = os.path.join(tmp, "params.json")
    json.dump(params, open(pj, "w"))
    frames = os.path.join(tmp, "frames")
    subprocess.run(["node", os.path.join(HERE, "render.cjs"), os.path.join(HERE, "effects", effect + ".html"),
                    pj, str(FPS), str(seconds), frames], check=True)
    return os.path.join(frames, "frame_%04d.png")

def backdrop_luma(clip):
    """Mean brightness of a 120px patch in the bottom-left corner of frame 1 - the white backdrop."""
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", clip, "-frames:v", "1", "-vf",
                          FIT + ",crop=120:120:0:1800,format=gray,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"YAVG=([0-9.]+)", log)
    return float(m.group(1)) if m else 235.0

def encode(args, graph, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", graph, "-map", "[o]",
                    "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-c:a", "aac", "-shortest", "-movflags", "+faststart", out], check=True)

def broken_reality(a, tmp):
    params = {k: v for k, v in dict(handle=a.handle, caption=a.caption, likes=a.likes,
                                    postColor=a.post_color).items() if v}
    feed = render("broken-reality", params, 0, tmp) % 0
    if a.key:
        lo, hi = a.key
    else:
        bg = backdrop_luma(a.clip)
        lo, hi = bg - 45, bg - 8
        print("backdrop luma %.0f -> key window %.0f..%.0f (override with --key LO HI)" % (bg, lo, hi))
    if hi - lo < 5:
        sys.exit("key window too narrow - the clip's corner is not a white backdrop")
    # Near-white pixels of the clip become the feed; everything darker stays on top of it.
    graph = (f"[0:v]{FIT},split[v][m];"
             f"[m]format=gray,geq=lum='clip((lum(X,Y)-{lo})*255/({hi}-{lo}),0,255)',boxblur=1:1[mask];"
             f"[1:v]scale=1080:1920,format=rgba[ui];[ui][mask]alphamerge[uia];"
             f"[v][uia]overlay=shortest=1,format=yuv420p[o]")
    encode(["-i", a.clip, "-loop", "1", "-i", feed], graph, a.out)

def overlay(effect, params, a, tmp):
    seq = render(effect, params, duration(a.clip), tmp)
    graph = f"[0:v]{FIT}[v];[v][1:v]overlay=format=auto,format=yuv420p[o]"
    encode(["-i", a.clip, "-framerate", str(FPS), "-i", seq], graph, a.out)

def main():
    ap = argparse.ArgumentParser(description="Put one effect on one vertical clip.")
    ap.add_argument("effect", help="effect name, or 'list'")
    ap.add_argument("clip", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--text", action="append", default=[], help="one line per banner / toggle (repeat)")
    ap.add_argument("--start", type=float, help="seconds before the first item appears")
    ap.add_argument("--gap", type=float, help="seconds between items")
    ap.add_argument("--app", help="messages: app name on the banner (default Messages)")
    ap.add_argument("--handle"); ap.add_argument("--caption"); ap.add_argument("--likes")
    ap.add_argument("--post-color", help="broken-reality: post background, e.g. '#e8d9c4'")
    ap.add_argument("--key", nargs=2, type=float, metavar=("LO", "HI"),
                    help="broken-reality: luma window; below LO keeps the clip, above HI shows the feed")
    a = ap.parse_args()

    if a.effect == "list":
        for k, v in EFFECTS.items():
            print(f"{k:16} {v}")
        return
    if a.effect not in EFFECTS:
        sys.exit("unknown effect %r - run: python3 reel.py list" % a.effect)
    if not a.clip or not a.out:
        sys.exit("usage: python3 reel.py %s <clip> -o <out.mp4>" % a.effect)
    need("ffmpeg"); need("ffprobe")

    with tempfile.TemporaryDirectory() as tmp:
        if a.effect == "broken-reality":
            broken_reality(a, tmp)
        else:
            params = {k: v for k, v in dict(items=a.text or None, start=a.start, gap=a.gap,
                                            app=a.app).items() if v is not None}
            overlay(a.effect, params, a, tmp)
    print("wrote", a.out)

if __name__ == "__main__":
    main()
