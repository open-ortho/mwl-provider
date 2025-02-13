#!/bin/bash
set -e

# Run database migrations
alembic upgrade head

# Start the MWL Provider using the installed entrypoint
exec mwl-provider "$@"
