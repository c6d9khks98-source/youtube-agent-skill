---
name: yt-niche
description: >-
  Find what's working in the user's niche from the public video lists of
  channels they name - top five by multiple over each channel's own median,
  with the formula each used. Use for "/yt-niche", "scan these channels",
  "what's working for these channels", or a list of competitor channels.
argument-hint: "[channel 1] [channel 2] [channel 3] ..."
---

# yt-niche

Find what's working in my niche. Use the public video lists of these channels (at least four videos
each): $ARGUMENTS. Show me the top five with their multiples and the formula each one used.

This is a fixed run of `/yt-viral`. Follow [the yt-viral skill](../yt-viral/SKILL.md), which sits next to this folder, for everything not
said here.

## Steps

1. **Channels.** Take them from the arguments above (URLs, @handles or names). If none were given, or
   only a placeholder like `[channel 1]`, ask for at least three before doing anything else.
2. **Collect** at least four videos per channel from the public listing only - never a logged-in
   session, never the user's credentials. For a Shorts channel use its `/shorts` tab, so you compare
   Shorts with Shorts. Fastest: `yt-dlp --flat-playlist -J "<channel url>/videos"` (or `/shorts`),
   when installed; otherwise read the public channel page. Take the 10-20 most recent per channel
   if they are available, and write them to a JSON file in the scratchpad:

   ```json
   [{"channel":"...","title":"...","views":412000,"url":"...","duration":613}]
   ```

3. **Rank:** `python3 -I ../yt-viral/swipe.py <collected.json>` (run from this skill's folder). If it skips a channel
   for having fewer than four videos, say so and name it.
4. **Hand back:**
   - the top five: title, channel, views, **multiple** over that channel's median, and the
     **formula**. Say plainly that the formula is a judgement about the title, not why it worked
   - the ONE structural thing the five share
   - which of them the user could make this week, in their voice (`~/.claude/youtube/voice.md`),
     with what they have

Never invent a view count. If a number could not be read, leave that video out and say so.

The last line of every run is the question: **ship it, or change it?**
