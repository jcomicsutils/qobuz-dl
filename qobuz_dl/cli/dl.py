"""
cli/dl.py — The `dl` command: download albums, tracks, and artist discographies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from click.core import ParameterSource
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ..api import QobuzAPI
from ..config import get_meta_fields, load_config
from ..constants import DEFAULT_CONFIG, EXT_MAP, QUALITY_LABELS, QUALITY_MAP
from ..downloader import download_album, download_single_track, dry_run_album
from ..metadata import fetch_cover, fetch_cover_for_embed
from ..utils import (
    apply_version_to_title,
    clean_name,
    console,
    get_artists,
    get_main_artist,
    get_quality_tag,
    get_year,
    parse_targets,
    safe_format,
    strip_feat_from_album_title,
    strip_feat_from_track_title,
    truncate_name,
)
from .completions import _complete_id_prefixes

SEPARATORS = {"--next", "+", "--and"}


def _check_group_artist_overrides(tokens: List[str], resilient_parsing: bool = False) -> None:
    """Detect multiple -a / --override-main-artist flags in a single group."""
    if resilient_parsing:
        return
    count = 0
    for t in tokens:
        if t in ("-a", "--override-main-artist") or t.startswith("--override-main-artist="):
            count += 1
    if count > 1:
        raise click.ClickException(
            "Multiple -a / --override-main-artist flags detected in a single group without a separator.\n"
            "Use '--next' or '+' to separate artist groups, for example:\n"
            "  qobuz-dl dl ar-id 1 2 -a 'Artist 1' --next ar-id 3 -a 'Artist 2'"
        )


def split_groups(args: List[str], resilient_parsing: bool = False) -> List[List[str]]:
    """Split CLI arguments into target groups using separator flags (--next, +, --and)."""
    groups: List[List[str]] = []
    current: List[str] = []
    for arg in args:
        if arg in SEPARATORS:
            if not current:
                if not resilient_parsing:
                    if not groups:
                        raise click.ClickException(
                            f"Empty target group before separator {arg!r}. Place options or targets before the separator."
                        )
                    else:
                        raise click.ClickException(
                            "Empty target group between consecutive separators."
                        )
            else:
                _check_group_artist_overrides(current, resilient_parsing=resilient_parsing)
                groups.append(current)
                current = []
        else:
            current.append(arg)

    if not current and groups:
        if not resilient_parsing:
            raise click.ClickException(
                "Trailing separator with no following targets or options."
            )
        groups.append([])
    elif current:
        _check_group_artist_overrides(current, resilient_parsing=resilient_parsing)
        groups.append(current)

    return groups


class BatchDlCommand(click.Command):
    """Click command that intercepts separator flags to support batch groups."""

    def parse_args(self, ctx: click.Context, args: List[str]) -> List[str]:
        if any(h in args for h in ctx.help_option_names):
            return super().parse_args(ctx, args)
        groups = split_groups(args, resilient_parsing=ctx.resilient_parsing)
        ctx.meta["dl_group_args"] = [list(g) for g in groups]
        active_group = list(groups[-1]) if (ctx.resilient_parsing and groups) else (list(groups[0]) if groups else [])
        return super().parse_args(ctx, active_group)


def _run_download_group(
    api: QobuzAPI,
    targets: List[Tuple[str, str]],
    effective_cfg: Dict[str, Any],
    quality_id: str,
    root_dir: Path,
    f_tmpl: str,
    t_tmpl: str,
    dry_run: bool,
    override_main_artist: Optional[str],
    override_artist_id: bool,
) -> None:
    auto_override_id: bool        = override_artist_id or bool(override_main_artist)
    global_artist_id: Optional[str] = None

    if auto_override_id:
        explicit_artist_ids = [id_ for kind, id_ in targets if kind == "artist"]
        global_artist_id = explicit_artist_ids[0] if explicit_artist_ids else None

    for kind, id_ in targets:

        if kind == "album":
            if dry_run:
                res_id = dry_run_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id,
                )
            else:
                res_id = download_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id,
                )
            if auto_override_id and not global_artist_id and res_id:
                global_artist_id = res_id

        elif kind == "track":
            console.print("\n[bold]Fetching track info…[/]")
            try:
                track = api.get_track(id_)
                album = track.get("album", {})
                if album.get("id"):
                    try:
                        full_album    = api.get_album(str(album["id"]))
                        track["album"] = full_album
                        album          = full_album
                    except Exception:
                        pass

                if effective_cfg.get("include_version", False):
                    apply_version_to_title(track)
                    apply_version_to_title(album)
                if effective_cfg.get("strip_feat_from_track_title", False):
                    strip_feat_from_track_title(track)
                if effective_cfg.get("strip_feat_from_album_title", False):
                    strip_feat_from_album_title(album)

                artist      = get_artists(album) or track.get("performer", {}).get("name", "")
                main_artist = override_main_artist or get_main_artist(album) or track.get("performer", {}).get("name", "")

                actual_artist_id = str(album.get("artist", {}).get("id", ""))
                used_artist_id   = (global_artist_id or actual_artist_id) if auto_override_id else actual_artist_id

                folder = truncate_name(safe_format(
                    f_tmpl,
                    artist      = artist,
                    main_artist = main_artist,
                    album       = album.get("title", ""),
                    year        = get_year(album),
                    genre       = album.get("genre", {}).get("name", ""),
                    label       = album.get("label", {}).get("name", ""),
                    quality     = get_quality_tag(album),
                    artist_id   = used_artist_id,
                    album_id    = str(album.get("id", "")),
                ), effective_cfg, "folder")
                out_dir = root_dir / folder

                if dry_run:
                    ext      = EXT_MAP.get(quality_id, "flac")
                    track_no = track.get("track_number", 0)
                    disc_no  = track.get("media_number", 1)
                    title    = track.get("title", "Unknown")
                    filename = truncate_name(clean_name(safe_format(
                        t_tmpl,
                        track    = track_no,
                        disc     = disc_no,
                        title    = title,
                        artist   = (
                            get_artists(album) if album.get("artists") else
                            track.get("performer", {}).get("name", "Various Artists")
                        ),
                        album    = album.get("title", ""),
                        year     = get_year(album),
                        track_id = str(track.get("id", "")),
                    ) + f".{ext}"), effective_cfg, "filename")
                    dest = out_dir / filename

                    exists = dest.exists()
                    skip   = effective_cfg.get("skip_existing", True)
                    if exists and skip:
                        action_markup = "[dim]skip (exists)[/]"
                    elif exists:
                        action_markup = "[yellow]overwrite[/]"
                    else:
                        action_markup = "[green]download[/]"

                    console.print(
                        Panel(
                            f"[bold]{artist}[/] — [italic]{title}[/]\n"
                            f"[dim]Dest:[/] {dest}\n"
                            f"Action: {action_markup}",
                            title="[bold blue]Dry Run — Track[/]",
                            border_style="blue",
                        )
                    )

                    if auto_override_id and not global_artist_id and actual_artist_id:
                        global_artist_id = actual_artist_id
                    continue

                track_meta_flds     = get_meta_fields(effective_cfg)
                embed_cover_in_file = track_meta_flds is not None and track_meta_flds.get("cover", True)

                cover_size       = effective_cfg.get("cover_size", "original")
                embed_cover_size = effective_cfg.get("embed_cover_size", "original")
                oversize_action  = effective_cfg.get("embed_cover_oversize_action", "use_large")

                need_save  = bool(effective_cfg.get("save_cover"))
                need_embed = embed_cover_in_file

                cover_for_save:  Optional[bytes] = None
                cover_for_embed: Optional[bytes] = None

                if need_save or need_embed:
                    with console.status("Fetching cover art…"):
                        if need_save and need_embed and cover_size == embed_cover_size:
                            # Both purposes need the same size — fetch once, reuse.
                            data = fetch_cover_for_embed(
                                album, api.session, embed_cover_size, oversize_action
                            )
                            cover_for_save  = data
                            cover_for_embed = data
                        else:
                            if need_save:
                                cover_for_save = fetch_cover(album, api.session, cover_size)
                            if need_embed:
                                cover_for_embed = fetch_cover_for_embed(
                                    album, api.session, embed_cover_size, oversize_action
                                )

                if need_save and cover_for_save:
                    cp = out_dir / "cover.jpg"
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    if not cp.exists():
                        cp.write_bytes(cover_for_save)

                console.print(
                    Panel(
                        f"[bold]{artist}[/] — [italic]{track.get('title', '')}[/]",
                        title="[bold blue]Downloading Track[/]",
                        border_style="blue",
                    )
                )

                with Progress(
                    SpinnerColumn(), TextColumn("{task.description}"),
                    BarColumn(), DownloadColumn(), TransferSpeedColumn(),
                    TimeRemainingColumn(), console=console, transient=True,
                ) as progress:
                    ok = download_single_track(
                        api              = api,
                        track            = track,
                        out_dir          = out_dir,
                        track_tmpl       = t_tmpl,
                        quality_id       = quality_id,
                        cover            = cover_for_embed,
                        meta_fields      = track_meta_flds,
                        skip_existing    = effective_cfg.get("skip_existing", True),
                        progress         = progress,
                        cfg              = effective_cfg,
                        retries          = int(effective_cfg.get("retries", 3)),
                        on_final_failure = effective_cfg.get("on_final_failure", "delete_partial"),
                        force_main_album_artist = effective_cfg.get("force_main_album_artist", False),
                        override_main_artist    = override_main_artist,
                    )

                if ok:
                    console.print(f"\n[bold green]✓ Done![/]  →  {out_dir}\n")
                else:
                    console.print("\n[yellow]⚠ Track download failed.[/]\n")

                if auto_override_id and not global_artist_id and actual_artist_id:
                    global_artist_id = actual_artist_id

            except Exception as exc:
                console.print(f"[red]✗ {exc}[/]")

        elif kind == "artist":
            console.print("\n[bold]Fetching artist discography…[/]")
            try:
                for release_type in ("album", "epSingle", "live", "compilation"):
                    offset    = 0
                    page_size = 100
                    while True:
                        page = api.get_artist_releases(
                            id_,
                            release_type=release_type,
                            limit=page_size,
                            offset=offset,
                        )
                        items    = page.get("items", [])
                        has_more = page.get("has_more", False)
                        if not items:
                            break
                        console.print(
                            f"\n[bold]{release_type}[/] — "
                            f"{len(items)} release(s)"
                            + (" [dim](more available)[/]" if has_more else "")
                        )
                        for stub in items:
                            album_id = stub.get("id") or stub.get("qobuz_id")
                            if album_id:
                                if dry_run:
                                    res_id = dry_run_album(
                                        api, str(album_id), effective_cfg,
                                        quality_id, root_dir, f_tmpl, t_tmpl,
                                        override_main_artist, global_artist_id, auto_override_id,
                                    )
                                else:
                                    res_id = download_album(
                                        api, str(album_id), effective_cfg,
                                        quality_id, root_dir, f_tmpl, t_tmpl,
                                        override_main_artist, global_artist_id, auto_override_id,
                                    )
                                if auto_override_id and not global_artist_id and res_id:
                                    global_artist_id = res_id
                        if not has_more:
                            break
                        offset += page_size

            except Exception as exc:
                console.print(f"[red]✗ Artist download error: {exc}[/]")


@click.command("dl", cls=BatchDlCommand)
@click.argument(
    "urls", nargs=-1, required=True,
    metavar="URL [URL …]",
    shell_complete=_complete_id_prefixes,
)
@click.option("-d", "--dir", "download_dir",
              default=None, type=click.Path(file_okay=False, dir_okay=True),
              help="Override download directory")
@click.option("-q", "--quality",
              default=None, type=click.Choice(list(QUALITY_MAP)),
              help="Audio quality")
@click.option("-F", "--folder-template",
              default=None, help="Folder naming template")
@click.option("-f", "--track-template",
              default=None, help="Track filename template  (no extension)")
@click.option("-M", "--no-metadata", "no_metadata",
              is_flag=True, help="Skip metadata embedding")
@click.option("-C", "--no-cover", "no_cover",
              is_flag=True, help="Skip saving cover.jpg")
@click.option("-S", "--no-skip", "no_skip",
              is_flag=True, help="Re-download even if file exists")
@click.option("-n", "--dry-run", "dry_run",
              is_flag=True, help="Preview what would be downloaded — no files written")
@click.option("-r", "--retries",
              default=None, type=int, help="Override retry count on network failure")
@click.option("-a", "--override-main-artist",
              default=None, help="Override the main artist (Album Artist) for this run")
@click.option("-i", "--override-artist-id", is_flag=True, help=(
    "Force a single artist_id across all downloads in this run. "
    "The ID is taken from the first artist URL / ar-id target supplied; "
    "if no artist target is given it is inferred from the first album or track processed. "
))
@click.pass_context
def dl(
    ctx: click.Context,
    urls: Tuple[str, ...],
    download_dir: Optional[str],
    quality: Optional[str],
    folder_template: Optional[str],
    track_template: Optional[str],
    no_metadata: bool,
    no_cover: bool,
    no_skip: bool,
    dry_run: bool,
    retries: Optional[int],
    override_main_artist: Optional[str],
    override_artist_id: bool,
) -> None:
    """Download albums, tracks, or entire artist discographies.

    \b
    Targets — pass URLs or prefixed IDs, mix freely, batch as many as you like:
      qobuz-dl dl https://play.qobuz.com/album/0060253780948
      qobuz-dl dl https://play.qobuz.com/artist/5765466
      qobuz-dl dl ar-id 707261
      qobuz-dl dl al-id 0060253780948
      qobuz-dl dl tr-id 23929921
      qobuz-dl dl ar-id 707261 al-id 0060253780948 https://play.qobuz.com/track/229720604

    \b
    Prefixes:  ar-id = artist  |  al-id = album  |  tr-id = track
    Bare IDs without a prefix are rejected — the type would be ambiguous.

    \b
    Multiple pages for the same artist:
      Supply multiple artist IDs under the same artist override:
        qobuz-dl dl ar-id 1 2 -a "Artist 1"

    \b
    Batch downloads & multiple artists:
      Separate groups with --next or + to download multiple artists with distinct
      options (e.g. -a / --override-main-artist) in a single run:
        qobuz-dl dl ar-id 1 2 -a "Artist 1" --next ar-id 3 -a "Artist 2"
        qobuz-dl dl ar-id 1 2 -a "Artist 1" + ar-id 3 -a "Artist 2"
      General options (-q, -d, --dry-run, etc.) set in earlier groups are inherited
      by subsequent groups unless explicitly overridden.

    \b
    Common flags:
      -q cd                                    Quality override for this run
      --dry-run                                Preview without writing files
      -F "{main_artist}/{album} ({year})"      Custom folder template
      -f "{track:02d}. {title}"               Custom track filename template

    \b
    Template variables
    ──────────────────
    Folder:  {artist}  {main_artist}  {album}  {year}  {genre}  {label}
             {quality}  {artist_id}  {album_id}
    Track:   {track}  {track:02d}  {disc}  {title}  {artist}  {album}
             {year}  {track_id}
    """
    cfg = load_config()
    api = QobuzAPI(cfg)

    group_args_list = ctx.meta.get("dl_group_args", [])
    has_multiple_groups = len(group_args_list) > 1

    if has_multiple_groups:
        groups_params: List[Dict[str, Any]] = []
        base_params = {k: v for k, v in ctx.params.items() if k != "ctx"}

        cmd = ctx.command
        for idx, g_args in enumerate(group_args_list):
            sub_ctx = cmd.make_context(f"{ctx.info_name}[{idx}]", list(g_args), parent=ctx.parent)
            merged = dict(base_params)
            for p, val in sub_ctx.params.items():
                if p == "ctx":
                    continue
                if sub_ctx.get_parameter_source(p) == ParameterSource.COMMANDLINE:
                    merged[p] = val
                elif p in ("urls", "override_main_artist", "override_artist_id"):
                    merged[p] = val
            groups_params.append(merged)
    else:
        groups_params = [{k: v for k, v in ctx.params.items() if k != "ctx"}]

    any_dry_run = any(gp.get("dry_run") for gp in groups_params)
    if any_dry_run:
        console.print(
            Panel(
                "[bold yellow]Dry run[/] — resolving targets, no files will be written.",
                border_style="yellow",
            )
        )

    for idx, gp in enumerate(groups_params):
        if has_multiple_groups:
            artist_desc = f" [italic]({gp.get('override_main_artist')})[/]" if gp.get("override_main_artist") else ""
            console.rule(f"[bold cyan]Batch Group {idx + 1}/{len(groups_params)}{artist_desc}[/]")

        targets = parse_targets(gp["urls"])

        quality_val         = gp.get("quality")
        download_dir_val    = gp.get("download_dir")
        folder_tmpl_val     = gp.get("folder_template")
        track_tmpl_val      = gp.get("track_template")
        no_meta_val         = gp.get("no_metadata", False)
        no_cov_val          = gp.get("no_cover", False)
        no_sk_val           = gp.get("no_skip", False)
        dry_run_val         = gp.get("dry_run", False)
        retries_val         = gp.get("retries")
        override_artist_val = gp.get("override_main_artist")
        override_id_val     = gp.get("override_artist_id", False)

        quality_id = QUALITY_MAP.get(quality_val or cfg.get("quality", "hi-res-192"), "27")
        root_dir   = Path(download_dir_val or cfg.get("download_dir", str(Path.home() / "Music" / "Qobuz")))
        f_tmpl     = folder_tmpl_val or cfg.get("folder_template", DEFAULT_CONFIG["folder_template"])
        t_tmpl     = track_tmpl_val  or cfg.get("track_template",  DEFAULT_CONFIG["track_template"])

        effective_cfg = {
            **cfg,
            "embed_metadata": not no_meta_val and cfg.get("embed_metadata", True),
            "save_cover":     not no_cov_val  and cfg.get("save_cover",     True),
            "skip_existing":  not no_sk_val   and cfg.get("skip_existing",  True),
            "retries":        retries_val if retries_val is not None else int(cfg.get("retries", 3)),
        }

        console.print(
            f"[dim]Quality:[/] {QUALITY_LABELS.get(quality_id, quality_id)}  "
            f"[dim]|  Root:[/] {root_dir}\n"
        )

        _run_download_group(
            api                  = api,
            targets              = targets,
            effective_cfg        = effective_cfg,
            quality_id           = quality_id,
            root_dir             = root_dir,
            f_tmpl               = f_tmpl,
            t_tmpl               = t_tmpl,
            dry_run              = dry_run_val,
            override_main_artist = override_artist_val,
            override_artist_id   = override_id_val,
        )

    if any_dry_run:
        console.print("\n[bold yellow]Dry run complete — nothing was downloaded.[/]\n")

