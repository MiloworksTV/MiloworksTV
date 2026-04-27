# Ep 0 — The Landing

> A small mint-green alien blob wakes up alone in a suburban backyard,
> figures out it can move and read, meets a deadpan 9-year-old, and
> decides — quietly, definitively — that it likes it here.

Runtime ≈ 116 s, 11 scenes (9 narrative + title + outro), 16:9 720p.
Pilot episode of **Milo** — see the [series README](../../README.md)
for the bigger picture, [`series_arc.md`](../../series_arc.md) for
the year-long curriculum, and [`daily_writer.md`](../../daily_writer.md)
for the system prompt that produces daily manifests. Ep 0 hands off
cleanly into Day 1.

---

## Why this version exists

There was an earlier pilot. It had a comet, a splash, a homeworld
flashback, and 22 shots. The video model rendered the imagery
beautifully and then quietly skipped most of the action — Milo never
landed in the pool, Pip leaked into shots that were supposed to be
solo, and a script full of "where am I?!" lines fell flat over
visuals of Milo standing dry on a lawn next to a kid he hadn't met
yet. It was, accurately, slop.

This pilot is rewritten around what we learned that night. It assumes
the model will:

1. **Skip action verbs and render the resulting state** ("comet
   crashes, splashes, Milo surfaces" became "Milo standing on a
   lawn"). So this pilot has no action sequences. Milo is already in
   the backyard from frame 1.
2. **Add characters from world context if they're anywhere nearby**.
   So every shot before Pip's intro ends with the explicit phrase
   *"THERE ARE NO HUMANS, NO GIRLS, NO OTHER CHARACTERS IN FRAME"* to
   fight the contamination.
3. **Score whatever dialogue we hand it, regardless of what's on
   screen**. So every spoken line in this pilot describes only what
   is visible in *that exact shot*. There are about twelve words of
   dialogue across the whole episode.

These three assumptions are now codified as the writing-for-the-model
rules in [`daily_writer.md`](../../daily_writer.md).

## Script — definition

The episode is one short story, laid out as an ordered list in
[`manifest.yaml`](manifest.yaml). Each entry is one shot: an `id`,
a `mode`, a `duration`, a visual `prompt`, and an `audio` direction.

| Beat | Scenes | What happens |
|---|---|---|
| **Cold open — waking up** | `01`–`02` | Empty late-afternoon backyard. A small green pebble in the foreground slowly uncurls into Milo's default form. No dialogue. |
| **Title card** | `03` | Hot-pink "Milo" card with a tiny morphing blob silhouette. Hard cut. `mode: text`. |
| **Act 1 — what is this** | `04`–`06` | Milo looks around at the world and says *"…what."* He notices the magazine on the lawn, lifts the cover with a temporary noodle arm, reads page one, says *"…oh."* No other characters anywhere. |
| **Act 2 — Pip** | `07`–`09` | Sliding glass door is open; Pip is already standing on the patio. *"Hey."* She walks across the lawn, sits a few feet from Milo, slurps. Milo offers the magazine. Pip says *"That's mine. You can borrow it."* She gets up, walks back toward the house, glances over her shoulder: *"Don't lose it."* |
| **Hand-off to Day 1** | `10` | Camera pulls back to a clean wide stable shot. Twilight. Pip is gone, the door is closed. Milo sits alone on the lawn with the magazine in his lap. No dialogue. This frame seeds Day 1. |
| **Outro card** | `11` | Mint-green card, "DAY 1 TOMORROW", tiny looping silhouettes of Milo morphing between shapes. `mode: text`. |

## Script — insight

Three constraints shaped this pilot, and most of its structure falls
out of them.

1. **No scripted action sequences.** Each shot is one stable state
   with at most one small animating element — Milo's eye opening, a
   noodle arm lifting a magazine cover, Pip taking one slow slurp.
   No splashes, no falls, no comet arrivals, no chases. If something
   has to happen, it happens *between* shots and the next shot just
   shows the after-state. This is how Milo "arrives" without an
   arrival sequence: he was already there.
2. **Self-evident dialogue.** Every spoken line refers only to what
   is on screen in that very shot. *"…what"* lands because Milo is
   visibly looking at things. *"…oh"* lands because he's visibly
   reading. *"Hey"* lands because Pip just walked into the frame.
   Lines that depend on off-screen events were the single biggest
   failure mode of the previous pilot, so they are gone.
3. **The morph is reserved.** Milo only meaningfully morphs three
   times in this whole pilot: he uncurls into his default form
   (shot 02), he sprouts one tiny noodle arm to lift a magazine
   (shot 05), and he extends both noodle arms to hold it open
   (shot 06). Everything else is the morph staying *un*-performed,
   which is what makes shots 07–10 feel like a real first contact
   instead of a chaos montage. The big morph budget belongs to the
   daily episodes.

Two continuity tricks survive from the previous pilot:

- **Scene 04 chains from scene 02**, not from the title card at
  `03`. The title is a pause, not a scene change.
- **Scene 10 is the daily-engine handoff.** Its `last_frame.png` is
  copied to `output/last_frame.png` at stitch time and becomes the
  seed for Day 1's shot 01 (`image_from: "_prev_episode"`). See
  [`series_arc.md`](../../series_arc.md) and the cross-episode
  chaining logic in `milo/runner.py::_resolve_prev_episode_frame`.

## Prompts — definition

Every scene has **two** prompt strings the runner combines before
sending:

- `prompt:` — the visual direction (camera, framing, character
  actions and morph state, props, lighting).
- `audio:` — ambience, SFX, and character dialogue with voice /
  morph-state direction.

At generation time `milo/manifest.py::compose_prompt` concatenates
three blocks joined by `\n\n---\n\n`:

```text
<style_bible.md contents>

---

SHOT:
<scene.prompt>

---

AUDIO:
<scene.audio>
```

The master style bible at the repo root is prepended to *every*
scene so character designs, voices, palette, and the "only named
characters appear" rule are restated each time — the model has no
memory between calls.

Chaining is controlled by three fields on each scene:

- `mode: text` — pure text-to-video (used only for the title and
  outro cards).
- `mode: image` + `image_from: "<prev_id>"` — seeds the next clip
  with the last extracted frame of a previous scene. The default
  for narrative shots.
- `mode: reference` + `reference_chars: [...]` — seeds from the
  character sheets in `characters/` instead of a previous frame.
  Not used in this pilot but available as a fallback if Pip's
  shot-07 entry refuses to render cleanly.

## Prompts — insight

Writing prompts for this model is less like writing screenplays and
more like writing **shot lists for a very literal DP who has no
short-term memory and no patience for verbs**. The patterns that
made this pilot work, in order of importance:

- **Name the negative space, then name it again.** Every shot
  before Pip's intro ends with *"THERE ARE NO HUMANS, NO GIRLS, NO
  OTHER CHARACTERS IN FRAME"* in caps. Without that, the model
  cheerfully paints a girl into the lawn because the style bible
  describes one. The previous pilot lost shots 03–06 to exactly
  this failure.
- **One stable state per shot, plus one small animating element.**
  "Milo holds his pose, only his eye blinks." "The cover lifts an
  inch." "The juice box slurps." Multi-step compound moves get
  compressed into the resulting state and the script falls out of
  sync.
- **Self-evident dialogue.** Read every spoken line aloud while
  looking only at its shot's `prompt`. If the line refers to
  something the prompt doesn't explicitly draw, rewrite the line
  or rewrite the prompt. The audio model will not save you.
- **Restate the frame every shot.** "Same backyard, same props,
  same lighting" appears in every narrative shot. Without it the
  model re-blocks the scene between cuts even when seeded from
  the prior frame.
- **Name the morph state.** Whenever Milo's body changes, name the
  exact change ("a tiny mint-green noodle arm sprouts from his
  right side"). Otherwise the model defaults him to a static
  teardrop and the gag is lost.
- **Describe the mouth.** Milo has no visible mouth until he
  speaks; when he does, the prompt says *"a small wobbly oval
  mouth appears briefly."* Without that cue, the model either
  gives him a permanent mouth or none at all, and lip-sync
  breaks.
- **Voice tags in the audio block.** Every dialogue line is written
  as `MILO (small, warm, dawning, high squeaky): "…oh."` — a
  character tag plus a morph / delivery adjective. Drop the
  adjective and Milo sometimes sounds like an adult narrator.
- **SFX are always specific.** "soft paper crinkle", "long juice-box
  slurp (~3 seconds)", "warm two-note evening chime". Abstract
  directions ("tense music") get ignored; literal onomatopoeia
  with durations gets scored.
- **Retry on moderation.** The runner wraps each call in up to three
  retries because the moderation filter is non-deterministic on
  benign prompts. Ambiguous verbs ("grabs", "hits", "takes") are
  swapped for concrete cartoon actions ("scoops up", "bonks
  gently", "plops onto") to reduce false positives.

## Sibling files in this folder

- `manifest.yaml` — the script (source of truth for all 11 shots).
- `style_bible.md` — **symlink to the master** at
  [`../../style_bible.md`](../../style_bible.md). Prepended to
  every prompt. Replace with a real file if this episode needs
  its own look.
- `characters.yaml` — **symlink to the master** at
  [`../../characters.yaml`](../../characters.yaml). Reference-sheet
  prompts for Milo and Pip.
- `characters/` — rendered PNGs produced by `milo characters`
  (created on first run).
- `output/` — per-scene MP4s + metadata + stitched final episode
  (created on first run).
- `_archive/` — previous runs of this pilot, including the
  comet-and-splash version and the earlier *Glonk & Glank*
  incarnation. Kept for diffing.
