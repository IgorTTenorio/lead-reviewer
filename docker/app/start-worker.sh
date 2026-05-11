#!/usr/bin/env sh
set -eu

exec celery -A worker.main.celery_app worker --loglevel=INFO
