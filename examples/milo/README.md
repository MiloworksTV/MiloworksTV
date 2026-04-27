# Milo

A 2D cartoon series about one shapeshifting blob from a liquid dimension,
produced end-to-end by feeding structured prompts into
[`grok-imagine-video`](https://x.ai/) via the `milo` CLI in this repo.

One **60-second episode every day**, all chained as a single continuous
plano-secuencia: every day's first frame *is* yesterday's last frame.
The show is **silent** — no spoken dialogue; every episode is scored
post-render with Satie's *Gymnopédie No. 1*.

---

## Definition

**Milo** is a warm, bright, slightly trippy animated short-form series for
kids and grown-ups alike. Tone: *Pocoyo* simplicity + *Adventure Time*
heart + *Futurama* sarcasm + *Midnight Gospel* gentle psychedelia. Every
episode is ≈60 seconds, silent (no spoken dialogue), self-contained, and
the entire run is shot as one unbroken plano-secuencia chain — the
backyard never cuts away, only Milo's body changes.

**Milo** is a single shapeshifting alien blob who crash-landed in a
suburban backyard. His body is made of unstable probability — it
literally morphs with every emotion, question, or human concept he
fails to understand. He is joined by **Pip**, a deadpan 9-year-old girl
who finds him unbearably ridiculous… and quietly becomes his best
friend.

---

## The Soul of the Show (why it exists)

Under the silliness is one simple, honest message:
**Change is not a problem to solve — it is the only honest way to be
alive.**

Milo's body is the proof. Kids see a silly, stretchy friend who turns
into a giant pretzel when he panics. Adults feel the deeper truth:
nothing stays the same, the universe is absurd, and that's okay —
especially when you have one unimpressed friend who sticks around
anyway.

The show never lectures. It just lets Milo melt, stretch, sprout extra
eyes, or briefly *become* the concept he's failing at (a ticking clock,
a rainbow of hearts, a floating question mark). The AI's natural drift
becomes the visual language. Every glitch is canon. Every morph is both
joke and philosophy.

---

## Core Characters

- **Milo** — Default form: small mint-green teardrop with two wobbly
  antennae and one big expressive eye, **no mouth**. He morphs
  constantly based on feeling. He never speaks — the show conveys his
  inner life through morphs, antenna movements, eye expressions, and
  small thought-bubble emoji that pop above his head (`!`, `?`, `❤️`,
  `💡`, `✅`, `❌`, `💭`, `💤`). His default form **slowly evolves
  over the year** — see "Compounding form" below.
- **Pip** — 9-year-old girl next door. Dry, juice-box addicted,
  unimpressed, secretly kind. The fixed point in Milo's liquid
  universe. She also never speaks — her power is the deadpan stare,
  the long slurp through her bendy straw, and one decisive gesture
  per beat.
- **The Magazine** — Milo's copy of *HOW TO BE HUMAN*, found in Ep 0,
  is a recurring sight gag. Each weekday episode "checks off" one page.
  Over the year, the magazine slowly empties.

No other permanent cast. Occasional one-offs appear only when the story
needs them.

---

## The long-term arc — *Year of Becoming*

The show follows **one Earth year** in the backyard, in real time.
Day 1 is today. Day 365 is one year from today. The seasons change
around Milo. Pip's life passes around them — school, summer, holidays,
a snow day, a new juice flavor at the corner store. Milo experiences
each "human ritual" exactly once. Education through the calendar
itself.

Three things compound across the year:

1. **The magazine empties.** Each weekday "checks off" one human
   concept. The page count is a quiet visible counter.
2. **Milo's default form drifts.** Every ~10 episodes, one tiny detail
   on his default teardrop changes permanently — a new color speck, a
   slightly different antenna tilt, a pupil that now sparkles a
   different way. By Day 365 his default is visibly *evolved*. Nothing
   ever resets.
3. **The sky knows he's here.** Roughly once a month, something
   distant happens overhead — a brief aurora, a falling star, a low
   ripple in the clouds. Never landing, never explained. The
   homeworld is aware of him; he doesn't yet know what to do with that.

Around **Day ~90** the foreshadowing pays off and an actual second
blob arrives. By then we've spent a full season making the audience
love this backyard before threatening it.

The full year-by-year roadmap, weekday curriculum buckets, monthly sky
events, and form-drift rules live in
[`series_arc.md`](series_arc.md). That file is the operational writers'
room — it's what new daily episodes are derived from.

---

## Daily Episode Formula (60 s, 6 shots, 7 days/week, silent)

The same micro-structure runs every day. It's a four-beat shape
plus open and hand-off, distributed over six shots so the model never
has to render more than ~14 s in a single call.

