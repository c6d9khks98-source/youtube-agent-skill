---
name: yt-kids
description: >-
  Build and run a kids cartoon channel - the channel bible, the recurring
  characters, episode scripts written for preschool ears, the AI production
  pipeline, and the made-for-kids and originality checks that decide whether
  it ever earns. Use for "/yt-kids", "kids cartoon channel", "nursery rhyme
  channel", "faceless animation channel for kids", "Cocomelon-style channel".
argument-hint: "[idea, age band, or 'bible' / 'episode' / 'check']"
---

# yt-kids

Most kids channels started this year are the same ten public-domain nursery rhymes in the same
glossy 3D toddler style, generated in a batch of twenty-four and uploaded on a Tuesday. That is the
exact shape YouTube's inauthentic-content rule (the old "repetitious content" rule, renamed in July
2025) exists to keep out of the Partner Programme, and it is up against Cocomelon, Little Angel,
Super Simple Songs and ChuChu TV, who have been doing it for a decade with real budgets.

So this skill does not start with a generator. It starts with **one thing a parent would recognise
across two different videos**: a character, a world, a recurring bit. That is what makes a channel
rather than a pile of uploads, and it is what an originality review looks for.

Arguments: $ARGUMENTS

## Modes

Pick from the arguments. With none, run **bible** first, because every other mode reads it.

### bible - the channel, once

Fill [`templates/channel-bible.md`](../../templates/channel-bible.md) with the user and save it to
`~/.claude/youtube/kids-bible.md` (if the template is not installed alongside, use the six questions
below as its sections). Ask, do not assume:

1. **Age band.** 0-2, 2-4, 4-6 or 6-8. These are different audiences. A 2-year-old needs one idea,
   slow cuts and the same song again; a 7-year-old leaves for that. Never "kids 0-10".
2. **The hook that is not the song.** Public-domain rhymes are fine as a vehicle and worthless as a
   moat. What is ours: a character (a nervous dinosaur who is scared of everything), a world (a
   bakery run by animals), a format (every episode ends with the same goodnight).
3. **Cast.** Two or three characters at most to start, each with one want, one fear, one catchphrase,
   a fixed colour palette and a silhouette you could tell apart at thumbnail size. Write the visual
   description once, word for word, so every generation reuses it. Character drift between episodes
   is the first thing that makes AI kids content look like AI kids content.
4. **What we teach.** One learning thread per episode - a colour, a number, sharing, brushing teeth,
   saying sorry. Parents choose what plays; a parent can say what the episode teaches.
5. **What we will never show.** Write it down: no peril without resolution, no characters getting
   hurt for a laugh, no brand names, no unsafe behaviour a child could copy (climbing, bath water,
   small objects in the mouth), no scary faces in the thumbnail. Kids content gets reviewed harder
   than anything else on the platform, and Elsagate is why.
6. **Long or short.** Kids watch long-form on a TV, played by a parent, in compilations. Plan the
   channel around 2-4 minute episodes that stack into 20-60 minute compilations, with Shorts as the
   trailer, not the product.

### episode - one script

Read the bible first. If it does not exist, run **bible**.

Write for the ear of the age band, not the eye of the adult reading the script:

- **One idea per episode.** If you need "and also", it is two episodes.
- **Short lines.** Under ten words per spoken line for 2-4, under fourteen for 4-6.
- **A refrain.** A line or a sung chorus that comes back at least three times. Repetition is the
  product for under-fives, not padding.
- **Talk to the viewer.** A question every 30-40 seconds, with a pause long enough to answer
  ("What colour is the balloon? ... Red!").
- **Name the learning out loud** at the end, in the character's catchphrase.
- **Shot list alongside the lines.** Each shot gets the bible's exact character descriptions,
  so the generator gets the same words every time.

Then lint it: `python3 -I kidscript.py episode.txt --age 2-4` (run from this skill's folder). It
flags long lines, long words, a missing refrain, too few questions and the runtime at a
kids pace. It is a heuristic. A clean report means nothing is obviously wrong, not that it is good.

If the episode uses a traditional rhyme, say which one and confirm it is public domain. "Twinkle
Twinkle" and "Humpty Dumpty" are. A song from a TV show, a film or another channel's original
version is not, and neither is someone else's arrangement or recording of a public-domain tune.

### pipeline - getting it made

Say which tools the user already has before suggesting a new one. If an AI video tool is connected
(for example a nursery-rhyme or story workflow in Everygen, or Higgsfield, or Artlist), use that
rather than signing up for another one.

The order that keeps the cast consistent:

1. Character reference sheets from the bible, one per character, approved by the user **before** any
   episode is generated.
2. Voice: one fixed voice per character, chosen once. Song tracks generated or licensed with the
   licence written into the bible.
3. Scenes generated from the shot list using the reference sheets, never from a description alone.
4. Assemble, caption (big, high-contrast, for the parent), add the channel's fixed intro sting and
   outro, then run `/yt-package` on the title and thumbnail.
5. A human watches every second before upload. AI video puts extra fingers, melting faces and
   things in the background that should not be there. In kids content, one of those is a strike.

Batch the **generation**, not the **uploading**. Making ten episodes in a day is fine. Publishing
them as ten near-identical videos is how a channel reads as mass-produced.

### check - before every upload

Go through this with the user and hand back what failed:

- [ ] **Made for kids set to Yes.** It is a legal requirement (COPPA), not a preference. The FTC
      has said channel owners can be liable themselves, and YouTube can override the setting.
      With it on: no personalised ads, no comments, no notification bell, no end screens or
      cards, no miniplayer. Plan for all of it.
- [ ] **Originality.** Would a reviewer see a recurring character, a written script and a deliberate
      edit, or a template with the nouns swapped? If two of the last five uploads have the same
      structure and only a different rhyme, stop and fix the format.
- [ ] **Rights.** Every song, voice and image is public domain, generated by a tool whose licence
      allows commercial use, or licensed - and the bible says which.
- [ ] **Safety.** Nothing from the bible's never-show list. Thumbnail has no fear, injury or
      distorted faces.
- [ ] **Packaging.** `/yt-package` passed. The title says what the child sees ("Dino Brushes His
      Teeth Song"), not keyword soup.
- [ ] **A person watched it all.**

## The money, honestly

Never put an earnings figure in front of the user that you did not get from their own analytics.
The screenshots in "faceless kids channel" adverts are routinely labelled as sample data in the
corner. Made-for-kids videos earn without personalised ads, so their RPM is typically well below
the same views on general content. Say that before the user plans a budget around it. If they ask
for a number, ask for their YouTube Studio export, or use `/yt-niche` on real channels in the age
band and talk about views, not dollars.

## The gate

Nothing here publishes. This skill writes and you upload. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**
