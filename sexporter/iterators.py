from collections.abc import Collection, Iterator
import spotipy
from schemas import Playlist, PlaylistBatch, Track, TrackBatch, TrackFilter

MAX_SPOTI_STEP = 50


def liked_tracks(sp: spotipy.Spotify, *, step: int = MAX_SPOTI_STEP) -> Iterator[Track]:
    offset = 0
    while (
        results := sp.current_user_saved_tracks(limit=step, offset=offset)
    ) and results.get("items"):
        yield from TrackBatch.model_validate(
            (item["track"] for item in results["items"])
        ).root
        offset += step


def filtered_tracks(
    liked_tracks: Iterator[Track], exclude_filters: Collection[TrackFilter]
) -> Iterator[Track]:
    for track in liked_tracks:
        matches = False
        for filter in exclude_filters:
            matches = matches or filter.matches_filter(track)
        if not matches:
            yield track


def playlist_tracks(
    sp: spotipy.Spotify, playlist_id: str, *, step: int = MAX_SPOTI_STEP
) -> Iterator[Track]:
    offset = 0
    while (
        results := sp.playlist_items(playlist_id, limit=step, offset=offset)
    ) and results.get("items"):
        yield from TrackBatch.model_validate(
            (item["track"] for item in results["items"])
        ).root
        offset += step


def user_playlists(
    sp: spotipy.Spotify, *, step: int = MAX_SPOTI_STEP
) -> Iterator[Playlist]:
    offset = 0
    while (
        results := sp.current_user_playlists(limit=step, offset=offset)
    ) and results.get("items"):
        yield from PlaylistBatch.model_validate(results["items"]).root
        offset += step
