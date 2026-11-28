#!/bin/bash
# Ubuntu 24.04 (WSL): tools for szg-hub e2e tests
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates git python3 python3-pip python3-venv util-linux iproute2 >/dev/null
if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi
echo "node $(node -v)"
pip install --break-system-packages -q playwright
python3 -m playwright install --with-deps chromium 2>&1 | tail -2
python3 -c 'import playwright; print("playwright ok")'
