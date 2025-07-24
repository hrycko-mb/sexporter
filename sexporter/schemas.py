"""Spotify JSON pydantic schemas.

Most of the schemas are not full, because other info was not needed.
"""

from typing import Self

from pydantic import BaseModel, RootModel, model_validator


class Model(BaseModel):
    """Base model for shared configuration."""


class Playlist(Model):
    """Playlist schema."""

    id: str
    name: str


class Track(Model):
    """Track schema."""

    id: str
    name: str


class User(Model):
    """User schema."""

    id: str
    display_name: str | None = None


class TrackBatch(RootModel[list[Track]]):
    """Batch of tracks as a schema."""


class PlaylistBatch(RootModel[list[Playlist]]):
    """Batch of playlists as a schema."""


class TrackFilter(Model):
    """Track filter schema."""

    id: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_single_filter_set(self) -> Self:
        """Checks if one and only one of the fields is set."""
        if (not self.id and not self.name) or (self.id and self.name):
            raise ValueError("Only single filter shall be set, not zero, not both")
        return self

    def matches_filter(self, track: Track) -> bool:
        """Checks if the track matches the filter."""
        return bool(self.id and track.id == self.id) or bool(
            self.name and track.name == self.name,
        )


class ExcludeFilters(Model):
    """Exclude filters schema."""

    filters: list[TrackFilter]
