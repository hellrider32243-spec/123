#!/bin/bash
# certbot deploy-hook: после renew перечитать cert в Xray.
set -e
if command -v x-ui >/dev/null 2>&1; then
    x-ui restart-xray || systemctl restart x-ui
else
    systemctl restart x-ui
fi
