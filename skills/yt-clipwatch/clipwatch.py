#!/usr/bin/env python3
"""clipwatch.py - watch a live Twitch stream, cut a vertical captioned clip at every chat spike.

    python3 clipwatch.py <channel>                       # run it before they go live, leave it on
    python3 clipwatch.py <channel> --k 3 --min-msgs 40   # big channel: stricter spike rule
    python3 clipwatch.py --simulate                      # offline self-test, no Twitch needed
    python3 clipwatch.py --replay clips/<ch>/chat.jsonl --k 3   # try a spike rule on last night's chat

HOW IT WORKS
  RECORD   streamlink pipes the live stream into ffmpeg, which writes 4-second .ts segments named by
           the UTC wall clock. The wall-clock name is what lines video up with chat.
  CHAT     an anonymous IRC connection (nick justinfan*, no account, no token) reads every message.
  SCORE    each bin gets a chat score, not a raw count, so volume alone cannot fake a moment:
             - bots (nightbot, streamelements...) and !commands (giveaway entries) count 0
             - one chatter counts at most --per-user-cap messages per bin (spammers, bots)
             - a reaction (KEKW, LUL, Pog, NO WAY, ???...) counts 1.5; "clip it" counts 3
           and nothing fires for --quiet-after seconds after a raid or a gift-sub bomb, because
           those floods are chat reacting to chat, not to the stream.
  SPIKE    a bin is a spike when its score is at least --min-msgs AND at least --k times the
           median score of the previous --baseline-bins bins. One spike per --cooldown.
  CUT      chat reacts AFTER the moment, so the window is biased backwards: it starts --pre seconds
           before the end of the spiking bin and runs --window seconds.
  CAPTION  whisper (openai-whisper CLI) or whisper-cli (whisper.cpp) writes an .srt; ffmpeg burns it
           into a 1080x1920 frame. No whisper installed -> the clip ships without captions.

WHAT IT DOES NOT DO. It does not post anything, and it cannot rewind: only moments recorded while it
was running can be clipped. Segments older than --keep-minutes are deleted so a long night does not
fill the disk. Needs: ffmpeg + ffprobe, streamlink (pip install streamlink). Optional: whisper.
"""
import argparse, calendar, collections, glob, json, os, queue, random, re, shutil, signal, socket
import statistics, subprocess, sys, threading, time

SEG_SECONDS = 4
STOP = threading.Event()

# Chat bots whose messages say nothing about the stream. Lower-case logins.
BOTS = {"nightbot", "streamelements", "streamlabs", "moobot", "fossabot", "wizebot", "botisimo",
        "sery_bot", "soundalerts", "kofistreambot", "pokemoncommunitygame", "commanderroot"}
# Reactions: case-sensitive on purpose, so "what" in normal chat does not count but "WHAT" does.
REACT = re.compile(r"(?<![\w])(KEKW|LUL|LULW|OMEGALUL|ICANT|Pog|PogU|POGGERS|PogChamp|monkaS|"
                   r"monkaW|Clap|LMAO|LMFAO|NO WAY|WHAT|HOLY|OMG|\?\?\?+)(?![\w])")
CLIP_ASK = re.compile(r"\bclip(ped)? (it|that|this)\b|\bclip it\b", re.I)
# USERNOTICE types after which chat floods for reasons unrelated to what is on screen.
FLOOD_EVENTS = {"raid", "submysterygift"}


