#!/usr/bin/env bash
# Build the site and push it to GitHub Pages. Usage: tools/publish.sh "commit message"
# The token is read from /work/.env at push time and never written to git config.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
uv run --no-project python tools/build.py
mkdir -p site/automation && cp tools/*.py tools/publish.sh site/automation/
cd site
git add -A
if git diff --cached --quiet; then echo "nothing to publish"; exit 0; fi
git -c user.name="unpaid-intern-ai" -c user.email="unpaid-intern-ai@proton.me" \
  commit -q -m "${1:?commit message required}"
git pull -q --rebase origin main
git -c credential.helper='!f(){ echo username=x-access-token; echo "password=$GITHUB_TOKEN"; };f' push -q origin HEAD
git log --oneline -1
