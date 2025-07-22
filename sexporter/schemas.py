from typing import Self
from pydantic import BaseModel, RootModel, model_validator


class Model(BaseModel): ...


class Playlist(Model):
    id: str
    name: str


class Artist(Model):
    id: str
    name: str


class Track(Model):
    id: str
    name: str
    artists: list[Artist]


class User(Model):
    id: str
    display_name: str | None = None


class TrackBatch(RootModel[list[Track]]): ...


class PlaylistBatch(RootModel[list[Playlist]]): ...


class TrackFilter(Model):
    id: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_single_filter_set(self) -> Self:
        if (not self.id and not self.name) or (self.id and self.name):
            raise ValueError("Only single filter shall be set, not zero, not both")
        return self

    def matches_filter(self, track: Track) -> bool:
        return bool(self.id and track.id == self.id) or bool(
            self.name and track.name == self.name
        )


class ExcludeFilters(Model):
    filters: list[TrackFilter]
