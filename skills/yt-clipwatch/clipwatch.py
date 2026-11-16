#!/usr/bin/env python3
"""clipwatch.py - watch a live Twitch stream, cut a vertical captioned clip at every chat spike.

    python3 clipwatch.py <channel>                       # run it before they go live, leave it on
    python3 clipwatch.py <channel> --k 3 --min-msgs 40   # big channel: stricter spike rule
    python3 clipwatch.py --simulate                      # offline self-test, no Twitch needed

HOW IT WORKS
  RECORD   streamlink pipes the live stream into ffmpeg, which writes 4-second .ts segments named by
           the UTC wall clock. The wall-clock name is what lines video up with chat.
  CHAT     an anonymous IRC connection (nick justinfan*, no account, no token) counts messages.
  SPIKE    every --bin seconds: a bin is a spike when it has at least --min-msgs messages AND at
           least --k times the median of the previous --baseline-bins bins. One spike per --cooldown.
  CUT      chat reacts AFTER the moment, so the window is biased backwards: it starts --pre seconds
           before the end of the spiking bin and runs --window seconds.
  CAPTION  whisper (openai-whisper CLI) or whisper-cli (whisper.cpp) writes an .srt; ffmpeg burns it
           into a 1080x1920 frame. No whisper installed -> the clip ships without captions.

WHAT IT DOES NOT DO. It does not post anything, and it cannot rewind: only moments recorded while it
was running can be clipped. Segments older than --keep-minutes are deleted so a long night does not
fill the disk. Needs: ffmpeg + ffprobe, streamlink (pip install streamlink). Optional: whisper.
"""
import argparse, calendar, collections, glob, json, os, queue, random, shutil, signal, socket
import statistics, subprocess, sys, threading, time