def score_bin(msgs, per_user_cap):
    """msgs: [(t, user, text)] -> (score, counted messages, distinct chatters)."""
    per_user = collections.Counter()
    score, counted = 0.0, 0
    for _, user, text in msgs:
        if user in BOTS or text.lstrip().startswith("!"):
            continue
        per_user[user] += 1
        if per_user[user] > per_user_cap:
            continue
        counted += 1
        score += 3.0 if CLIP_ASK.search(text) else 1.5 if REACT.search(text) else 1.0
    return round(score, 1), counted, len(per_user)


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
            # streamlink filters Twitch ads itself now (--twitch-disable-ads is deprecated)
            src = ["streamlink", "--retry-streams", "30", "--retry-max", "0",
                   "--stdout", f"https://www.twitch.tv/{args.channel}", args.quality]
        log("REC  starting", "(simulated source)" if args.simulate else
            f"twitch.tv/{args.channel} - waits here until the channel is live")
        errpath = os.path.join(os.path.dirname(segdir), "streamlink.log")
        errf = open(errpath, "a")
        p1 = subprocess.Popen(src, stdout=subprocess.PIPE, stderr=errf)
        p2 = subprocess.Popen(seg, stdin=p1.stdout, env=env)
        p1.stdout.close()
        seen = {p for _, p in segments(segdir)}
        live = False
        while not STOP.is_set() and p2.poll() is None:
            time.sleep(1)
            if not live and any(p not in seen for _, p in segments(segdir)):
                live = True
                log("REC  live - video is being recorded")
        for p in (p1, p2):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
        errf.close()
        if not STOP.is_set():
            last = ""
            try:
                lines = [l.strip() for l in open(errpath, errors="replace") if l.strip()]
                last = next((l for l in reversed(lines) if "error" in l.lower()), lines[-1] if lines else "")
            except OSError:
                pass
            log("REC  recorder stopped" + (f": {last}" if last else "") +
                "  - retrying in 10s (full output: streamlink.log)")
            time.sleep(10)


def segments(segdir):
    """[(start_epoch, path)] sorted. Start comes from the UTC filename ffmpeg wrote."""
    out = []
    for p in glob.glob(os.path.join(segdir, "*.ts")):
        try:
            st = time.strptime(os.path.basename(p)[:-3], "%Y%m%d-%H%M%S")
            mtime = os.path.getmtime(p)
        except (ValueError, OSError):
            continue
        t = calendar.timegm(st)
        # ffmpeg is asked for UTC names (TZ=UTC), but some builds (Windows) ignore TZ and write
        # local time. A file is written within seconds of its name, so trust whichever reading
        # lands near its modification time.
        if abs(t - mtime) > 900:
            t_local = time.mktime(st)
            if abs(t_local - mtime) < abs(t - mtime):
                t = t_local
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
def parse_irc(line):
    """One Twitch IRC line (with IRCv3 tags) -> (command, user, text, tags), or None."""
    tags = {}
    if line.startswith("@"):
        if " " not in line:
            return None
        tagstr, line = line[1:].split(" ", 1)
        for kv in tagstr.split(";"):
            k, _, v = kv.partition("=")
            tags[k] = v
    if not line.startswith(":"):
        return None
    parts = line[1:].split(" ", 3)
    if len(parts) < 2:
        return None
    prefix, cmd = parts[0], parts[1]
    text = parts[3][1:] if len(parts) == 4 and parts[3].startswith(":") else ""
    return cmd, prefix.split("!", 1)[0].lower(), text, tags


