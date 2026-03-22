"""
write_posts.py — 1テーマから4本のThreads投稿を生成

data/topic.txt を読み、Claude CLI で4本生成。
output.txt に保存し、post_history.json に追記。
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system.txt"
TOPIC_PATH = BASE_DIR / "data" / "topic.txt"
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"
HISTORY_TXT_PATH = BASE_DIR / "data" / "post_history.txt"
REASON_PATH = BASE_DIR / "data" / "topic_reason.txt"
LOG_PATH = BASE_DIR / "logs" / "run.log"

POST_TYPES = ["観察", "分解", "断言", "予測"]


def build_prompt(system: str, topic: str) -> str:
    return f"""{system}

---

テーマ: {topic}

このテーマでThreads投稿を4本作成してください。
それぞれ以下の型で1本ずつ書いてください。各投稿は100〜150字目安。

出力形式（この通りに出力してください）:

【観察】
（観察型の投稿本文）

【分解】
（分解型の投稿本文）

【断言】
（断言型の投稿本文）

【予測】
（予測型の投稿本文）"""


def parse_posts(raw: str) -> dict:
    posts = {}
    for ptype in POST_TYPES:
        pattern = rf"【{ptype}】\s*\n(.*?)(?=【|\Z)"
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            posts[ptype] = match.group(1).strip()
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
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = timestamp[:10]

    prompt = build_prompt(system_prompt, topic)

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Claude CLI 呼び出し失敗:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    raw_output = result.stdout.strip()
    posts = parse_posts(raw_output)

    if len(posts) < 4:
        missing = [t for t in POST_TYPES if t not in posts]
        print(f"[WARN] フォーマット不一致。不足: {missing}", file=sys.stderr)

    # output.txt に保存
    lines = [f"生成日時: {timestamp}", f"テーマ: {topic}", ""]
    for ptype in POST_TYPES:
        if ptype in posts:
            lines.append(f"【{ptype}】")
            lines.append(posts[ptype])
            lines.append("")
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
