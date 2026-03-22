"""
quality_check.py — 生成投稿の品質チェック

チェック項目:
  - 文字数（80〜200字の範囲外を警告）
  - 論文調・硬すぎる表現の検出
  - 投稿間の類似度（同じ回の4本同士）
  - 直近履歴との重複チェック

exit 0: 通過（警告があっても続行可能）
exit 1: 致命的エラー（投稿が取得できないなど）
"""
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "data" / "output.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"

POST_TYPES = ["観察", "分解", "断言", "予測"]

CHAR_MIN = 80
CHAR_MAX = 200
SIMILARITY_THRESHOLD = 0.5   # 50%以上の n-gram 重複で類似と判定
HISTORY_CHECK_COUNT = 5       # 直近何件と比較するか

# 論文調・硬すぎる表現パターン
HARD_PATTERNS = [
    r"においては",
    r"に関しては",
    r"に関する",
    r"と考えられる",
    r"と思われる",
    r"であると言える",
    r"と言えよう",
    r"の観点から",
    r"する傾向がある",
    r"傾向が見られる",
    r"することができる",
    r"であろう",
    r"と思っている",
]


def parse_posts(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    posts = {}
    for ptype in POST_TYPES:
        pattern = rf"【{ptype}】\s*\n(.*?)(?=【|\Z)"
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            posts[ptype] = match.group(1).strip()
    return posts


def ngram_similarity(a: str, b: str, n: int = 3) -> float:
    """文字 n-gram による類似度（0.0〜1.0）"""
    def ngrams(s):
        return set(s[i:i + n] for i in range(len(s) - n + 1))
    ng_a, ng_b = ngrams(a), ngrams(b)
    if not ng_a or not ng_b:
        return 0.0
    return len(ng_a & ng_b) / min(len(ng_a), len(ng_b))


def check_length(ptype: str, text: str) -> list:
    n = len(text)
    if n < CHAR_MIN:
        return [f"【{ptype}】短すぎ ({n}字 < {CHAR_MIN}字)"]
    if n > CHAR_MAX:
        return [f"【{ptype}】長すぎ ({n}字 > {CHAR_MAX}字)"]
    return []


def check_hardness(ptype: str, text: str) -> list:
    issues = []
    for pat in HARD_PATTERNS:
        if re.search(pat, text):
            issues.append(f"【{ptype}】硬い表現: 「{pat}」")
    return issues


def check_cross_similarity(posts: dict) -> list:
    issues = []
    keys = list(posts.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            sim = ngram_similarity(posts[keys[i]], posts[keys[j]])
            if sim >= SIMILARITY_THRESHOLD:
                issues.append(
                    f"【{keys[i]}】と【{keys[j]}】が類似 ({sim:.0%})"
                )
    return issues


def check_history_overlap(posts: dict) -> list:
    issues = []
    if not HISTORY_PATH.exists():
        return issues
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    # 直近エントリ（今回 write_posts.py が書いたもの）を除外して比較
    past = history[:-1] if history else []
    recent = past[-HISTORY_CHECK_COUNT:] if len(past) > HISTORY_CHECK_COUNT else past
    for entry in recent:
        for past_post in entry.get("posts", []):
            past_text = past_post.get("text", "")
            if not past_text:
                continue
            for ptype, text in posts.items():
                sim = ngram_similarity(text, past_text)
                if sim >= SIMILARITY_THRESHOLD:
                    issues.append(
                        f"【{ptype}】過去と類似 "
                        f"({entry['date']} / {past_post['type']} / {sim:.0%})"
                    )
    return issues


def main():
    if not OUTPUT_PATH.exists():
        print("[ERROR] data/output.txt が存在しません", file=sys.stderr)
        sys.exit(1)

    posts = parse_posts(OUTPUT_PATH)
    if not posts:
        print("[ERROR] 投稿が1本も取得できませんでした", file=sys.stderr)
        sys.exit(1)

    warnings = []
    for ptype, text in posts.items():
        warnings.extend(check_length(ptype, text))
        warnings.extend(check_hardness(ptype, text))
    warnings.extend(check_cross_similarity(posts))
    warnings.extend(check_history_overlap(posts))

    # サマリー表示
    print(f"[品質チェック] {len(posts)}本確認")
    for ptype in POST_TYPES:
        if ptype in posts:
            print(f"  【{ptype}】{len(posts[ptype])}字")

    if warnings:
        print(f"\n[警告] {len(warnings)}件")
        for w in warnings:
            print(f"  ⚠ {w}")
    else:
        print("\n警告なし。")

    # 致命的エラー: 投稿数不足のみ hard fail
    if len(posts) < 4:
        missing = [t for t in POST_TYPES if t not in posts]
        print(f"\n[ERROR] 投稿が不足: {missing}", file=sys.stderr)
        sys.exit(1)

    print("\n品質チェック通過。")
    sys.exit(0)


if __name__ == "__main__":
    main()