| # | Beat | ~Dur | What happens |
|---|---|---|---|
| 01 | **Cold open** | 10 s | Pick up *exactly* from yesterday's last frame. Milo mid-something, world stable. |
| 02 | **Concept hook** | 10 s | Pip arrives or shifts pose. One deadpan gesture names today's topic. A `?` thought-bubble can pop above Milo. |
| 03 | **Wrong attempt** | 12 s | Milo tries it the alien way. One single body-morph. Goes visibly sideways. |
| 04 | **Becomes the concept** | 14 s | Signature beat: Milo *holds one sustained pose* that **is** the concept. |
| 05 | **Quiet payoff** | 8 s | Morph settles. Tiny `❤️` / `💡` / `✅` thought-bubble pops and fades. Pip flickers a half-smile or doesn't. |
| 06 | **Hand-off frame** | 8 s | Camera holds on a clean stable image. Pip out of frame. **This frame is tomorrow's seed.** |

Episodes are scored post-render with **Satie's _Gymnopédie No. 1_**
(public domain, see [`music/README.md`](music/README.md)). The model
bakes its own audio into each clip; the stitch step throws it away
and lays the Satie track on top. Result is consistent musical identity
across every daily episode without depending on the model's bad
lip-sync.

### Weekday curriculum buckets

The "concept of the day" rotates through five themed buckets so the
week has texture without ever feeling templated:

- **Mon — Feelings** (patience, jealousy, boredom, embarrassment, hope, pride…)
- **Tue — How Things Work** (gravity, shadows, ice, wind, echoes, mirrors…)
- **Wed — People Rules** (sharing, thank-you, lying, taking turns, secrets…)
- **Thu — Words** (idioms only — "hold your horses", "spill the beans"…)
- **Fri — Big Questions** (time, dreams, infinity, "where do thoughts go?"…)

### Weekend — chain-rest episodes

Saturday and Sunday do **not** run the curriculum. They are quieter,
cheaper-to-generate, atmosphere-first episodes:

- **Sat — Pure being.** No concept, no lesson. Milo and the backyard at
  a different hour (early dawn, deep dusk, midday rain). One small
  visual gag, ambient audio, almost no dialogue. The chain breathes.
- **Sun — Recap morph.** Milo absent-mindedly half-morphs through the
  week's five concepts in a single quiet sequence while Pip reads
  beside him. Light callback to compound the week.

Every shot still chains via `image_from`, even on weekends.

---

## The Pipeline

Three files at the repo root are the **master canon** for the series
and are reused by every episode:

- [`style_bible.md`](style_bible.md) — the look, voices, world rules,
  character-presence rule. Prepended to every prompt.
- [`series_arc.md`](series_arc.md) — the year roadmap and operational
  writers' room (curriculum buckets, milestones, sky events,
  form-drift schedule).
- [`characters.yaml`](characters.yaml) — reference-sheet prompts for
  Milo and Pip.
- [`README.md`](README.md) — this file.

Each episode lives in `episodes/<slug>/` with its own:

- `manifest.yaml` — the ordered scene list (the **script**).
- `README.md` — a human-readable overview of the episode.
- `style_bible.md` and `characters.yaml` — symlinks back to the root
  masters so the show stays self-consistent. (You can override by
  replacing the symlink with a real file if a specific episode needs
  its own look.)

```text
style_bible.md  ─┐
characters.yaml ─┼─►  milo characters  ─►  character PNGs
                 │
manifest.yaml   ─┴─►  milo run         ─►  per-scene MP4s  ─►  stitched episode.mp4
                                              │
                                              └─►  last_frame.png  ─►  next day's scene 01 seed
```

Every narrative scene chains from the previous frame
(`mode: image`, `image_from: "<prev>"`). Daily episodes additionally
chain *from each other*: each episode's final `last_frame.png` becomes
the next day's `image_from: "_prev_episode"`. The model doesn't know
it's making a series — it only knows it's continuing the exact frame
it was handed. Shapeshifting is now the feature, not the bug.

New episodes = new `episodes/<slug>/` folders. The CLI does not need to
change.

## Repo layout

```
README.md                series definition (this file)
series_arc.md            year roadmap + curriculum buckets + sky events
style_bible.md           master style bible, used by every episode
characters.yaml          master reference sheets (Milo, Pip)
milo/                    CLI + runner (Python)
  manifest.py            loads manifest.yaml + style_bible.md
  runner.py              orchestrates characters → scenes → stitch
  xai_client.py          thin client over grok-imagine
  ffmpeg_utils.py        concat + last-frame extraction
episodes/
  ep00-the-landing/      pilot — see its README
  day-001-…/             daily episodes from here on
```
