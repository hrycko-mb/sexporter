from typing import Any, Iterator, NamedTuple
import itertools
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import dotenv
from pathlib import Path
from base64 import b64encode

dotenv.load_dotenv()

IMAGE = Path("assets/cover.jpeg")
EXPORT_PLAYLIST_NAME = "Ayo, fuck your tmp vibes, bro!"
MAX_SPOTI_STEP = 50
MAX_SPOTI_SIZE = 100


def liked_tracks(
    sp: spotipy.Spotify, *, step: int = MAX_SPOTI_STEP
) -> Iterator[dict[str, Any]]:
    offset = 0
    while (
        results := sp.current_user_saved_tracks(limit=step, offset=offset)
    ) and results.get("items"):
        yield from results["items"]
        offset += step


def playlist_items(
    sp: spotipy.Spotify, playlist_id: str, *, step: int = MAX_SPOTI_STEP
) -> Iterator[dict[str, Any]]:
    offset = 0
    while (
        results := sp.playlist_items(playlist_id, limit=step, offset=offset)
    ) and results.get("items"):
        yield from results["items"]
        offset += step


class Playlist(NamedTuple):
    name: str
    id: str


def user_playlists(
    sp: spotipy.Spotify, *, step: int = MAX_SPOTI_STEP
) -> Iterator[Playlist]:
    offset = 0
    while (
        results := sp.current_user_playlists(limit=step, offset=offset)
    ) and results.get("items"):
        for item in results["items"]:
            yield Playlist(item["name"], item["id"])
        offset += step


def user_playlist_by_name(sp: spotipy.Spotify, playlist_name: str) -> Playlist | None:
    for pl in user_playlists(sp):
        if pl.name == playlist_name:
            return pl
    return None


def update_existing_export(sp: spotipy.Spotify, playlist: Playlist) -> None: ...


def reexport_existing_playlist(sp: spotipy.Spotify, playlist_id: str) -> None:
    for track_batch in itertools.batched(
        list(playlist_items(sp, playlist_id)), MAX_SPOTI_SIZE
    ):
        track_ids: list[str] = []
        for track in track_batch:
            print(f"removing {track['track']['name']}")
            track_ids.append(track["track"]["id"])
        sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
    export_to_playlist(sp, playlist_id)


def export_to_new_playlist(sp: spotipy.Spotify, playlist_name: str) -> None:
    user = sp.current_user()
    if user is None:
        raise RuntimeError("Auth failed")

    playlist = sp.user_playlist_create(user["id"], playlist_name)
    if playlist is None:
        raise RuntimeError("playlist creation failed")

    print(f"created playlist with id={playlist['id']}")
    try:
        print("Uploading playlist cover")
        sp.playlist_upload_cover_image(playlist["id"], b64encode(IMAGE.read_bytes()))
        export_to_playlist(sp, playlist["id"])
    except:
        print("export failed, deleting playlist")
        sp.user_playlist_unfollow(user["id"], playlist["id"])
        raise


def export_to_playlist(sp: spotipy.Spotify, playlist_id: str) -> None:
    for track_batch in itertools.batched(liked_tracks(sp), MAX_SPOTI_SIZE):
        track_ids = []
        for track in track_batch:
            print("Adding", track["track"]["name"])
            track_ids.append(track["track"]["id"])
        sp.playlist_add_items(playlist_id, track_ids)


def does_export_match(sp: spotipy.Spotify, playlist_id: str) -> bool:
    for liked_track, playlist_track in zip(
        liked_tracks(sp), playlist_items(sp, playlist_id), strict=True
    ):
        if liked_track != playlist_track:
            return False
    return True


def main() -> None:
    scope = ["user-library-read", "playlist-modify-public", "ugc-image-upload"]

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    if playlist := user_playlist_by_name(sp, EXPORT_PLAYLIST_NAME):
        print(f"playlist already exists: {playlist}")
        reexport_existing_playlist(sp, playlist.id)
    else:
        print("playlist does not exists")
        export_to_new_playlist(sp, EXPORT_PLAYLIST_NAME)


if __name__ == "__main__":
    main()
