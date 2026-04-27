# Music

Public-domain classical recordings used as Milo's signature score and
sting cues. The autonomous video pipeline cannot trust the xAI video
model's lip-synced dialogue, so episodes are scored entirely in post:
the stitch step replaces the concatenated video's audio with a track
from this folder.

## Tracks

| File | Composer | Piece | Recording | Duration | License |
|---|---|---|---|---|---|
| `satie-gymnopedie-1.mp3` | Erik Satie | Gymnopédie No. 1 | Internet Archive `Gymnopedie_201309` | 3:03 | Public Domain |

## Adding a track

1. Drop the file into this folder. Naming convention: `composer-piece-N.ext`
   in lowercase ASCII (e.g. `debussy-arabesque-1.mp3`,
   `saint-saens-aquarium.mp3`). The runner accepts any name; the
   convention is just for our own sanity.
2. Verify the licence — only Public Domain or CC0 sources are safe for
   long-term autonomous use. CC-BY recordings require attribution and we
   don't have an automated attribution slot yet.
3. Reference the track from a manifest:

   ```yaml
   music:
     track: satie-gymnopedie-1   # extension is inferred
     volume_db: -2               # gain offset (default -2 dB)
     fade_in_s: 1.5
     fade_out_s: 2.5
     start_offset_s: 0.0         # skip into the source track
   ```

## Show theme

`satie-gymnopedie-1.mp3` is **Milo's signature theme** — every episode
that doesn't pick something else uses it. Treat it like a sitcom theme:
recognisable, recurring, identity-forming. Only deviate when the
episode's mood truly demands a different colour.