SEG_SECONDS = 4
STOP = threading.Event()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- record
def recorder(args, segdir):
    """Keep a streamlink | ffmpeg segmenter running until STOP. Restarts when the stream drops."""
    env = dict(os.environ, TZ="UTC")
    pattern = os.path.join(segdir, "%Y%m%d-%H%M%S.ts")
    seg = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-map", "0:v:0?",
           "-map", "0:a:0?", "-c", "copy", "-f", "segment", "-segment_time", str(SEG_SECONDS),
           "-reset_timestamps", "1", "-strftime", "1", pattern]
    while not STOP.is_set():
        if args.simulate:
            src = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re",
                   "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                   "-c:v", "libx264", "-preset", "ultrafast", "-g", "30", "-c:a", "aac",
                   "-f", "mpegts", "pipe:1"]
        else:
            # --retry-streams: poll until the channel goes live; --retry-max 0 = keep polling forever
            src = ["streamlink", "--retry-streams", "30", "--retry-max", "0", "--twitch-disable-ads",
                   "--stdout", f"https://www.twitch.tv/{args.channel}", args.quality]
        log("REC  starting", "(simulated source)" if args.simulate else f"twitch.tv/{args.channel}")
        p1 = subprocess.Popen(src, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(seg, stdin=p1.stdout, env=env)
        p1.stdout.close()
        while not STOP.is_set() and p2.poll() is None:
            time.sleep(1)
        for p in (p1, p2):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
        if not STOP.is_set():
            log("REC  stream ended or dropped; waiting for it to come back")
            time.sleep(10)


def segments(segdir):
    """[(start_epoch, path)] sorted. Start comes from the UTC filename ffmpeg wrote."""
    out = []
    for p in glob.glob(os.path.join(segdir, "*.ts")):
        try:
            t = calendar.timegm(time.strptime(os.path.basename(p)[:-3], "%Y%m%d-%H%M%S"))
        except ValueError:
            continue
        out.append((t, p))
    return sorted(out)


def prune(segdir, keep_seconds):
    cutoff = time.time() - keep_seconds
    for t, p in segments(segdir)[:-2]:
        if t < cutoff:
            try:
                os.remove(p)
            except OSError:
                pass


# ---------------------------------------------------------------- chat
class Chat:
    """Anonymous Twitch IRC reader. Appends (epoch, user) for every chat message."""

    def __init__(self, channel, logpath):
        self.channel = channel.lower().lstrip("#")
        self.msgs = collections.deque()
        self.lock = threading.Lock()
        self.logf = open(logpath, "a", encoding="utf-8")

    def add(self, t, user):
        with self.lock:
            self.msgs.append((t, user))
        self.logf.write(json.dumps({"t": round(t, 3), "u": user}) + "\n")

    def count(self, t0, t1):
        with self.lock:
            while self.msgs and self.msgs[0][0] < t0 - 3600:
                self.msgs.popleft()
            hits = [u for t, u in self.msgs if t0 <= t < t1]
        return len(hits), len(set(hits))

    def run_irc(self):
        while not STOP.is_set():
            try:
                s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=10)
                s.settimeout(330)  # twitch PINGs about every 5 minutes
                nick = f"justinfan{random.randint(10000, 99999)}"
                s.sendall(f"NICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
                log(f"CHAT joined #{self.channel} anonymously as {nick}")
                buf = b""
                while not STOP.is_set():
                    data = s.recv(65536)
                    if not data:
                        raise ConnectionError("server closed the connection")
                    buf += data
                    *lines, buf = buf.split(b"\r\n")
                    for raw in lines:
                        line = raw.decode("utf-8", "replace")
                        if line.startswith("PING"):
                            s.sendall(("PONG" + line[4:] + "\r\n").encode())
                        elif " PRIVMSG #" in line and line.startswith(":"):
                            self.add(time.time(), line[1:line.find("!")])
            except (OSError, ConnectionError) as e:
                if not STOP.is_set():
                    log(f"CHAT disconnected ({e}); reconnecting in 5s")
                    time.sleep(5)

    def run_simulated(self, burst_at):
        """~1 msg/s background chatter, one 6-second burst of ~25 msg/s at burst_at."""
        while not STOP.is_set():
            now = time.time()
            rate = 25 if burst_at <= now < burst_at + 6 else 1
            self.add(now, f"viewer{random.randint(1, 400)}")
            time.sleep(random.expovariate(rate))


# ---------------------------------------------------------------- cut + caption
def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, **kw)


def cut_raw(segdir, start, length, out):
    """Concatenate the segments covering [start, start+length) and trim to the exact window."""
    segs = segments(segdir)
    use = [(t, p) for i, (t, p) in enumerate(segs)
           if t < start + length and (segs[i + 1][0] if i + 1 < len(segs) else t + SEG_SECONDS) > start]
    if not use:
        return "no recorded segments cover this window (was the recorder running?)"
    lst = out + ".txt"
    with open(lst, "w") as f:
        for _, p in use:
            f.write(f"file '{os.path.abspath(p)}'\n")
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lst, "-ss", f"{max(0.0, start - use[0][0]):.2f}", "-t", str(length),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", out])
    os.remove(lst)
    return None if r.returncode == 0 else r.stderr.strip()[-400:]


def transcribe(args, clip, workdir):
    """Return the path of an .srt next to the clip, or None."""
    base = os.path.splitext(os.path.basename(clip))[0]
    if shutil.which("whisper"):
        cmd = ["whisper", clip, "--model", args.whisper_model, "--output_format", "srt",
               "--output_dir", workdir, "--verbose", "False"]
        if args.language:
            cmd += ["--language", args.language]
        run(cmd)
    elif shutil.which("whisper-cli") and args.whisper_cpp_model:
        wav = os.path.join(workdir, base + ".wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-ar", "16000", "-ac", "1", wav])
        cmd = ["whisper-cli", "-m", args.whisper_cpp_model, "-f", wav, "-osrt",
               "-of", os.path.join(workdir, base)]
        if args.language:
            cmd += ["-l", args.language]
        run(cmd)
        os.remove(wav)
    srt = os.path.join(workdir, base + ".srt")
    return srt if os.path.exists(srt) and os.path.getsize(srt) > 0 else None


