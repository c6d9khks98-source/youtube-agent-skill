---
name: yt-reel
description: >-
  Plan, shoot and finish a vertical Reel or Short built around one visual
  effect, using what the swipe file in reels.md says actually stopped the
  scroll. Renders the effects with reel.py (broken-reality, messages,
  toggles). Use for "make a reel like this", "add an effect", "how should I
  shoot this", "learn from this reel", or when the user pastes a reel link.
---

# yt-reel

A reel that stops the scroll does one thing the feed is not supposed to do, in the first second.
Everything else in it is there to explain that one thing or sell off the back of it.

## Learning from a reel

When the user pastes a reel to learn from:

1. Watch it. If a short-form watcher is connected (vidIQ's `vidiq_watch_shortform_content`, Everygen's
   `analyze_video`), use it and say what it cost. If not, ask for the on-screen text and a description;
   never describe a video you have not seen.
2. Add an entry to `reels.md` in the same shape as the ones there: **hook (0-2s), the trick, the beat
   sheet, the setup, the CTA, what we take, what we don't**. "What we don't" is mandatory. Most of a
   viral reel is the creator's distribution, and copying that part does nothing for you.
3. If the trick is an effect `reel.py` cannot do yet, say so and propose it as a new `effects/*.html`
   page rather than faking it with an effect that exists.

## The setup (from reels.md, not from taste)

- **Tripod, locked off.** Both swipe-file reels are static shots. Every effect here assumes the frame
  does not move. A handheld wobble breaks `broken-reality` outright.
- **Effect first, in the first second.** Neither reel opens on a face saying hello. One opens on sauce
  crossing the UI, the other on a command producing a result.
- **One effect per 2-4 seconds when it's a montage**, cut on the beat, no voiceover needed. A single-
  effect reel (the sauce one) can run the whole length on one trick.
- **Plain backdrop.** White for `broken-reality` (it is the key). Neutral and warm-lit for overlay effects,
  so the banners and cards are the brightest thing in the frame.
- **Faces medium close-up, upper third clear.** `messages` uses the top 30% of the frame and `toggles`
  the band from 60% to 80%. Frame the subject so neither covers the mouth.

## The effects

```bash
python3 reel.py list
python3 reel.py broken-reality pour.mp4 -o reel.mp4 --handle yourcafe --caption "careful, it's hot"
python3 reel.py messages talk.mp4 -o reel.mp4 --text "how did you edit this??" --text "which app is this"
python3 reel.py toggles talk.mp4 -o reel.mp4 --text "One clip" --text "One command" --text "Zero editing apps"
```

| effect | use it for | the shot it needs |
| --- | --- | --- |
| `broken-reality` | The pour or drip that leaves the post and runs over the like row and caption. | Dark liquid on a plain, evenly lit **white** backdrop. Pour from the top third, slightly left of centre so it crosses the icons; catch it in a dark mug in the bottom 250px. Nothing white on the subject. |
| `messages` | Social proof shown, not said: the DMs you would get if this worked. | Any locked-off clip with the top 30% free. |
| `toggles` | A three-part claim ("one clip / one command / zero apps") without three cuts. | Any locked-off clip with the 60-80% band free. |

`reel.py` needs ffmpeg and Node with Playwright. It is the one tool in this pack that is not plain
Python, because it makes video. The look of each effect lives in `effects/<name>.html`; change the
CSS there, not the script. A new effect is a new HTML page that defines `window.seek(t)`.

**`broken-reality` lives or dies on the backdrop.** It replaces every near-white pixel with the feed.
Shadows on the wall come out as grey smudges over the feed; milk, matcha or a white cup simply
disappear. If the edges look dirty, pass `--key LO HI` with a narrower window (e.g. `--key 190 230`).

## The CTA

Both reels end on "comment WORD and I'll send you X". That only works with a DM automation (ManyChat
or similar) connected to the account, which this pack does not set up. If the user has none, write
the CTA as a follow or a save instead, and say why.

## The gate

Nothing here publishes. This skill writes and renders, and you post. Every run ends with the file
path, the caption block to copy, and one question: **ship it, or change it?**
