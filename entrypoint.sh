#!/bin/bash
set -e

# Run database migrations
alembic upgrade head

# Start the MWL Provider
exec python -m mwl_provider.main "$@"
