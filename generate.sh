#!/bin/bash

echo "=== 実行開始 ==="

echo "[1/2] 投稿生成..."
python3 write_posts.py

echo "[2/2] Threads投稿..."
python3 publish_threads.py

echo "=== 完了 ==="
