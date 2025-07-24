import logging
from pathlib import Path

import click
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from sexporter import exporter, iterators
from sexporter.schemas import ExcludeFilters, Playlist

logger = logging.getLogger(__name__)

EXPORT_PLAYLIST_NAME = "Ayo, fuck your bad vibes, bro!"
SCOPE = ["user-library-read", "playlist-modify-public", "ugc-image-upload"]


def user_playlist_by_name(sp: spotipy.Spotify, playlist_name: str) -> Playlist | None:
    """Returns user playlist by name if any."""
    for pl in iterators.user_playlists(sp):
        if pl.name == playlist_name:
            return pl
    return None


@click.command()
@click.option(
    "--playlist-name",
    default=EXPORT_PLAYLIST_NAME,
    help="Name of expoted playlist",
)
@click.option(
    "--update-mode",
    type=click.Choice(exporter.UpdateMode),
    default=exporter.UpdateMode.APPEND,
    help="Behavior when updating existing playlist",
)
@click.option(
    "--cover-image",
    type=Path,
    default=None,
    help="Cover image for the export playlist",
)
@click.option(
    "--exclude-file",
    type=Path,
    default=None,
    help="Path to liked songs exclude filters file",
)
def cli(
    playlist_name: str,
    update_mode: exporter.UpdateMode,
    cover_image: Path | None,
    exclude_file: Path | None,
) -> None:
    """CLI app."""
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))

    exclude_filters = None
    if exclude_file:
        exclude_filters = ExcludeFilters.model_validate_json(
            exclude_file.read_text(),
        ).filters

    if playlist := user_playlist_by_name(sp, playlist_name):
        logger.warning(f"Playlist already exists: {playlist}")
        exporter.export_to_existing_playlist(
            sp,
            playlist,
            mode=update_mode,
            cover_image=cover_image,
            exclude_filters=exclude_filters,
        )
    else:
        logger.warning("Playlist does not exists")
        exporter.export_to_new_playlist(
            sp,
            playlist_name,
            cover_image=cover_image,
            exclude_filters=exclude_filters,
        )
