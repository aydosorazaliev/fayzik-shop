#!/usr/bin/env python3
"""Fayzik FF Shop: sahifani beradi va akkauntlar ro'yxatini products.json da saqlaydi."""
import os, json, hmac, hashlib, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(os.environ.get("DATA_DIR", BASE), "products.json")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET = hashlib.sha256(("fz|" + PASSWORD).encode()).digest()
LOCK = threading.Lock()
GROUPS = {"cheap", "mid", "premium"}
TOKEN_TTL = 12 * 3600

DEFAULTS = [
    {"id": 1, "emoji": "🎮", "group": "cheap", "price": 150000, "level": 72, "skins": 12, "sold": False, "img": "",
     "name_uz": "12 ta skin, pochta almashadi", "name_ru": "12 скинов, почта меняется",
     "desc_uz": "Evolyutsion quroll bor. Akkaunt toza, ban bo‘lmagan.", "desc_ru": "Есть эво-оружие. Аккаунт чистый, без банов."},
    {"id": 2, "emoji": "👑", "group": "cheap", "price": 180000, "level": 65, "skins": 7, "sold": False, "img": "",
     "name_uz": "Elite Pass, eski bundle’lar", "name_ru": "Elite Pass, старые бандлы",
     "desc_uz": "Eski mavsum bundle’lari. Bog‘langan platforma va topshirish tartibini admin bilan aniqlashtiring.",
     "desc_ru": "Бандлы прошлых сезонов. Привязанную платформу и порядок передачи уточняйте у админа."},
    {"id": 3, "emoji": "🔫", "group": "mid", "price": 320000, "level": 80, "skins": 21, "sold": False, "img": "",
     "name_uz": "M1887 skin va 3 ta pet", "name_ru": "Скин M1887 и 3 питомца",
     "desc_uz": "M1887 skin va 3 ta pet mavjud.", "desc_ru": "Есть скин M1887 и 3 питомца."},
    {"id": 4, "emoji": "🏆", "group": "mid", "price": 560000, "level": 77, "skins": 30, "sold": False, "img": "",
     "name_uz": "Grandmaster reyting", "name_ru": "Рейтинг Грандмастер",
     "desc_uz": "Grandmaster reyting, 30 ta skin.", "desc_ru": "Рейтинг Грандмастер, 30 скинов."},
    {"id": 5, "emoji": "💎", "group": "premium", "price": 1250000, "level": 85, "skins": 44, "sold": False, "img": "",
     "name_uz": "Birinchi mavsum yutuqlari", "name_ru": "Достижения первого сезона",
     "desc_uz": "Birinchi mavsum yutuqlari va noyob kiyimlar.", "desc_ru": "Достижения первого сезона и редкая одежда."},
    {"id": 6, "emoji": "⚡", "group": "premium", "price": 3500000, "level": 88, "skins": 75, "sold": False, "img": "",
     "name_uz": "Mythic kiyim to‘plami", "name_ru": "Коллекция одежды Mythic",
     "desc_uz": "Mythic kiyim to‘plami.", "desc_ru": "Коллекция одежды Mythic."},
]


def num(v, lo=0, hi=10**10):
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return lo


def txt(v, n):
    return str(v or "").strip()[:n]


def clean(items):
    out, used = [], set()
    for it in items[:200]:
        if not isinstance(it, dict):
            continue
        img = txt(it.get("img"), 500)
        if img and not img.startswith("https://"):
            img = ""
        pid = num(it.get("id"), 0, 10**9)
        if pid == 0 or pid in used:
            pid = max(used | {0}) + 1
        used.add(pid)
        name_uz, name_ru = txt(it.get("name_uz"), 120), txt(it.get("name_ru"), 120)
        if not (name_uz or name_ru):
            continue
        out.append({
            "id": pid, "emoji": txt(it.get("emoji"), 8) or "🎮",
            "group": it.get("group") if it.get("group") in GROUPS else "cheap",
            "price": num(it.get("price")), "level": num(it.get("level"), 0, 999),
            "skins": num(it.get("skins"), 0, 9999), "sold": bool(it.get("sold")), "img": img,
            "name_uz": name_uz or name_ru, "name_ru": name_ru or name_uz,
            "desc_uz": txt(it.get("desc_uz"), 1000), "desc_ru": txt(it.get("desc_ru"), 1000),
        })
    return out


def load():
    with LOCK:
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return DEFAULTS


def save(items):
    with LOCK:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DATA_FILE)


def sign(exp):
    return hmac.new(SECRET, str(exp).encode(), hashlib.sha256).hexdigest()


def make_token():
    exp = int(time.time()) + TOKEN_TTL
    return f"{exp}.{sign(exp)}"


def check_token(tok):
    if not PASSWORD:
        return False
    try:
        exp, sig = tok.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, sign(int(exp)))
    except ValueError:
        return False


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def body(self):
        n = min(int(self.headers.get("Content-Length") or 0), 1_000_000)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        p = self.path.split("?")[0].split("#")[0]
        if p in ("/", "/index.html"):
            with open(os.path.join(BASE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if p == "/api/products":
            return self.send(200, {"products": load()})
        if p == "/healthz":
            return self.send(200, b"ok", "text/plain")
        self.send(404, {"error": "not found"})

    do_HEAD = do_GET

    def do_POST(self):
        if self.path.split("?")[0] != "/api/login":
            return self.send(404, {"error": "not found"})
        if not PASSWORD:
            return self.send(503, {"error": "ADMIN_PASSWORD o‘rnatilmagan (Render → Environment)"})
        given = str(self.body().get("password", ""))
        if hmac.compare_digest(given.encode(), PASSWORD.encode()):
            return self.send(200, {"token": make_token()})
        time.sleep(1)
        self.send(401, {"error": "Parol noto‘g‘ri"})

    def do_PUT(self):
        if self.path.split("?")[0] != "/api/products":
            return self.send(404, {"error": "not found"})
        auth = self.headers.get("Authorization", "")
        if not check_token(auth[7:] if auth.startswith("Bearer ") else ""):
            return self.send(401, {"error": "Qayta kiring"})
        items = self.body().get("products")
        if not isinstance(items, list):
            return self.send(400, {"error": "noto‘g‘ri ma’lumot"})
        items = clean(items)
        save(items)
        self.send(200, {"products": items})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    if not PASSWORD:
        print("DIQQAT: ADMIN_PASSWORD o'rnatilmagan, admin panel ishlamaydi.")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
