#!/usr/bin/env bash

set -e

python3.8 -m venv .venv
. .venv/bin/activate
trap 'deactivate' EXIT

python src/server.py