def render(args, raw, srt, out):
    """1080x1920 vertical, captions burned in. Layout 'blur' keeps the whole frame; 'crop' fills it."""
    if args.layout == "crop":
        v = "[0:v]crop=trunc(ih*9/32)*2:ih,scale=1080:1920,setsar=1"
    else:
        v = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=20:2[bg];[b]scale=1080:-2[fg];"
             "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    if srt:
        style = ("FontName=Arial,FontSize=16,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 "BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=70")
        v += f",subtitles={os.path.basename(srt)}:force_style='{style}'"
    v += "[v]"
    # cwd = the srt's folder, so the subtitles filter gets a bare filename with nothing to escape
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", os.path.abspath(raw),
             "-filter_complex", v, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset",
             "veryfast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", os.path.abspath(out)],
            cwd=os.path.dirname(srt) if srt else None)
    return None if r.returncode == 0 else r.stderr.strip()[-400:]


def cutter(args, segdir, outdir, jobs):
    workdir = os.path.join(outdir, "work")
    os.makedirs(workdir, exist_ok=True)
    while True:
        job = jobs.get()
        if job is None:
            return
        while time.time() < job["ready_at"] and not STOP.is_set():
            time.sleep(0.5)
        name = time.strftime("%Y%m%d-%H%M%S", time.gmtime(job["spike_at"])) + f"_x{job['ratio']:.1f}"
        raw = os.path.join(workdir, name + ".mp4")
        err = cut_raw(segdir, job["start"], job["length"], raw)
        if err:
            log(f"CUT  {name} failed: {err}")
            continue
        srt = None if args.no_captions else transcribe(args, raw, workdir)
        final = os.path.join(outdir, name + ".mp4")
        err = render(args, raw, srt, final)
        if err:
            log(f"CUT  {name} render failed: {err}")
            continue
        os.remove(raw)
        job.update(file=final, captions=bool(srt))
        with open(os.path.join(outdir, "clips.jsonl"), "a") as f:
            f.write(json.dumps(job) + "\n")
        log(f"CLIP {final}  ({'captioned' if srt else 'NO captions'})")


