# sexporter

`sexporter` (short for Spotify exporter) is a tool which allows you to share all you liked songs with other people.
It let's you create a playlist which would contain all the songs in you likes in the same order, and even
to update it based on your liked songs when you add them.

## Getting started

First of all, you'll need to create a Spotify development token to give `sexporter` rights to access and modify
your playlists.
For app name and description you can put anything you'd want, e.g. just put `sexporter` in there.
For redirect URL some placeholder like `https://127.0.0.1:9090` can be put, we'll not use this one, so just fill-in.
Any other fields or checkboxes we should not worry about.

But what we'll need are the client ID and the client secret. We'll put them in place later, so keep an eye on them.

"user-library-read", "playlist-modify-public", "ugc-image-upload"

SPOTIPY_CLIENT_ID=''
SPOTIPY_CLIENT_SECRET=''
SPOTIPY_REDIRECT_URI=''
