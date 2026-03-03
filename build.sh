#!/bin/sh
# Cloudflare Pages build script
# Generates token.js from MAPBOX_TOKEN environment variable
# Set MAPBOX_TOKEN in CF Pages > Settings > Environment Variables

if [ -n "$MAPBOX_TOKEN" ]; then
    echo "// Generated at build time" > webapp/token.js
    echo "const MAPBOX_TOKEN = '$MAPBOX_TOKEN';" >> webapp/token.js
    echo "token.js generated from environment variable"
else
    echo "WARNING: MAPBOX_TOKEN not set, map will not load"
fi
