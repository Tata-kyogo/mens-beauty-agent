"""
get_token.py — Threads アクセストークン取得ヘルパー

.env の THREADS_APP_ID / THREADS_APP_SECRET を使って OAuth フローを実行し、
取得した ACCESS_TOKEN と USER_ID を .env に書き込む。

実行:
    python3 get_token.py
"""
import sys
import urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] pip install requests が必要です", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

THREADS_AUTH_URL = "https://threads.net/oauth/authorize"
THREADS_TOKEN_URL = "https://graph.threads.net/oauth/access_token"
THREADS_LONGTOKEN_URL = "https://graph.threads.net/access_token"
THREADS_ME_URL = "https://graph.threads.net/v1.0/me"
SCOPES = "threads_basic,threads_content_publish,threads_manage_insights"


def load_env() -> dict:
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def save_env(updates: dict):
    """既存の .env を保ちながら指定キーだけ上書き（なければ追記）"""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                updated_keys.add(k)
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def extract_code(raw: str) -> str:
    """リダイレクト先 URL 全体 or code 値のどちらにも対応"""
    if raw.startswith("http"):
        parsed = urllib.parse.urlparse(raw)
        code = urllib.parse.parse_qs(parsed.query).get("code", [""])[0]
        return code.split("#")[0]
    return raw.strip()


def main():
    env = load_env()
    app_id = env.get("THREADS_APP_ID", "").strip()
    app_secret = env.get("THREADS_APP_SECRET", "").strip()

    if not app_id or not app_secret:
        print("[ERROR] .env に THREADS_APP_ID と THREADS_APP_SECRET を設定してください。")
        sys.exit(1)

    print("=" * 50)
    print("Threads アクセストークン取得")
    print("=" * 50)

    # ---- Step 1: リダイレクト URI ----
    print("\n[Step 1] リダイレクト URI を入力してください。")
    print("  Meta Developer Portal > アプリ > Threads > リダイレクト URI に登録済みのもの。")
    print("  （例: https://localhost）")
    redirect_uri = input("  リダイレクト URI: ").strip()
    if not redirect_uri:
        redirect_uri = "https://localhost"

    # ---- Step 2: 認可 URL ----
    params = urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "response_type": "code",
    })
    auth_url = f"{THREADS_AUTH_URL}?{params}"

    print("\n[Step 2] 以下の URL をブラウザで開いて認証してください:")
    print(f"\n  {auth_url}\n")
    print("認証後にリダイレクトされた URL（または code= の値）を貼り付けてください。")
    raw_code = input("  >> ").strip()
    code = extract_code(raw_code)

    if not code:
        print("[ERROR] code を取得できませんでした。URL を確認してください。")
        sys.exit(1)

    # ---- Step 3: 短期トークン取得 ----
    print("\n[Step 3] 短期アクセストークンを取得中...")
    resp = requests.post(THREADS_TOKEN_URL, data={
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code,
    }, timeout=30)

    if not resp.ok:
        print(f"[ERROR] 短期トークン取得失敗: {resp.status_code} {resp.text}")
        sys.exit(1)

    short_token = resp.json().get("access_token")
    print("  短期トークン取得成功。")

    # ---- Step 4: 長期トークンへ交換 ----
    print("[Step 4] 長期トークン（60日）へ交換中...")
    resp2 = requests.get(THREADS_LONGTOKEN_URL, params={
        "grant_type": "th_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "access_token": short_token,
    }, timeout=30)

    if resp2.ok:
        data2 = resp2.json()
        long_token = data2.get("access_token", short_token)
        expires_in = int(data2.get("expires_in", 0))
        days = expires_in // 86400
        print(f"  長期トークン取得成功（有効期限: 約{days}日）。")
    else:
        long_token = short_token
        print(f"  [WARN] 長期トークン交換失敗（{resp2.status_code}）。短期トークンを使用します。")

    # ---- Step 5: User ID 取得 ----
    print("[Step 5] User ID を取得中...")
    resp3 = requests.get(THREADS_ME_URL, params={"access_token": long_token}, timeout=30)

    if not resp3.ok:
        print(f"[ERROR] User ID 取得失敗: {resp3.status_code} {resp3.text}")
        sys.exit(1)

    user_id = resp3.json().get("id")
    print(f"  User ID: {user_id}")

    # ---- Step 6: .env に保存 ----
    save_env({
        "THREADS_ACCESS_TOKEN": long_token,
        "THREADS_USER_ID": user_id,
    })

    print("\n" + "=" * 50)
    print(".env に保存しました。次回から bash generate.sh で投稿できます。")
    print(f"  THREADS_USER_ID   = {user_id}")
    print(f"  THREADS_ACCESS_TOKEN = （設定済み）")
    print("=" * 50)


if __name__ == "__main__":
    main()