class Chat:
    """Anonymous Twitch IRC reader. Keeps (epoch, user, text) per message and flood events."""

    def __init__(self, channel, logpath):
        self.channel = channel.lower().lstrip("#")
        self.msgs = collections.deque()
        self.events = collections.deque()
        self.lock = threading.Lock()
        self.logf = open(logpath, "a", encoding="utf-8")

    def add(self, t, user, text):
        with self.lock:
            self.msgs.append((t, user, text))
        self.logf.write(json.dumps({"t": round(t, 3), "u": user, "m": text}) + "\n")

    def add_event(self, t, kind):
        with self.lock:
            self.events.append((t, kind))
        self.logf.write(json.dumps({"t": round(t, 3), "event": kind}) + "\n")
        log(f"CHAT {kind} - no clips for the next --quiet-after seconds")

    def window(self, t0, t1):
        """Messages in [t0, t1), and the flood events in [t0, t1)."""
        with self.lock:
            while self.msgs and self.msgs[0][0] < t0 - 3600:
                self.msgs.popleft()
            while self.events and self.events[0][0] < t0 - 3600:
                self.events.popleft()
            msgs = [m for m in self.msgs if t0 <= m[0] < t1]
            events = [e for e in self.events if t0 <= e[0] < t1]
        return msgs, events

    def run_irc(self):
        while not STOP.is_set():
            try:
                s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=10)
                s.settimeout(330)  # twitch PINGs about every 5 minutes
                nick = f"justinfan{random.randint(10000, 99999)}"
                # tags + commands: needed to see raids and gift bombs (USERNOTICE). Still read-only.
                s.sendall(f"CAP REQ :twitch.tv/tags twitch.tv/commands\r\nNICK {nick}\r\n"
                          f"JOIN #{self.channel}\r\n".encode())
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
                            continue
                        msg = parse_irc(line)
                        if not msg:
                            continue
                        cmd, user, text, tags = msg
                        if cmd == "PRIVMSG":
                            self.add(time.time(), user, text)
                        elif cmd == "USERNOTICE" and tags.get("msg-id") in FLOOD_EVENTS:
                            self.add_event(time.time(), tags["msg-id"])
                        elif cmd == "RECONNECT":
                            raise ConnectionError("twitch asked us to reconnect")
            except (OSError, ConnectionError) as e:
                if not STOP.is_set():
                    log(f"CHAT disconnected ({e}); reconnecting in 5s")
                    time.sleep(5)

    def run_simulated(self, t0):
        """A scripted night: a spammer, a giveaway, a raid, then one real moment at t0+50.
        Only the real moment should produce a clip."""
        chatter = ["hi", "lol", "gg", "what is he doing", "nice", "this game looks insane"]
        real = ["KEKW", "NO WAY", "clip it", "OMEGALUL", "WHAT", "???", "LMAO", "that was insane"]
        raided = False
        while not STOP.is_set():
            now, dt = time.time(), time.time() - t0
            if 12 <= dt < 14:      # one account flooding
                self.add(now, "spambot99", "BUY FOLLOWERS cheap")
                rate = 20
            elif 18 <= dt < 20:    # giveaway entries
                self.add(now, f"viewer{random.randint(1, 400)}", "!enter")
                rate = 25
            elif 24 <= dt < 30:    # raid: lots of new people saying hello
                if not raided:
                    self.add_event(now, "raid")
                    raided = True
                self.add(now, f"raider{random.randint(1, 300)}", "RAID HYPE hello chat")
                rate = 10
            elif 50 <= dt < 56:    # the real moment
                self.add(now, f"viewer{random.randint(1, 400)}", random.choice(real))
                rate = 25
            else:
                self.add(now, f"viewer{random.randint(1, 400)}", random.choice(chatter))
                rate = 1
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


WHISPER_CPP_BINS = ("whisper-cli", "whisper-cpp")  # whisper.cpp, newer and older Homebrew names
GGML_DIRS = ["~/.claude/models", "~/models", "~/whisper.cpp/models", "~/whisper-models",
             "~/Downloads", "/opt/homebrew/share/whisper-cpp", "/opt/homebrew/share/whisper-cpp/models",
             "/usr/local/share/whisper-cpp", "/usr/local/share/whisper-cpp/models"]
GGML_PREFER = ["small", "medium", "base", "large-v3-turbo", "large", "tiny"]  # speed vs quality


def find_ggml(language=None):
    """A whisper.cpp model already on this machine, so captions work without a flag.
    English (or no --language): prefer the .en models, which are more accurate for English.
    Any other --language: only multilingual models can do it."""
    english = not language or language.lower().startswith("en")
    found = []
    for d in GGML_DIRS:
        for p in glob.glob(os.path.join(os.path.expanduser(d), "ggml-*.bin")):
            name = os.path.basename(p).lower()
            if "silero" in name or "vad" in name:  # voice-activity models, not speech-to-text
                continue
            try:
                if os.path.getsize(p) < 30 * 1024 * 1024:  # a failed download, not a model
                    continue
            except OSError:
                continue
            is_en = ".en." in name
            if is_en and not english:
                continue
            rank = next((i for i, k in enumerate(GGML_PREFER) if f"ggml-{k}" in name), len(GGML_PREFER))
            found.append((rank, 0 if is_en == english else 1, p))
    return min(found)[2] if found else None


def captioner(args):
    """('whisper.cpp', bin, model) / ('openai-whisper', 'whisper', model) / None."""
    cpp = next((b for b in WHISPER_CPP_BINS if shutil.which(b)), None)
    model = args.whisper_cpp_model or (find_ggml(args.language) if cpp else None)
    if cpp and model:
        return "whisper.cpp", cpp, model  # preferred: much faster than openai-whisper on a laptop
    if shutil.which("whisper"):
        return "openai-whisper", "whisper", args.whisper_model
    return None


