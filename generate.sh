#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# .env 読み込み（存在する場合）
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

mkdir -p logs data

TS=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TS] === 実行開始 ===" | tee -a logs/run.log

# 1. テーマ選定
echo ""
echo "[1/4] テーマ選定 (research.py)..."
if ! python3 research.py; then
    echo "[ERROR] research.py 失敗" | tee -a logs/run.log
    exit 1
fi

# 2. 投稿生成
echo ""
echo "[2/4] 投稿生成 (write_posts.py)..."
if ! python3 write_posts.py; then
    echo "[ERROR] write_posts.py 失敗" | tee -a logs/run.log
    exit 1
fi

# 3. 品質チェック（警告は続行、致命的エラーのみ中断）
echo ""
echo "[3/4] 品質チェック (quality_check.py)..."
if ! python3 quality_check.py; then
    echo "[WARN] 品質チェックでエラーが検出されました。" | tee -a logs/run.log
    echo "       data/output.txt を確認して手動で修正するか、再実行してください。"
    exit 1
fi

# 4. Threads 投稿（トークン未設定なら自動スキップ）
echo ""
echo "[4/4] Threads 投稿 (publish_threads.py)..."
python3 publish_threads.py

TS=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "[$TS] === 完了 ===" | tee -a logs/run.log
