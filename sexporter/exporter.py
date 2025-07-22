from collections.abc import Collection, Iterable
from enum import Enum, auto
import itertools
import logging
from base64 import b64encode
from pathlib import Path

import spotipy

from sexporter.schemas import Playlist, Track, TrackFilter, User
from sexporter import iterators

logger = logging.getLogger(__name__)

MAX_SPOTI_SIZE = 100


class UpdateMode(Enum):
    REEXPORT = auto()
    APPEND = auto()
    WALKTHROUGH = auto()


def append_to_existing_export(
    sp: spotipy.Spotify,
    playlist: Playlist,
    liked_tracks: Iterable[Track],
    playlist_tracks: Iterable[Track],
) -> None:
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

    for track_batch in itertools.batched(reversed(missing), MAX_SPOTI_SIZE):
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


def reexport_existing_playlist(
    sp: spotipy.Spotify,
    playlist: Playlist,
    liked_tracks: Iterable[Track],
    playlist_tracks: Iterable[Track],
) -> None:
    logger.info("Collecting playlist songs to clear playlist")
    for track_batch in itertools.batched(list(playlist_tracks), MAX_SPOTI_SIZE):
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
            reexport_existing_playlist(sp, playlist, liked_iter, playlist_iter)
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
    sp: spotipy.Spotify, playlist_id: str, liked_tracks: Iterable[Track]
) -> None:
    for track_batch in itertools.batched(liked_tracks, MAX_SPOTI_SIZE):
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
                f"({liked_track=}) != ({playlist_track=})"
            )


def set_playlist_cover(sp: spotipy.Spotify, playlist: Playlist, image: Path) -> None:
    logger.info("Uploading playlist cover")
    sp.playlist_upload_cover_image(playlist.id, b64encode(image.read_bytes()))
