#!/bin/sh
set -e
exec gunicorn -w "$GUNICORN_WORKERS" -b 0.0.0.0:5000 app:app