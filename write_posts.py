"""
write_posts.py — 1テーマから4本のThreads投稿を生成

data/topic.txt を読み、テンプレートで4本生成。
output.txt に保存し、post_history.json に追記。
"""
import json
import random
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOPIC_PATH = BASE_DIR / "data" / "topic.txt"
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"
HISTORY_TXT_PATH = BASE_DIR / "data" / "post_history.txt"
REASON_PATH = BASE_DIR / "data" / "topic_reason.txt"
LOG_PATH = BASE_DIR / "logs" / "run.log"

POST_TYPES = ["観察", "分解", "断言", "予測"]

# トピックからキーワードを抽出
def _extract(topic: str) -> dict:
    quoted = re.findall(r'「([^」]+)」', topic)
    # 先頭の主語候補（助詞の前まで）
    m = re.match(r'^([^\s、。にがはをのでも]{2,12})', topic)
    subject = m.group(1) if m else "この市場"
    # 短縮トピック（20字以内）
    topic_short = topic[:20] + ("…" if len(topic) > 20 else "")
    q0 = quoted[0] if quoted else "損失回避"
    q1 = quoted[1] if len(quoted) > 1 else "現在より将来"
    return {
        "subject": subject,
        "topic_short": topic_short,
        "q0": q0,
        "q1": q1,
    }

# 型別テンプレート（各2案、ランダム選択）
_TEMPLATES: dict[str, list[str]] = {
    "観察": [
        "{subject}への消費行動が変化している。「モテたい」ではなく「損したくない」——動機のシフトが市場の実態と合い始めた。数字より先に、現場の感覚として現れていた変化だ。",
        "{topic_short}という問い自体、消費者の動機が変わったサインだ。攻めではなく守りの論理で財布が開く。メンズ美容市場の構造は、静かに塗り替えられつつある。",
    ],
    "分解": [
        "{subject}への課金動機を分解すると、現在の改善より将来の損失回避が先に来る。「やらないと不利になる」という構造が購買を動かしている。市場の本質はここにある。",
        "この消費を分解すると「{q0}」が起点にある。見た目の改善ではなく、リスクの排除。その違いが購買行動の構造を決め、市場の伸び方も変えている。",
    ],
    "断言": [
        "{subject}に課金するのは未来への不安からだ。現在の見た目より将来の損失回避——その心理が財布を開かせる。市場は「{q0}」の文脈で伸びる。今後もその構造は変わらない。",
        "男性の美容消費は「よくなりたい」ではなく「悪くなりたくない」で動く。{topic_short}への答えは、すでに購買データが示している。市場の訴求軸はそこに集約される。",
    ],
    "予測": [
        "{subject}の市場は損失回避訴求でさらに拡大する。改善訴求に反応しない層も、減点回避なら動く。この構造が定着すれば、数年後には訴求軸の主流が入れ替わるだろう。",
        "「{q0}」を動機とした消費は増え続ける。基準が上がるたびに市場も広がる。防御的消費の拡大は一時的トレンドではなく、構造的変化として定着していく。",
    ],
}


def generate_posts(topic: str) -> dict:
    """テンプレートベースで4本の投稿を生成"""
    kw = _extract(topic)
    posts = {}
    for ptype in POST_TYPES:
        tmpl = random.choice(_TEMPLATES[ptype])
        posts[ptype] = tmpl.format(**kw)
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
