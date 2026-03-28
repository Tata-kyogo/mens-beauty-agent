"""
write_posts.py — 1テーマから1本のThreads投稿を生成

data/topic.txt を読み、Anthropic APIで1本生成。
output.txt に保存し、post_history.json に追記。
"""
import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent
TOPIC_PATH = BASE_DIR / "data" / "topic.txt"
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"
HISTORY_TXT_PATH = BASE_DIR / "data" / "post_history.txt"
REASON_PATH = BASE_DIR / "data" / "topic_reason.txt"
LOG_PATH = BASE_DIR / "logs" / "run.log"


def generate_post(topic: str) -> str:
    """Anthropic APIを使って1本の投稿を生成"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("環境変数 ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""以下のテーマについて、メンズ美容市場向けのThreads投稿を1本生成してください。

テーマ: {topic}

条件:
- 200〜280字程度（Threads投稿として適切な長さ）
- 観察・分析・主張・展望を自然にまとめた1段落
- メンズ美容市場の文脈に即した内容
- 読者の関心を引く表現
- 投稿文のみ出力（タイトルや説明は不要）"""

    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    return next(b.text for b in response.content if b.type == "text").strip()


def load_history() -> list:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return []


def save_history(history: list):
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    topic = TOPIC_PATH.read_text(encoding="utf-8").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = timestamp[:10]

    post = generate_post(topic)

    # output.txt に保存
    OUTPUT_PATH.write_text(post, encoding="utf-8")

    # post_history.json に追記
    history = load_history()
    history.append({
        "date": date_str,
        "topic": topic,
        "post": {"text": post, "chars": len(post)},
        "published": False,
        "post_ids": [],
    })
    save_history(history)

    # post_history.txt に追記（人間可読ログ）
    reason = ""
    if REASON_PATH.exists():
        lines = REASON_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in reversed(lines):
            if line.startswith("理由:"):
                reason = line[3:].strip()
                break
    with HISTORY_TXT_PATH.open("a", encoding="utf-8") as f:
        f.write("=" * 45 + "\n")
        f.write(f"日時: {timestamp}\n")
        f.write(f"テーマ: {topic}\n")
        if reason:
            f.write(f"採用理由: {reason}\n")
        f.write("-" * 45 + "\n")
        f.write(f"({len(post)}字)\n{post}\n\n")
        f.write("投稿済み: いいえ\n")
        f.write("=" * 45 + "\n\n")

    # run.log に追記
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [write] テーマ: {topic} | {len(post)}字生成完了\n")

    print(f"\n{'='*40}")
    print(f"テーマ: {topic}")
    print(f"生成日時: {timestamp}")
    print(f"{'='*40}\n")
    print(f"({len(post)}字)")
    print(post)
    print("\n保存先: data/output.txt")


if __name__ == "__main__":
    main()
