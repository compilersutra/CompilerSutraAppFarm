#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Host-mounted /farm often has a different UID than the container user; git
# then refuses to use cache/sources ("dubious ownership"). Mark the tree safe.
set -eu
if command -v git >/dev/null 2>&1; then
  # '*' covers nested clones under cache/sources; /farm alone is not enough.
  git config --global --add safe.directory '*' 2>/dev/null || true
  git config --global --add safe.directory /farm 2>/dev/null || true
fi
exec csfarm "$@"
