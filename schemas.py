from pydantic import BaseModel, RootModel


class Model(BaseModel): ...


class Playlist(Model):
    id: str
    name: str


class Track(Model):
    id: str
    name: str


class User(Model):
    id: str
    display_name: str | None = None


class TrackBatch(RootModel[list[Track]]): ...


class PlaylistBatch(RootModel[list[Playlist]]): ...
