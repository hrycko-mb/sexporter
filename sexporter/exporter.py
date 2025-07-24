"""Spotify exporters."""

from io import BytesIO
import itertools
import logging
from base64 import b64encode
from collections.abc import Collection, Iterable
from enum import Enum, auto
from pathlib import Path

import spotipy
from PIL import Image

from sexporter import iterators
from sexporter.schemas import Playlist, Track, TrackFilter, User

logger = logging.getLogger(__name__)

MAX_SPOTI_INSERT_BATCH = 100
MAX_IMAGE_SIZE_BYTES = 250 * 1024


class UpdateMode(Enum):
    """Playlist update mode."""

    REEXPORT = auto()
    APPEND = auto()
    WALKTHROUGH = auto()


def append_to_existing_export(
    sp: spotipy.Spotify,
    playlist: Playlist,
    liked_tracks: Iterable[Track],
    playlist_tracks: Iterable[Track],
) -> None:
    """Appends new track from the top of liked tracks to the playlist.

    Tracks that are missing in the middle of the playlist are ignored.
    """
    try:
        top_playlist_track = next(iter(playlist_tracks))
    except StopIteration:
        logger.warning("Target playlist is empty, just exporting from liked")
        _export_liked_to_playlist(sp, playlist.id, liked_tracks)
        return

    logging.debug("Top playlist track is '%s'", top_playlist_track.name)
    missing: list[Track] = []
    for liked_track in liked_tracks:
        if liked_track != top_playlist_track:
            logging.debug("Track '%s' is missing", liked_track.name)
            missing.append(liked_track)
        else:
            break

    if not missing:
        logging.debug("No tracks to append")

    for track_batch in itertools.batched(reversed(missing), MAX_SPOTI_INSERT_BATCH):
        track_ids: list[str] = []
        for track in track_batch:
            logger.debug("Adding missing '%s'", track.name)
            track_ids.append(track.id)
        sp.playlist_add_items(playlist.id, track_ids, position=0)


def walkthrough_update_existing_export(
    sp: spotipy.Spotify,
    playlist: Playlist,
    liked_tracks: Iterable[Track],
    playlist_tracks: Iterable[Track],
) -> None:
    """Walks through liked tracks inserting missing one to the playlist."""
    playlist_iter = iter(playlist_tracks)
    liked_iter = iter(liked_tracks)
    try:
        cur_playlist_track = next(playlist_iter)
    except StopIteration:
        logger.warning("Target playlist is empty, just exporting from liked")
        _export_liked_to_playlist(sp, playlist.id, liked_tracks)
        return

    missing_at_pos: list[tuple[Track, int]] = []
    try:
        for cur_pos, liked_track in enumerate(liked_iter):
            if liked_track == cur_playlist_track:
                cur_playlist_track = next(playlist_iter)
                continue
            logging.debug(
                "Missing track '%s' before '%s' at position %d",
                liked_track.name,
                cur_playlist_track.name,
                cur_pos,
            )
            missing_at_pos.append((liked_track, cur_pos))
    except StopIteration:
        pass

    for track, pos in missing_at_pos:
        logging.debug(
            "Inserting missing track '%s' at position %d",
            track.name,
            pos,
        )
        sp.playlist_add_items(playlist.id, [track.id], position=pos)

    # export the rest of liked tracks
    _export_liked_to_playlist(sp, playlist.id, liked_iter)


def reexport_to_existing_playlist(
    sp: spotipy.Spotify,
    playlist: Playlist,
    liked_tracks: Iterable[Track],
    playlist_tracks: Iterable[Track],
) -> None:
    """Removes all tracks from the playlist and then inserts all liked songs into the playlist."""
    logger.info("Collecting playlist tracks to clear playlist")
    for track_batch in itertools.batched(list(playlist_tracks), MAX_SPOTI_INSERT_BATCH):
        track_ids: list[str] = []
        for track in track_batch:
            logger.debug("Removing %s", track.name)
            track_ids.append(track.id)
        sp.playlist_remove_all_occurrences_of_items(playlist.id, track_ids)
    _export_liked_to_playlist(sp, playlist.id, liked_tracks)