# ---------------------------------------------------------------- spike loop
def watch(args, chat, jobs, segdir):
    history = collections.deque(maxlen=args.baseline_bins)
    warmup = max(3, args.baseline_bins // 5)
    last_spike = 0.0
    t_bin = time.time()
    since_prune = 0
    while not STOP.is_set():
        t_end = t_bin + args.bin
        while time.time() < t_end and not STOP.is_set():
            time.sleep(0.2)
        n, uniq = chat.count(t_bin, t_end)
        base = statistics.median(history) if history else 0.0
        hot = (len(history) >= warmup and n >= args.min_msgs and n >= args.k * max(base, 1.0)
               and t_end - last_spike >= args.cooldown)
        if args.verbose or hot:
            log(f"BIN  {n:4d} msgs / {uniq:3d} chatters   baseline {base:6.1f}" + ("   << SPIKE" if hot else ""))
        if hot:
            last_spike = t_end
            start = t_end - args.pre
            jobs.put({"spike_at": t_end, "msgs": n, "chatters": uniq, "baseline": base,
                      "ratio": round(n / max(base, 1.0), 2), "start": start, "length": args.window,
                      # wait for the post-roll to be recorded and its segment to be closed
                      "ready_at": start + args.window + 2 * SEG_SECONDS + 2})
        history.append(n)
        t_bin = t_end
        since_prune += args.bin
        if since_prune >= 60:
            prune(segdir, args.keep_minutes * 60)
            since_prune = 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("channel", nargs="?", help="twitch channel login, e.g. the part after twitch.tv/")
    ap.add_argument("--out", default="clips", help="output folder (default ./clips)")
    ap.add_argument("--quality", default="best", help="streamlink quality: best, 1080p60, 720p60...")
    ap.add_argument("--bin", type=float, default=10, help="seconds per chat count (default 10)")
    ap.add_argument("--window", type=float, default=30, help="clip length in seconds (default 30)")
    ap.add_argument("--pre", type=float, default=22,
                    help="clip starts this many seconds before the end of the spiking bin (default 22)")
    ap.add_argument("--k", type=float, default=2.5, help="spike = k x the baseline median (default 2.5)")
    ap.add_argument("--min-msgs", type=int, default=15, help="a spike needs at least this many msgs per bin")
    ap.add_argument("--baseline-bins", type=int, default=30, help="bins in the rolling baseline (default 30 = 5 min)")
    ap.add_argument("--cooldown", type=float, default=60, help="min seconds between clips (default 60)")
    ap.add_argument("--keep-minutes", type=float, default=15, help="delete raw segments older than this")
    ap.add_argument("--layout", choices=["blur", "crop"], default="blur",
                    help="blur = full frame over a blurred fill (keeps facecam/HUD); crop = centre crop")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--whisper-model", default="small", help="openai-whisper model (default small)")
    ap.add_argument("--whisper-cpp-model", help="path to a ggml model, used if only whisper-cli is installed")
    ap.add_argument("--language", help="force caption language, e.g. en (default: auto-detect)")
    ap.add_argument("--verbose", action="store_true", help="print every bin, not only spikes")
    ap.add_argument("--simulate", action="store_true", help="offline self-test: test pattern + fake chat")
    args = ap.parse_args()

    if args.simulate:
        args.channel = args.channel or "simulated"
        args.bin, args.window, args.pre, args.baseline_bins = 2, 10, 6, 10
        args.min_msgs, args.cooldown, args.verbose = 10, 30, True
    if not args.channel:
        ap.error("give a channel, or --simulate")
    need = ["ffmpeg", "ffprobe"] + ([] if args.simulate else ["streamlink"])
    missing = [b for b in need if not shutil.which(b)]
    if missing:
        sys.exit(f"missing: {', '.join(missing)}  (streamlink: pip install streamlink)")
    if not args.no_captions and not (shutil.which("whisper") or
                                      (shutil.which("whisper-cli") and args.whisper_cpp_model)):
        log("WARN no whisper found - clips will have no captions (pip install openai-whisper)")
    if args.pre > args.window:
        ap.error("--pre cannot be larger than --window")

    outdir = os.path.abspath(os.path.join(args.out, args.channel))
    segdir = os.path.join(outdir, "segments")
    os.makedirs(segdir, exist_ok=True)
    chat = Chat(args.channel, os.path.join(outdir, "chat.jsonl"))
    jobs = queue.Queue()

    def stop(*_):
        STOP.set()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    threads = [threading.Thread(target=recorder, args=(args, segdir), daemon=True)]
    if args.simulate:
        burst = time.time() + 30
        threads.append(threading.Thread(target=chat.run_simulated, args=(burst,), daemon=True))
        end = threading.Timer(burst - time.time() + args.window + 30, stop)
        end.daemon = True
        end.start()
    else:
        threads.append(threading.Thread(target=chat.run_irc, daemon=True))
    cut_thread = threading.Thread(target=cutter, args=(args, segdir, outdir, jobs))
    for t in threads + [cut_thread]:
        t.start()
    log(f"WATCH clips -> {outdir}   (Ctrl-C to stop)")
    watch(args, chat, jobs, segdir)
    jobs.put(None)  # finish clips already queued, then exit
    cut_thread.join()
    threads[0].join(15)  # let the recorder terminate streamlink/ffmpeg instead of orphaning them
    log("DONE")


if __name__ == "__main__":
    main()
