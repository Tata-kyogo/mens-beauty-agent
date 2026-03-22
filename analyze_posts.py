"""
analyze_posts.py — 投稿反応分析（将来実装用スケルトン）

実装予定:
  - Threads Insights API から投稿のインプレッション・いいね数・返信数を取得
  - post_history.json の post_ids を参照してデータを紐付け
  - 投稿タイプ（観察/分解/断言/予測）別のエンゲージメント傾向を分析
  - 高パフォーマンス投稿のパターンを reports/ に出力

Threads Insights API（参考）:
  GET https://graph.threads.net/v1.0/{media_id}/insights
    ?metric=views,likes,replies,reposts,quotes
    &access_token={THREADS_ACCESS_TOKEN}
"""
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"


def load_history() -> list:
    if not HISTORY_PATH.exists():
        print("[INFO] post_history.json が存在しません。")
        return []
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def print_summary(history: list):
    total = len(history)
    published = sum(1 for h in history if h.get("published"))
    print(f"総生成回数: {total}")
    print(f"投稿済み:   {published}")
    print(f"未投稿:     {total - published}")

    if not history:
        return

    # 文字数サマリー
    print("\n--- 文字数（直近5件）---")
    for entry in history[-5:]:
        print(f"  {entry['date']} / {entry['topic'][:20]}...")
        for post in entry.get("posts", []):
            print(f"    【{post['type']}】{post['chars']}字")


# TODO: エンゲージメント分析（トークン設定後に実装）
# def fetch_insights(post_id: str, token: str) -> dict:
#     import requests
#     url = f"https://graph.threads.net/v1.0/{post_id}/insights"
#     resp = requests.get(url, params={
#         "metric": "views,likes,replies,reposts,quotes",
#         "access_token": token,
#     })
#     resp.raise_for_status()
#     return resp.json()


def main():
    print("=== 投稿分析レポート（スケルトン）===\n")
    history = load_history()
    print_summary(history)
    print("\n※ エンゲージメント分析は Threads_ACCESS_TOKEN 設定後に実装予定。")


if __name__ == "__main__":
    main()
