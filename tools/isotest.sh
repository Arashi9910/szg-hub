#!/bin/sh
# 在「自己的網路＋自己的 /tmp」裡跑 e2e 測試，讓好幾份測試（不同 worktree）可以同時跑：
# 每份都有自己的 127.0.0.1:8787／9900 和 /tmp/hub，互不打架。測試程式本身不用改。
# 用法：tools/isotest.sh tests/e2e_raid.py [tests/e2e_smoke.py ...]   （在 repo 根目錄或 worktree 根目錄執行）
# 需要 Linux（含 Windows 的 WSL2）。Mac／原生 Windows 不能用，請照舊一次跑一支。
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
U="-nm"; [ "$(id -u)" = 0 ] || U="-rnm"   # 不是 root（例如 WSL 一般使用者）就用 user namespace
exec unshare $U --propagation private sh -c '
  mount -t tmpfs tmpfs /tmp && python3 "$0/tools/loup.py" || exit 97
  cd "$0"; rc=0
  for t in "$@"; do python3 "$t" || rc=1; done
  exit $rc' "$ROOT" "$@"