def export_to_existing_playlist(
    sp: spotipy.Spotify,
    playlist: Playlist,
    *,
    mode: UpdateMode,
    cover_image: Path | None = None,
    exclude_filters: Collection[TrackFilter] | None = None,
) -> None:
    """Exports liked tracks to the existing playlist as per mode.

    Args:
        sp (spotipy.Spotify): Spotify client instance.
        playlist (Playlist): Target playlist.
        mode (UpdateMode): The way of updating the playlist.
        cover_image (Path | None, optional): If provided, the cover image of the playlist will be updated. Defaults to None.
        exclude_filters (Collection[TrackFilter] | None, optional): Tracks to skip during exporting. If tracks are already in the playlist, they are not removed. Defaults to None.
    """
    exclude_filters = exclude_filters or []
    liked_iter = iterators.liked_tracks(sp)
    if exclude_filters:
        logger.info("Filters were supplied, applying")
        liked_iter = iterators.filtered_tracks(liked_iter, exclude_filters)
    playlist_iter = iterators.playlist_tracks(sp, playlist.id)
    if cover_image:
        set_playlist_cover(sp, playlist, cover_image)
    logging.info("Exporting to existing playlist in %s mode", mode)
    match mode:
        case UpdateMode.REEXPORT:
            reexport_to_existing_playlist(sp, playlist, liked_iter, playlist_iter)
        case UpdateMode.APPEND:
            append_to_existing_export(sp, playlist, liked_iter, playlist_iter)
        case UpdateMode.WALKTHROUGH:
            walkthrough_update_existing_export(sp, playlist, liked_iter, playlist_iter)
    verify_export_match(sp, playlist.id, exclude_filters=exclude_filters)


def export_to_new_playlist(
    sp: spotipy.Spotify,
    playlist_name: str,
    *,
    cover_image: Path | None = None,
    exclude_filters: Collection[TrackFilter] | None = None,
) -> None:
    """Creates new playlist and exports all liked tracks into it.

    Args:
        sp (spotipy.Spotify): Spotify client instance.
        playlist_name (str): Name of the new playlist.
        cover_image (Path | None, optional): If provided, the cover image of the playlist will be updated. Defaults to None.
        exclude_filters (Collection[TrackFilter] | None, optional): Tracks to skip during exporting. If tracks are already in the playlist, they are not removed. Defaults to None.
    """
    exclude_filters = exclude_filters or []
    user = User.model_validate(sp.current_user())
    playlist = Playlist.model_validate(sp.user_playlist_create(user.id, playlist_name))
    print(f"Created playlist {playlist} as {user}")
    try:
        if cover_image:
            set_playlist_cover(sp, playlist, cover_image)
        liked_iter = iterators.liked_tracks(sp)
        if exclude_filters:
            logger.info("Filters were supplied, applying")
            liked_iter = iterators.filtered_tracks(liked_iter, exclude_filters)
        _export_liked_to_playlist(sp, playlist.id, liked_iter)
        verify_export_match(sp, playlist.id, exclude_filters=exclude_filters)
    except:
        logger.exception("Export failed, deleting playlist")
        sp.user_playlist_unfollow(user.id, playlist.id)
        raise


def _export_liked_to_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    liked_tracks: Iterable[Track],
) -> None:
    """Exports all liked tracks to the playlist by id."""
    for track_batch in itertools.batched(liked_tracks, MAX_SPOTI_INSERT_BATCH):
        track_ids: list[str] = []
        for track in track_batch:
            logger.debug("Adding %s", track.name)
            track_ids.append(track.id)
        sp.playlist_add_items(playlist_id, track_ids)


def verify_export_match(
    sp: spotipy.Spotify,
    playlist_id: str,
    *,
    exclude_filters: Collection[TrackFilter] | None = None,
) -> None:
    """Verifies that liked tracks are equal to the playlist tracks.

    If filters are given, filtered tracks are expected to be missing in the playlist.
    """
    exclude_filters = exclude_filters or []
    logger.info("Verifying export")
    liked_iter = iterators.liked_tracks(sp)
    if exclude_filters:
        liked_iter = iterators.filtered_tracks(liked_iter, exclude_filters)
    for liked_track, playlist_track in zip(
        liked_iter,
        iterators.playlist_tracks(sp, playlist_id),
        strict=True,
    ):
        if liked_track.id != playlist_track.id:
            raise RuntimeError(
                "Export does not match the liked list: "
                f"({liked_track=}) != ({playlist_track=})",
            )


def set_playlist_cover(sp: spotipy.Spotify, playlist: Playlist, image: Path) -> None:
    """Sets playlist cover image, shrinking if needed."""
    logger.info("Uploading playlist cover")
    file_size = image.stat().st_size
    size_ratio = (
        1 if file_size < MAX_IMAGE_SIZE_BYTES else MAX_IMAGE_SIZE_BYTES / file_size
    )
    with Image.open(image) as img:
        img.resize((int(img.size[0] * size_ratio), int(img.size[1] * size_ratio)))
        buff = BytesIO()
        img.save(buff, format="JPEG")
        sp.playlist_upload_cover_image(playlist.id, b64encode(buff.getvalue()))
