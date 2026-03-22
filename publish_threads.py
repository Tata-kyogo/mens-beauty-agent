"""
publish_threads.py — Threads API への投稿

.env の THREADS_ACCESS_TOKEN / THREADS_USER_ID を使って投稿。
トークン未設定の場合は安全にスキップ（exit 0）。

Threads API フロー:
  1. メディアコンテナ作成: POST /v1.0/{user_id}/threads
  2. コンテナ公開:         POST /v1.0/{user_id}/threads_publish
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # python-dotenv 未インストール時は環境変数をそのまま使用

try:
    import requests
except ImportError:
    print("[ERROR] requests が未インストールです: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"
POST_LOG_PATH = BASE_DIR / "logs" / "post.log"

POST_TYPES = ["観察", "分解", "断言", "予測"]
THREADS_API_BASE = "https://graph.threads.net/v1.0"


def parse_posts(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    posts = {}
    for ptype in POST_TYPES:
        pattern = rf"【{ptype}】\s*\n(.*?)(?=【|\Z)"
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            posts[ptype] = match.group(1).strip()
    return posts


def create_container(user_id: str, token: str, text: str) -> str:
    """テキスト投稿コンテナを作成し creation_id を返す"""
    url = f"{THREADS_API_BASE}/{user_id}/threads"
    resp = requests.post(url, data={
        "media_type": "TEXT",
        "text": text,
        "access_token": token,
    }, timeout=30)
    resp.raise_for_status()
    creation_id = resp.json().get("id")
    if not creation_id:
        raise ValueError(f"creation_id が取得できませんでした: {resp.text}")
    return creation_id


def publish_container(user_id: str, token: str, creation_id: str) -> str:
    """コンテナを公開し post_id を返す"""
    url = f"{THREADS_API_BASE}/{user_id}/threads_publish"
    resp = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": token,
    }, timeout=30)
    resp.raise_for_status()
    post_id = resp.json().get("id")
    if not post_id:
        raise ValueError(f"post_id が取得できませんでした: {resp.text}")
    return post_id


def log_post(message: str):
    POST_LOG_PATH.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with POST_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def update_history_published(post_ids: list):
    """直近エントリの published フラグと post_ids を更新"""
    if not HISTORY_PATH.exists():
        return
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    if history:
        history[-1]["published"] = True
        history[-1]["post_ids"] = post_ids
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("THREADS_USER_ID", "").strip()

    if not token or not user_id:
        print("[SKIP] THREADS_ACCESS_TOKEN または THREADS_USER_ID が未設定。投稿をスキップします。")
        sys.exit(0)

    if not OUTPUT_PATH.exists():
        print("[ERROR] data/output.txt が存在しません", file=sys.stderr)
        sys.exit(1)

    posts = parse_posts(OUTPUT_PATH)
    if not posts:
        print("[ERROR] output.txt から投稿を取得できませんでした", file=sys.stderr)
        sys.exit(1)

    print(f"{len(posts)}本の投稿を Threads に送信します。")
    post_ids = []

    for ptype in POST_TYPES:
        if ptype not in posts:
            continue
        text = posts[ptype]
        print(f"  投稿中: 【{ptype}】({len(text)}字)...", end="", flush=True)
        try:
            creation_id = create_container(user_id, token, text)
            time.sleep(1)  # Threads API 推奨ウェイト
            post_id = publish_container(user_id, token, creation_id)
            post_ids.append(post_id)
            print(f" 完了 (id: {post_id})")
            log_post(f"投稿成功 | {ptype} | post_id={post_id} | {len(text)}字")
        except Exception as e:
            print(f" 失敗")
            log_post(f"投稿失敗 | {ptype} | {e}")
            print(f"[ERROR] 【{ptype}】投稿失敗: {e}", file=sys.stderr)

    if post_ids:
        update_history_published(post_ids)
        print(f"\n投稿完了: {len(post_ids)}本")
    else:
        print("\n[ERROR] 投稿に失敗しました。logs/post.log を確認してください。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
