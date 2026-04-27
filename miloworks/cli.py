"""MiloWorks CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from .config import (
    episodes_dir,
    get_api_key,
    get_fal_api_key,
    load_env,
    project_root,
    set_project,
)
from .init import scaffold_project
from .publish import publish_site
from .runner import generate_characters, run_episode, stitch_episode
from .xai_client import XaiClient, download

console = Console()


def _default_output_subdir(backend: str) -> str:
    """Keep each backend's renders in its own sibling folder.

    xAI stays at ``output/`` for backwards compatibility; other backends
    get ``output-<backend>/`` so you can render the same manifest with
    multiple providers and stitch each independently.
    """
    if backend == "xai":
        return "output"
    return f"output-{backend}"


def _resolve_api_key(backend: str) -> str | None:
    if backend == "xai":
        return get_api_key()
    if backend == "fal":
        return get_fal_api_key()
    return None


def _cmd_run(args: argparse.Namespace) -> int:
    load_env()
    output_subdir = args.output_subdir or _default_output_subdir(args.backend)
    run_episode(
        args.slug,
        api_key=_resolve_api_key(args.backend),
        only_scenes=args.scene or None,
        force=args.force,
        backend=args.backend,
        wan_base_url=args.wan_url,
        output_subdir=output_subdir,
    )
    return 0


def _cmd_stitch(args: argparse.Namespace) -> int:
    output_subdir = args.output_subdir or _default_output_subdir(args.backend)
    stitch_episode(args.slug, output_subdir=output_subdir)
    return 0


def _cmd_characters(args: argparse.Namespace) -> int:
    load_env()
    generate_characters(args.slug, api_key=get_api_key(), force=args.force)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import run_server

    proot = project_root()
    console.print(
        f"[bold green]MiloWorks[/bold green] · project: "
        f"[cyan]{proot.name}[/cyan] [dim]({proot})[/dim]"
    )
    console.print(f"  → http://{args.host}:{args.port}\n")
    run_server(host=args.host, port=args.port)
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    scaffold_project(target, name=args.name or target.name)
    console.print(
        f"[green]✓[/green] new MiloWorks project scaffolded at "
        f"[bold]{target}[/bold]\n\n"
        f"  cd {target.relative_to(Path.cwd()) if target.is_relative_to(Path.cwd()) else target}\n"
        f"  cp .env.example .env       [dim]# add your XAI_API_KEY[/dim]\n"
        f"  miloworks serve            [dim]# open http://127.0.0.1:8765[/dim]\n"
    )
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    site_dir = Path(args.site).resolve()
    site_dir.mkdir(parents=True, exist_ok=True)
    manifest = publish_site(
        site_dir,
        show_name=args.name,
        show_tagline=args.tagline,
        show_description=args.description or "",
        output_subdir=args.output_subdir,
    )
    n = len(manifest["episodes"])
    console.print(
        f"[green]✓[/green] published [bold]{n}[/bold] episode(s) to "
        f"[cyan]{site_dir}[/cyan]"
    )
    if n == 0:
        console.print(
            "[yellow]warning[/yellow]: no episodes had a final.mp4 to publish. "
            "Run [bold]miloworks run <slug>[/bold] first."
        )
    return 0


def _cmd_smoke(_: argparse.Namespace) -> int:
    load_env()
    client = XaiClient(api_key=get_api_key())
    console.print("[bold]Smoke test:[/bold] generating a 5s test clip…")
    result = client.generate_text_to_video(
        prompt=(
            "2D flat cartoon style, thick black outlines, bright saturated colors. "
            "A tiny mint-green blob with two dot eyes waves hello in a backyard."
        ),
        duration=5,
        aspect_ratio="16:9",
        resolution="480p",
    )
    out = episodes_dir() / "_smoke" / "test.mp4"
    download(result.url, out)
    console.print(f"[green]✓[/green] saved → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="miloworks",
        description=(
            "MiloWorks — make AI shorts from chained-prompt manifests. "
            "Run inside a project directory or pass --project."
        ),
    )
    parser.add_argument(
        "--project",
        default=None,
        help=(
            "Path to a MiloWorks project (a directory with episodes/ and "
            "style_bible.md). Defaults to walking up from cwd, or "
            "$MILOWORKS_PROJECT."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scaffold a new MiloWorks project")
    p_init.add_argument("path", help="Directory to create (e.g. ./my-show)")
    p_init.add_argument("--name", default=None, help="Show name (defaults to dir name)")
    p_init.set_defaults(func=_cmd_init, _skip_project=True)

    p_chars = sub.add_parser("characters", help="Generate character reference sheets")
    p_chars.add_argument("slug", help="Episode slug, e.g. ep00-the-landing")
    p_chars.add_argument("--force", action="store_true", help="Regenerate cached sheets")
    p_chars.set_defaults(func=_cmd_characters)

    p_run = sub.add_parser("run", help="Generate an episode")
    p_run.add_argument("slug", help="Episode slug, e.g. ep00-the-landing")
    p_run.add_argument(
        "--scene",
        action="append",
        help="Generate only these scene ids (can repeat). Skips stitch.",
    )
    p_run.add_argument("--force", action="store_true", help="Regenerate cached scenes")
    p_run.add_argument(
        "--backend",
        choices=("xai", "wan", "fal"),
        default="xai",
        help="Video generation backend (default: xai)",
    )
    p_run.add_argument(
        "--wan-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI base URL for the wan backend",
    )
    p_run.add_argument(
        "--output-subdir",
        default=None,
        help=(
            "Override the per-episode output folder name. Defaults to "
            "'output' for xai and 'output-<backend>' for everything else."
        ),
    )
    p_run.set_defaults(func=_cmd_run)

    p_stitch = sub.add_parser("stitch", help="Stitch existing scenes into final.mp4")
    p_stitch.add_argument("slug")
    p_stitch.add_argument(
        "--backend",
        choices=("xai", "wan", "fal"),
        default="xai",
        help="Which backend's output/ folder to stitch (default: xai)",
    )
    p_stitch.add_argument("--output-subdir", default=None)
    p_stitch.set_defaults(func=_cmd_stitch)

    p_smoke = sub.add_parser("smoke", help="Quick API/plumbing smoke test")
    p_smoke.set_defaults(func=_cmd_smoke)

    p_pub = sub.add_parser(
        "publish",
        help="Generate site/episodes.json + copy finals into site/videos/",
    )
    p_pub.add_argument(
        "--site", default="site", help="Site directory (default: ./site)"
    )
    p_pub.add_argument(
        "--name", required=True, help="Show name shown on the site (e.g. 'Milo')"
    )
    p_pub.add_argument(
        "--tagline", required=True, help="One-line tagline shown in the hero"
    )
    p_pub.add_argument(
        "--description",
        default="",
        help="Multi-paragraph description (use \\n\\n for breaks)",
    )
    p_pub.add_argument(
        "--output-subdir",
        default="output",
        help="Which backend's output/ folder to publish (default: output = xai)",
    )
    p_pub.set_defaults(func=_cmd_publish)

    p_serve = sub.add_parser(
        "serve", help="Run the local studio webapp (FastAPI)"
    )
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    if args.project:
        set_project(args.project)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
