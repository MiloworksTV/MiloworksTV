# API keys

MiloWorks supports three video backends. You only need to configure
the one(s) you'll use. All keys live in `.env` at your project root
and are loaded via `python-dotenv` — never hardcoded, never logged,
never sent anywhere except to the named provider.

## xAI / Grok Imagine (default)

```ini
# .env
XAI_API_KEY=xai-...
```

Get a key at <https://x.ai/api>. Pricing is per-second of generated
video and is billed directly by xAI. The MiloWorks engine never
proxies or caches your key.

Strengths: best prompt adherence of the three, generates audio
natively, supports all four scene modes (`text`, `image`, `reference`,
`extend`).

## fal.ai (Kling 2.6 Pro)

```ini
# .env
FALAI_API_KEY=...
# or
FAL_KEY=...
```

Get a key at <https://fal.ai/dashboard/keys>. Useful for image-to-video
continuity — Kling tends to preserve seed frames more faithfully than
xAI when the prompt asks for a small change. Limitations: 2500-char
prompt cap, no `text` or `extend` mode, audio is variable.

## Wan 2.2 (self-hosted)

No API key needed — you run [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
locally with Wan 2.2 weights and point MiloWorks at it:

```sh
miloworks run my-episode --backend wan --wan-url http://127.0.0.1:8188
```

Free at the margin and silent (no audio generation), so it pairs
well with a post-mix score. Supports `image` and FLF2V (first-and-last
frame interpolation) modes.

## Switching backends per render

Each backend writes to a separate output folder under the same
episode:

| Backend | Output folder |
|---|---|
| `xai` | `episodes/<slug>/output/` |
| `fal` | `episodes/<slug>/output-fal/` |
| `wan` | `episodes/<slug>/output-wan/` |

So you can render the same manifest with all three and pick the best
take per scene. The studio UI's backend dropdown switches which
folder it's reading from; selection is persisted per browser.

## Security

- `.env` is gitignored by default. Never commit it.
- The studio web server binds to `127.0.0.1` by default. If you pass
  `--host 0.0.0.0` to expose it on your LAN, anyone on your network
  can trigger renders against your API keys. Don't do this on
  untrusted networks.
- The engine doesn't ship any telemetry or call-home logic.
