"""Allow running as `python -m mws`."""

import sys

from mws.engine.aliases import resolve_alias

sys.argv[1:] = resolve_alias(sys.argv[1:])

from mws.cli import app  # noqa: E402

app()
