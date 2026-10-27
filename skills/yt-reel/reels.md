# Reel swipe file

What we learned from reels we studied. Add one entry per reel, in this shape. View counts are what
the reel itself claims unless marked otherwise; they are not verified.

---

## Broken reality: the sauce that spills onto the feed

- **Source:** instagram.com/reel/DcORDV6phDM (a breakdown of `@asadshotchicken`'s reel, which claims
  38M views), 39s.
- **Hook (0-2s):** sauce pours out of the post's frame and drips over the like button and caption.
  For a frame the viewer thinks it is on their screen. No words needed. The original has none.
- **The trick:** the feed UI is composited *behind* the liquid, so the liquid crosses the boundary
  the brain expects to stay flat.
- **Beat sheet:** the whole reel is the one trick. Pour, cross the UI, land in the food below.
- **Copies that also worked (per the breakdown):** `@urbanritualcafe` (matcha into a drawn
  character's mouth), `@realmrpatty` (cheese off a burger), `@bondscoffee` (coffee onto a person
  below the UI).
- **CTA:** the breakdown ends "comment HOOKS for 5,000 hooks". That is a lead magnet, not part of
  the format.
- **What we take:** `reel.py broken-reality`. Locked-off, white backdrop, dark liquid, landing target
  below the caption.
- **What we don't:** the 5,000-hooks list. It is padding around about twenty formulas, and
  `yt-script/hooks.json` already has 21.

---

## /effects montage: a command per effect

- **Source:** instagram.com/reel/DfALvrURxFL (an ad for an AI video-editing studio in progress), 28s.
- **Hook (0-2s):** a dark chat UI types `/effects carousel-spin` and the result appears straight away.
  It promises effort-free production in one line.
- **The trick:** the cut alternates between the command being typed (cause) and the effect playing
  full screen (effect), about every 3s, cut to a trap beat. No voiceover at all.
- **Beat sheet:** carousel-spin (0-2) → over-the-shoulder zoom with a glass views graph (3-6) →
  match-cut with kinetic type (7-9) → liquid-glass analytics HUD (10-13) → notification bubbles
  "how did you edit this??" / "wait, which app is this" / "send me the effects pls" (14-16) → toggles
  "One clip / Type /effects / Zero editing apps" (17-19) → clips dropping into a profile grid (20-22)
  → reveal of the product and CTA (23-28).
- **Setup:** tripod, eye-level medium close-up, warm key light, warm practical lamp behind, plain
  neutral wall, a handheld mic in frame as a "creator" signal.
- **CTA:** "Comment 'studio' for early access + all 45 effects". It needs DM automation behind it.
- **What we take:** the montage rhythm (one effect per ~3s, effect in second one, no VO), the setup,
  and two of the effects as `reel.py messages` and `reel.py toggles`. The notifications are social
  proof faked as UI. They work because they are what the viewer is about to think.
- **What we don't:** the chat-UI framing that imitates a specific AI app. It's someone else's interface
  and it is not ours to wear. The "45 effects" number either: three that are good beat 45 listed.
  The carousel, HUD and grid effects are not built yet. They are candidates for `effects/`, not
  promises.
