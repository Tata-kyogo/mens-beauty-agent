"""
write_posts.py — 1テーマから4本のThreads投稿を生成

data/topic.txt を読み、Anthropic APIで4本生成。
output.txt に保存し、post_history.json に追記。
"""
import json
import os
import re
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

POST_TYPES = ["観察", "分解", "断言", "予測"]


def generate_posts(topic: str) -> dict:
    """Anthropic APIを使って4本の投稿を生成"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("環境変数 ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""以下のテーマについて、メンズ美容市場向けのThreads投稿を4本生成してください。

テーマ: {topic}

投稿タイプと要件:
1. 【観察】: 市場や消費者行動の変化を客観的に観察・描写する投稿。事実ベースで現状を伝える。
2. 【分解】: 消費行動や市場構造の背景にあるメカニズムを分解・分析する投稿。「なぜそうなるか」を掘り下げる。
3. 【断言】: 市場トレンドや消費者心理について断定的に主張する投稿。自信を持った断言口調で。
4. 【予測】: 今後の市場変化や消費行動の変化を予測する投稿。将来展望を示す。

各投稿の条件:
- 100〜140字程度（Threads投稿として適切な長さ）
- 改行なしの1段落
- メンズ美容市場の文脈に即した内容
- 読者の関心を引く表現

以下のJSON形式で出力してください（他のテキストは不要）:
{{
  "観察": "投稿文",
  "分解": "投稿文",
  "断言": "投稿文",
  "予測": "投稿文"
}}"""

    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(b.text for b in response.content if b.type == "text")

    # JSON部分を抽出してパース
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        raise ValueError(f"APIレスポンスからJSONを抽出できませんでした: {text}")

    posts = json.loads(m.group())

    # 必要なキーが揃っているか確認
    missing = [t for t in POST_TYPES if t not in posts]
    if missing:
        raise ValueError(f"APIレスポンスに不足しているタイプ: {missing}")

    return posts


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

    posts = generate_posts(topic)

    # output.txt に保存
    sep = "-" * 40
    lines = [sep]
    for ptype in POST_TYPES:
        if ptype in posts:
            lines.append(f"【{ptype}】")
            lines.append(posts[ptype])
            lines.append("")
    lines.append(sep)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # post_history.json に追記
    history = load_history()
    history.append({
        "date": date_str,
        "topic": topic,
        "posts": [
            {"type": t, "text": posts.get(t, ""), "chars": len(posts.get(t, ""))}
            for t in POST_TYPES
        ],
        "published": False,
        "post_ids": [],
    })
    save_history(history)

    # post_history.txt に追記（人間可読ログ）
    reason = ""
    if REASON_PATH.exists():
        lines = REASON_PATH.read_text(encoding="utf-8").strip().splitlines()
        # 直近の「理由:」行を取得
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
        for ptype in POST_TYPES:
            if ptype in posts:
                text = posts[ptype]
                f.write(f"【{ptype}】({len(text)}字)\n{text}\n\n")
        f.write("投稿済み: いいえ\n")
        f.write("=" * 45 + "\n\n")

    # run.log に追記
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [write] テーマ: {topic} | {len(posts)}本生成完了\n")

    print(f"\n{'='*40}")
    print(f"テーマ: {topic}")
    print(f"生成日時: {timestamp}")
    print(f"{'='*40}\n")
    for ptype in POST_TYPES:
        if ptype in posts:
            text = posts[ptype]
            print(f"【{ptype}】({len(text)}字)")
            print(text)
            print()
    print("保存先: data/output.txt")


if __name__ == "__main__":
    main()
