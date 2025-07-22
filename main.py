from typing import Iterator
import logging
import itertools
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import dotenv
from pathlib import Path
from base64 import b64encode
from schemas import Playlist, PlaylistBatch, Track, TrackBatch, User

dotenv.load_dotenv()
logger = logging.getLogger("sexport")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("spotipy").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

IMAGE = Path("assets/cover.jpeg")
EXPORT_PLAYLIST_NAME = "Ayo, fuck your tmp vibes, bro!"
MAX_SPOTI_STEP = 50
MAX_SPOTI_SIZE = 100


def liked_tracks(sp: spotipy.Spotify, *, step: int = MAX_SPOTI_STEP) -> Iterator[Track]:
    offset = 0
    while (
        results := sp.current_user_saved_tracks(limit=step, offset=offset)
    ) and results.get("items"):
        yield from TrackBatch.model_validate(
            (item["track"] for item in results["items"])
        ).root
        offset += step


def playlist_items(
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


def user_playlist_by_name(sp: spotipy.Spotify, playlist_name: str) -> Playlist | None:
    for pl in user_playlists(sp):
        if pl.name == playlist_name:
            return pl
    return None


def update_existing_export(sp: spotipy.Spotify, playlist: Playlist) -> None: ...


def reexport_existing_playlist(sp: spotipy.Spotify, playlist: Playlist) -> None:
    logger.info("Collecting playlist songs to clear playlist")
    for track_batch in itertools.batched(
        list(playlist_items(sp, playlist.id)), MAX_SPOTI_SIZE
    ):
        track_ids: list[str] = []
        for track in track_batch:
            logger.debug(f"removing %s", track.name)
            track_ids.append(track.id)
        sp.playlist_remove_all_occurrences_of_items(playlist.id, track_ids)
    export_to_playlist(sp, playlist.id)
    verify_export_match(sp, playlist.id)


def export_to_new_playlist(sp: spotipy.Spotify, playlist_name: str) -> None:
    user = User.model_validate(sp.current_user())
    playlist = Playlist.model_validate(sp.user_playlist_create(user.id, playlist_name))
    print(f"created playlist {playlist} as {user}")
    try:
        logger.info("Uploading playlist cover")
        sp.playlist_upload_cover_image(playlist.id, b64encode(IMAGE.read_bytes()))
        export_to_playlist(sp, playlist.id)
        verify_export_match(sp, playlist.id)
    except:
        logger.exception("export failed, deleting playlist")
        sp.user_playlist_unfollow(user.id, playlist.id)
        raise


def export_to_playlist(sp: spotipy.Spotify, playlist_id: str) -> None:
    for track_batch in itertools.batched(liked_tracks(sp), MAX_SPOTI_SIZE):
        track_ids: list[str] = []
        for track in track_batch:
            logger.debug("Adding %s", track.name)
            track_ids.append(track.id)
        sp.playlist_add_items(playlist_id, track_ids)


def verify_export_match(sp: spotipy.Spotify, playlist_id: str) -> None:
    logger.info("Verifying export")
    for liked_track, playlist_track in zip(
        liked_tracks(sp), playlist_items(sp, playlist_id), strict=True
    ):
        if liked_track.id != playlist_track.id:
            raise RuntimeError(
                "Export does not match the liked list: "
                f"({liked_track=}) != ({playlist_track=})"
            )


def main() -> None:
    scope = ["user-library-read", "playlist-modify-public", "ugc-image-upload"]

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    if playlist := user_playlist_by_name(sp, EXPORT_PLAYLIST_NAME):
        logger.warning(f"playlist already exists: {playlist}")
        reexport_existing_playlist(sp, playlist)
    else:
        logger.warning("playlist does not exists")
        export_to_new_playlist(sp, EXPORT_PLAYLIST_NAME)


if __name__ == "__main__":
    main()
