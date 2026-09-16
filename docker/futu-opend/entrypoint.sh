#!/bin/sh
set -eu

OPEND_BIN="/opt/futu-opend/OpenD"
if [ ! -x "$OPEND_BIN" ]; then
  echo "Futu OpenD binary missing at $OPEND_BIN"
  echo "Mount the official Linux OpenD directory to /opt/futu-opend (see docker/futu-opend/README.md)"
  exec sleep infinity
fi

exec "$OPEND_BIN"
