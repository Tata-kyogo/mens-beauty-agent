import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system.txt"
TOPIC_PATH = BASE_DIR / "data" / "topic.txt"
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
LOG_PATH = BASE_DIR / "logs" / "run.log"


def build_prompt(system: str, topic: str) -> str:
    return f"""{system}

---

テーマ: {topic}

このテーマでThreads投稿を4本作成してください。
それぞれ以下の型で1本ずつ書いてください。各投稿は120〜220字。

出力形式（この通りに出力してください）:

【観察】
（観察型の投稿本文）

【分解】
（分解型の投稿本文）

【断言】
（断言型の投稿本文）

【予測】
（予測型の投稿本文）"""


def main():
    topic = TOPIC_PATH.read_text(encoding="utf-8").strip()
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prompt = build_prompt(system_prompt, topic)

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        check=True,
    )

    output = result.stdout.strip()

    # data/output.txt に保存
    OUTPUT_PATH.write_text(
        f"生成日時: {timestamp}\nテーマ: {topic}\n\n{output}\n",
        encoding="utf-8",
    )

    # logs/run.log に追記
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] テーマ: {topic} | 4本生成完了\n")

    # ターミナルに表示
    print(f"\n{'='*41}")
    print(f"テーマ: {topic}")
    print(f"生成日時: {timestamp}")
    print(f"{'='*41}\n")
    print(output)
    print(f"\n{'-'*41}")
    print("保存先: data/output.txt")
    print("ログ:   logs/run.log")


if __name__ == "__main__":
    main()
