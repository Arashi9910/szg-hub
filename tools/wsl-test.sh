#!/bin/bash
# Sync repo into WSL and run e2e tests: BRANCH=<branch> wsl-test.sh [-j N] [tests...]
# Uncommitted changes are not copied: commit (or WIP-commit) first.
set -e
SRC="/mnt/d/自己寫程式的/上漲谷/szghub"
BR="${BRANCH:-claude/project-folder-access-fd00e7}"
DST="/root/wt/$(printf %s "$BR" | tr -c 'A-Za-z0-9._-' _)"  # 每個分支自己的資料夾，多個子任務可以同時跑
mkdir -p /root/wt
git config --global --add safe.directory '*' 2>/dev/null || true
if [ ! -d "$DST/.git" ]; then git init -q "$DST"; fi
cd "$DST"
git fetch -q "$SRC" "$BR"
git reset -q --hard FETCH_HEAD
chmod +x tools/*.sh 2>/dev/null || true
echo "repo at $(git log --oneline -1)"
python3 tools/run-tests.py "$@"
