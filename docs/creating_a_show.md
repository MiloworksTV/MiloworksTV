# Creating a chained-frame show

This is the design philosophy behind shows like **Milo**. None of it
is enforced by the engine — manifests can be whatever you want — but
the chain-frame technique is what MiloWorks is shaped around, and it
solves several real problems with prompt-driven video generation. If
you're building a long-running series, read this once.

## The chain

Every scene in a manifest names where its seed image comes from:

```yaml
- id: "02"
  mode: image
  image_from: "01"        # last frame of scene 01
```

So scene 02 begins with the *exact* pixels scene 01 ended on. Scene 03
begins where 02 ended. The whole episode plays as one continuous take
— a *plano-secuencia*. The model never has to invent the world from
scratch; it inherits it.

A whole season can chain across episodes, too:

```yaml
prev_episode: ep00-pilot
handoff_scene: "06"

scenes:
  - id: "01"
    mode: image
    image_from: "_prev_episode"
    duration: 10
    prompt: >-
      The next morning. Same backyard, ...
```

`miloworks stitch` copies the `handoff_scene`'s `last_frame.png` up to
`output/last_frame.png`, where the next episode finds it.

## Why this works

Prompt-driven video has three fragility modes:

1. **Style drift**: every clip is a fresh roll of the dice on look
   and feel. Same character, different render.
2. **Setting drift**: same room, different room.
3. **Time-of-day drift**: same sunset, different sunset.

Reference images mostly fix (1). The chain fixes (2) and (3) almost
completely. Whatever was in the last frame is in the next first frame.
The model is no longer authoring the world; it's continuing it.

A useful rule of thumb: **the seed frame carries about 80% of the
visual information**. Your prompt only needs to specify what changes.

## Trade-offs to budget for

- **The chain is sacred.** Once you start, you can't go back and
  re-render scene 01 without invalidating every later scene's seed.
  Plan the order; render in order; reroll only when needed.
- **Hand-off frames are the whole game.** Episode N's last shot is
  episode N+1's first shot. If your hand-off frame has weird artifacts
  or a character mid-blink, tomorrow's writer is stuck with it.
  Practice: design the last shot of every episode as a *clean stable
  wide* with the world in default state.
- **Negation is unreliable.** Telling the model "no Pip" while Pip is
  in the seed frame doesn't reliably remove her. The fix is to design
  the *previous* shot to walk her out of frame *before* the cut. The
  seed frame *is* the law.
- **One body change per shot.** Multi-step compound moves ("crashes
  then splashes then surfaces") almost always render badly. If a beat
  needs N changes, that's N shots.
- **Restate the world in every prompt.** The model is an actor with
  no memory between calls. Repeat the location, lighting, props, and
  character defaults in every shot.

## Scene budget

For a 60-second episode, six shots × ~10 seconds is the sweet spot:

| # | Beat | Dur | Job |
|---|---|---|---|
| 01 | Cold open | 10 s | Pick up exactly from yesterday's last frame. |
| 02 | Concept hook | 10 s | One deadpan gesture names the topic. |
| 03 | Wrong attempt | 12 s | One single visible try. |
| 04 | The signature beat | 14 s | One sustained pose that *is* the concept. |
| 05 | Quiet payoff | 8 s | Morph settles. Tiny insight cue. |
| 06 | Hand-off frame | 8 s | Clean stable wide. Becomes tomorrow's seed. |

Longer than 14 s in a single scene tends to compound model errors.
Shorter than 5 s rarely lands a beat. The Milo example calls each
of these out in `examples/milo/daily_writer.md` — that file is a
working "system prompt" you can hand an LLM along with the day's
inputs to draft a manifest.

## A weekly curriculum

Long-running shows benefit from texture. Milo rotates through five
themed buckets across the work week so the show has shape without
feeling templated:

- **Mon** — Feelings (an emotion or emotional state)
- **Tue** — How Things Work (gravity, shadows, ice melting…)
- **Wed** — People Rules (sharing, please-and-thank-you, taking turns…)
- **Thu** — Words (idioms, taken literally)
- **Fri** — Big Questions (time, dreams, infinity…)
- **Sat** — Pure Being (a quiet hangout, no concept)
- **Sun** — Recap (Saturday's gentle echo of the week)

Saturday and Sunday are deliberately cheaper to produce — fewer
characters, less choreography. The model gets a rest, the chain gets
a rest, you get a rest.

## Compounding

Three things that change slowly across a long run:

1. **The world itself drifts.** Add one tiny permanent change to your
   protagonist's default form every ~10 episodes. Never remove. By
   episode 100 they're visibly evolved.
2. **A long-arc thread runs underneath.** Roughly monthly, something
   distant happens (sky event, weather change, calendar holiday) that
   isn't acknowledged in the script but is visible in the frame.
3. **Concept pools deplete.** Track which concepts you've used per
   quarter and avoid repeats within the same quarter.

Milo's `series_arc.md` documents all three. Steal whatever's useful.

## Make the model's drift work for you

The AI doesn't render the same character the same way twice — that's
not a bug to suppress, it's the visual language of a show about
change. Milo (the show) leans into this hard: the protagonist is a
shapeshifting blob whose body literally morphs with every emotion he
fails to understand. Every glitch is canon.

Yours doesn't have to be a shapeshifter. But the closer your premise
sits to "controlled drift" — dreams, glitches, memory, transformation,
seasons, weather — the more the model's natural behavior reads as
intentional rather than broken.