def transcribe(args, clip, workdir):
    """Return the path of an .srt next to the clip, or None."""
    base = os.path.splitext(os.path.basename(clip))[0]
    kind, binary, model = args.captioner
    if kind == "openai-whisper":
        cmd = [binary, clip, "--model", model, "--output_format", "srt",
               "--output_dir", workdir, "--verbose", "False"]
        if args.language:
            cmd += ["--language", args.language]
        run(cmd)
    else:
        wav = os.path.join(workdir, base + ".wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-ar", "16000", "-ac", "1", wav])
        cmd = [binary, "-m", model, "-f", wav, "-osrt", "-of", os.path.join(workdir, base)]
        if args.language:
            cmd += ["-l", args.language]
        run(cmd)
        os.remove(wav)
    srt = os.path.join(workdir, base + ".srt")
    return clean_srt(srt) if os.path.exists(srt) else None


SOUND_TAG = re.compile(r"^\s*([\[(*♪][^\]\)]*[\])*♪]\s*)+$")  # [MUSIC], (gunshots), *laughs*, ♪


def clean_srt(path):
    """Drop cues that are only sound labels ([MUSIC], (explosion), [BLANK_AUDIO]): over gameplay
    they are noise on screen. Returns the path, or None when no spoken line is left."""
    blocks = open(path, encoding="utf-8", errors="replace").read().replace("\r", "").split("\n\n")
    kept = []
    for b in blocks:
        lines = [l for l in b.strip().split("\n") if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        text = [l for l in lines[2:] if not SOUND_TAG.match(l)]
        if text:
            kept.append(f"{len(kept) + 1}\n{lines[1]}\n" + "\n".join(text))
    if not kept:
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(kept) + "\n")
    return path


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
        srt = None if args.no_captions or not args.captioner else transcribe(args, raw, workdir)
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
class Detector:
    """The spike rule, shared by the live watcher and --replay so both decide identically."""

    def __init__(self, args):
        self.args = args
        self.history = collections.deque(maxlen=args.baseline_bins)
        self.warmup = max(3, args.baseline_bins // 5)
        self.last_spike = -1e18
        self.quiet_until = -1e18

    def step(self, t_end, msgs, events):
        a = self.args
        for t_ev, _ in events:
            self.quiet_until = max(self.quiet_until, t_ev + a.quiet_after)
        n, counted, uniq = score_bin(msgs, a.per_user_cap)
        base = statistics.median(self.history) if self.history else 0.0
        big = len(self.history) >= self.warmup and n >= a.min_msgs and n >= a.k * max(base, 1.0)
        quiet = t_end <= self.quiet_until
        hot = big and not quiet and t_end - self.last_spike >= a.cooldown
        if hot:
            self.last_spike = t_end
        self.history.append(n)
        line = (f"score {n:6.1f}  ({len(msgs):4d} msgs, {counted:4d} counted, {uniq:3d} chatters)"
                f"   baseline {base:6.1f}"
                + ("   << SPIKE" if hot else "   (ignored: raid/gift flood)" if big and quiet else ""))
        info = {"spike_at": t_end, "score": n, "msgs": len(msgs), "counted": counted,
                "chatters": uniq, "baseline": base, "ratio": round(n / max(base, 1.0), 2)}
        return hot, big and quiet, line, info


def watch(args, chat, jobs, segdir):
    det = Detector(args)
    t_bin = time.time()
    since_prune = 0
    while not STOP.is_set():
        t_end = t_bin + args.bin
        while time.time() < t_end and not STOP.is_set():
            time.sleep(0.2)
        msgs, events = chat.window(t_bin, t_end)
        hot, ignored, line, info = det.step(t_end, msgs, events)
        if args.verbose or hot or ignored:
            log("BIN  " + line)
        if hot:
            start = t_end - args.pre
            info.update(start=start, length=args.window,
                        # wait for the post-roll to be recorded and its segment to be closed
                        ready_at=start + args.window + 2 * SEG_SECONDS + 2)
            jobs.put(info)
        t_bin = t_end
        since_prune += args.bin
        if since_prune >= 60:
            prune(segdir, args.keep_minutes * 60)
            since_prune = 0


def replay(args):
    """Run the spike rule over a saved chat.jsonl. No video, no network, takes seconds."""
    msgs, events = [], []
    with open(args.replay, encoding="utf-8") as f:
        for raw in f:
            try:
                r = json.loads(raw)
            except ValueError:
                continue
            if "event" in r:
                events.append((r["t"], r["event"]))
            elif "u" in r:
                msgs.append((r["t"], r["u"], r.get("m", "")))  # pre-scoring logs have no text
    if not msgs:
        sys.exit(f"no chat messages in {args.replay}")
    msgs.sort()
    events.sort()
    det, spikes, i, j = Detector(args), [], 0, 0
    t_bin, t_last = msgs[0][0], msgs[-1][0]
    while t_bin <= t_last:
        t_end = t_bin + args.bin
        k = i
        while k < len(msgs) and msgs[k][0] < t_end:
            k += 1
        e = j
        while e < len(events) and events[e][0] < t_end:
            e += 1
        hot, ignored, line, info = det.step(t_end, msgs[i:k], events[j:e])
        stamp = time.strftime("%H:%M:%S", time.gmtime(t_end)) + "Z"
        if args.verbose or hot or ignored:
            print(f"{stamp}  {line}")
        if hot:
            spikes.append(info)
        i, j, t_bin = k, e, t_end
    hours = (t_last - msgs[0][0]) / 3600
    print(f"\n{len(msgs)} messages over {hours:.2f} h, {len(events)} raid/gift events -> "
          f"{len(spikes)} clips ({len(spikes) / max(hours, 1e-9):.1f} per hour)")
    for s in sorted(spikes, key=lambda s: -s["ratio"])[:10]:
        print(f"  {time.strftime('%H:%M:%S', time.gmtime(s['spike_at']))}Z  x{s['ratio']:<6} "
              f"score {s['score']:<6} {s['chatters']} chatters")


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
    ap.add_argument("--min-msgs", type=float, default=15,
                    help="a spike needs at least this chat score per bin (about 1 per counted message)")
    ap.add_argument("--per-user-cap", type=int, default=2,
                    help="max messages one chatter adds per bin (default 2; stops spammers)")
    ap.add_argument("--quiet-after", type=float, default=90,
                    help="no clips for this many seconds after a raid or gift-sub bomb (default 90)")
    ap.add_argument("--baseline-bins", type=int, default=30, help="bins in the rolling baseline (default 30 = 5 min)")
    ap.add_argument("--cooldown", type=float, default=60, help="min seconds between clips (default 60)")
    ap.add_argument("--keep-minutes", type=float, default=15, help="delete raw segments older than this")
    ap.add_argument("--layout", choices=["blur", "crop"], default="blur",
                    help="blur = full frame over a blurred fill (keeps facecam/HUD); crop = centre crop")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--whisper-model", default="small", help="openai-whisper model (default small)")
    ap.add_argument("--whisper-cpp-model", help="whisper.cpp model file (ggml-*.bin). Default: found automatically in the usual folders")
    ap.add_argument("--language", help="force caption language, e.g. en (default: auto-detect)")
    ap.add_argument("--verbose", action="store_true", help="print every bin, not only spikes")
    ap.add_argument("--simulate", action="store_true", help="offline self-test: test pattern + fake chat")
    ap.add_argument("--replay", metavar="CHAT_JSONL",
                    help="no recording: run the spike rule over a saved chat.jsonl and list the clips it would cut")
    args = ap.parse_args()

    if args.replay:
        replay(args)
        return

    if args.simulate:
        args.channel = args.channel or "simulated"
        args.bin, args.window, args.pre, args.baseline_bins = 2, 10, 6, 10
        args.min_msgs, args.cooldown, args.quiet_after, args.verbose = 10, 30, 20, True
    if not args.channel:
        ap.error("give a channel, or --simulate")
    need = ["ffmpeg", "ffprobe"] + ([] if args.simulate else ["streamlink"])
    missing = [b for b in need if not shutil.which(b)]
    if missing:
        sys.exit(f"missing: {', '.join(missing)}  (streamlink: pip install streamlink)")
    args.captioner = None if args.no_captions else captioner(args)
    if args.captioner:
        log(f"CAPTION {args.captioner[0]}  ({args.captioner[1]}, model {args.captioner[2]})")
    elif not args.no_captions:
        log("WARN no captions: found neither whisper.cpp (whisper-cli + a ggml-*.bin model) nor "
            "openai-whisper. Already have a model? pass --whisper-cpp-model /path/to/ggml-small.bin")
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
        t0 = time.time()
        threads.append(threading.Thread(target=chat.run_simulated, args=(t0,), daemon=True))
        end = threading.Timer(56 + args.window + 30, stop)  # real moment ends at t0+56
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
