---
name: yt-clipwatch
description: >-
  Watch a live Twitch stream and cut a vertical, captioned 30-second clip at
  every chat spike, while it is still live. Use for "clip this stream live",
  "watch this streamer and clip the moments", "auto-clip twitch", "set up the
  clip watcher".
---

# yt-clipwatch

Every clipper waits for the VOD, downloads the whole night, and scans it after the fact. They all
find the same moments, and they all find them late. This one records from the first second, reads
chat while it happens, and has the clip cut a minute after the moment.

The catch, said up front: **it only works while the stream is live.** It cannot rewind. If it was
not running, the moment is gone.

## Setup (once)

```bash
pip install streamlink openai-whisper    # whisper is optional: without it clips ship uncaptioned
# ffmpeg from your package manager: brew install ffmpeg / apt install ffmpeg
python3 clipwatch.py --simulate          # 2-minute offline self-test, no Twitch involved
```

Ask the user which channel. Then run it on a machine that stays awake for the whole stream. A
laptop that sleeps loses the night.

```bash
python3 clipwatch.py <channel>                 # start it before they go live; it waits for them
python3 clipwatch.py <channel> --verbose       # print every 10-second chat count, to tune the rule
```

Clips land in `clips/<channel>/` as 1080x1920 MP4s named `<UTC time>_x<multiple>.mp4`. The multiple
is how far that bin beat the baseline, so sorting by it puts the biggest moments first.
`clips.jsonl` has every spike's numbers, and `chat.jsonl` keeps the raw chat timeline.

## What counts as a spike

Chat volume alone is easy to fake, so every 10-second bin gets a **score** instead of a count:

- chat bots and `!commands` (giveaway entries) count zero
- one chatter adds at most 2 messages per bin, so a spammer cannot trip it
- reactions (`KEKW`, `LUL`, `Pog`, `NO WAY`, `???`...) count 1.5, and "clip it" counts 3
- for 90 seconds after a **raid** or a **gift-sub bomb**, nothing fires. Those floods are chat
  reacting to chat, not to the stream. The cost: a real moment inside that window is missed.

`--simulate` plays a spammer, a giveaway, a raid and then one real moment, and should produce
exactly one clip. If it produces more, the filters are broken.

## Tuning: the only part that needs judgement

| symptom | change |
| --- | --- |
| clips every minute on a huge channel | raise `--k` (3-4) and `--min-msgs` (40-100+) |
| nothing fires on a small channel | lower `--min-msgs` (5-8) and `--k` (2) |
| the moment is cut off at the start | raise `--pre` (chat reacts 5-15 s late, after the stream delay) |
| the same moment clipped twice | raise `--cooldown` |
| a real moment right after a raid was skipped | lower `--quiet-after` (default 90 s) |
| one excited regular never moves the score | raise `--per-user-cap` (default 2 messages per bin) |
| facecam or HUD lost in the crop | keep `--layout blur` (the default). `crop` fills the frame but cuts the sides |

Look at the first night's `clips.jsonl` before you change anything: the chat count is evidence,
your memory of the stream is not.

Then tune on the recording, not on the next stream. `--replay` runs the same spike rule over a saved
chat log in seconds, with no video and no network, and lists the clips it would have cut and how many
per hour:

```bash
python3 clipwatch.py --replay clips/<channel>/chat.jsonl              # what the defaults pick
python3 clipwatch.py --replay clips/<channel>/chat.jsonl --k 3.5 --min-msgs 40
```

Change one setting at a time until the clip count per hour is one you would actually review, and
the moments you remember are in the list. Replay bins start at the first message, so times can sit
a few seconds off the live run's.

## The gate

Nothing here publishes. A chat spike is a *candidate*: chat also spikes on raids, giveaways and
copypasta. Every clip still needs a human to watch it, write the first line (`/yt-shorts` rules,
scored with `../yt-script/hookscore.py`) and decide. **The streamer owns the footage.** Clip the
channels that allow it, or that run a clipping programme, and say so in the post.

Last line of every run: **ship it, or change it?**
