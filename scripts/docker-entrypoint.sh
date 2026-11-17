#!/bin/sh
# web: serve the demo run (copy of data/demo.db) on 0.0.0.0:8765 inside the container.
# test: run the test suite. Anything else runs as a command, e.g. `koc run --mock`.
set -e
case "$1" in
  web)
    [ -f data/koc.db ] || cp data/demo.db data/koc.db
    exec python -m koc.web --host 0.0.0.0 --port 8765 ;;
  test)
    shift
    exec python -m pytest -q -p no:cacheprovider "$@" ;;
  *)
    exec "$@" ;;
esac
