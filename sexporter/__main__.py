import logging

import dotenv

from sexporter.cli import cli


def main() -> None:
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("spotipy").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    cli()


if __name__ == "__main__":
    main()
