#!/usr/bin/env python3
"""Fayzik FF Shop: sahifani beradi va akkauntlar ro'yxatini products.json da saqlaydi."""
import os, json, hmac, hashlib, time, threading
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(os.environ.get("DATA_DIR", BASE), "products.json")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET = hashlib.sha256(("fz|" + PASSWORD).encode()).digest()
LOCK = threading.Lock()
GROUPS = {"cheap", "mid", "premium"}
TOKEN_TTL = 12 * 3600
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
USE_DB = bool(SUPABASE_URL and SUPABASE_KEY)


def sb(method, path, body=None, prefer=None):
    """Supabase REST (PostgREST) so'rovi. Faqat serverda, service_role kaliti bilan."""
    headers = {"apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY,
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(SUPABASE_URL + "/rest/v1/" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"Supabase xato {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Supabase bilan aloqa yo'q") from exc


def to_row(p):
    r = dict(p)
    r["grp"] = r.pop("group", "cheap")
    return r


def from_row(r):
    p = {k: v for k, v in r.items() if k not in ("grp", "updated_at")}
    p["group"] = r.get("grp", "cheap")
    return p


def verify_telegram_init_data(init_data):
    """Validate Telegram Mini App initData before trusting its user details."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        from urllib.parse import parse_qsl
        fields = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = fields.pop("hash", "")
        if not received_hash:
            return None
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            return None
        auth_date = int(fields.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > 86400:
            return None
        user = json.loads(fields.get("user", "{}"))
        return user if isinstance(user, dict) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def telegram_send_message(text):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        raise RuntimeError("Render Environment'da BOT_TOKEN va ADMIN_CHAT_ID sozlanmagan.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Telegram'ga xabar yuborilmadi. Bot tokeni va chat ID ni tekshiring.") from exc
    if not result.get("ok"):
        raise RuntimeError("Telegram API xabarni qabul qilmadi. Bot admin chatda /start qilinganini tekshiring.")
    return result

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
    if USE_DB:
        rows = sb("GET", "products?select=*&order=id.asc")
        return [from_row(r) for r in rows or []]
    with LOCK:
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return DEFAULTS


def save(items):
    if USE_DB:
        with LOCK:
            if items:
                sb("POST", "products?on_conflict=id", [to_row(i) for i in items],
                   prefer="resolution=merge-duplicates,return=minimal")
                ids = ",".join(str(i["id"]) for i in items)
                sb("DELETE", f"products?id=not.in.({ids})", prefer="return=minimal")
            else:
                sb("DELETE", "products?id=gte.0", prefer="return=minimal")
        return
    with LOCK:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DATA_FILE)


def save_order(name, username, customer_id, lines, total):
    """Buyurtmani bazaga yozadi. Xato bo'lsa ham buyurtma Telegram'ga baribir yuboriladi."""
    if not USE_DB:
        return
    try:
        sb("POST", "orders", {"customer_name": name, "username": username, "telegram_id": customer_id,
                              "items": lines, "total": total}, prefer="return=minimal")
    except RuntimeError as exc:
        print("Buyurtmani saqlab bo'lmadi:", exc)


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
            try:
                return self.send(200, {"products": load()})
            except RuntimeError as exc:
                return self.send(502, {"error": str(exc)})
        if p == "/healthz":
            return self.send(200, b"ok", "text/plain")
        self.send(404, {"error": "not found"})

    do_HEAD = do_GET

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/order":
            return self.create_order()
        if path != "/api/login":
            return self.send(404, {"error": "not found"})
        if not PASSWORD:
            return self.send(503, {"error": "ADMIN_PASSWORD o‘rnatilmagan (Render → Environment)"})
        given = str(self.body().get("password", ""))
        if hmac.compare_digest(given.encode(), PASSWORD.encode()):
            return self.send(200, {"token": make_token()})
        time.sleep(1)
        self.send(401, {"error": "Parol noto‘g‘ri"})

    def create_order(self):
        if not BOT_TOKEN or not ADMIN_CHAT_ID:
            return self.send(503, {"error": "Buyurtma bot sozlanmagan. Render Environment'da BOT_TOKEN va ADMIN_CHAT_ID kerak."})
        data = self.body()
        raw_items = data.get("items")
        if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 30:
            return self.send(400, {"error": "Savat bo‘sh yoki buyurtma ma’lumoti noto‘g‘ri."})

        try:
            catalog = load()
        except RuntimeError as exc:
            return self.send(502, {"error": str(exc)})
        products = {int(p["id"]): p for p in catalog if isinstance(p, dict) and str(p.get("id", "")).isdigit()}
        lines, total = [], 0
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            pid = num(entry.get("id"), 0, 10**9)
            qty = num(entry.get("qty"), 0, 20)
            product = products.get(pid)
            if not product or product.get("sold") or qty < 1:
                return self.send(400, {"error": "Savatdagi mahsulot sotilgan yoki mavjud emas. Sahifani yangilang."})
            price = num(product.get("price"))
            subtotal = price * qty
            total += subtotal
            title = txt(product.get("name_uz") or product.get("name_ru"), 120)
            lines.append(f"• {title} × {qty} — {subtotal:,} so‘m".replace(",", " "))

        if not lines:
            return self.send(400, {"error": "Buyurtmada mahsulot topilmadi."})

        name = txt(data.get("name"), 80) or "Ko‘rsatilmagan"
        username = txt(data.get("username"), 80)
        if username and not username.startswith("@"):
            username = "@" + username
        tg_user = verify_telegram_init_data(txt(data.get("initData"), 5000))
        if tg_user:
            first = txt(tg_user.get("first_name"), 80)
            last = txt(tg_user.get("last_name"), 80)
            full = (first + " " + last).strip()
            if full:
                name = full
            if tg_user.get("username"):
                username = "@" + txt(tg_user.get("username"), 80)
            customer_id = str(tg_user.get("id", ""))
        else:
            customer_id = ""

        message = (
            "🛒 YANGI BUYURTMA — FAYZIK FF SHOP\n\n"
            + "\n".join(lines)
            + f"\n\n💰 JAMI: {total:,} so‘m".replace(",", " ")
            + f"\n👤 Xaridor: {name}"
            + f"\n📨 Username: {username or 'Ko‘rsatilmagan'}"
            + (f"\n🆔 Telegram ID: {customer_id}" if customer_id else "")
        )
        save_order(name, username, customer_id, lines, total)
        try:
            telegram_send_message(message)
        except RuntimeError as exc:
            return self.send(502, {"error": str(exc)})
        return self.send(200, {"ok": True, "message": "Buyurtmangiz adminga yuborildi!"})

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
        try:
            save(items)
        except RuntimeError as exc:
            return self.send(502, {"error": str(exc)})
        self.send(200, {"products": items})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    if USE_DB:
        try:
            if not sb("GET", "products?select=id&limit=1"):
                save(clean(DEFAULTS))  # birinchi ishga tushishda namunaviy akkauntlar
        except RuntimeError as exc:
            print("DIQQAT: Supabase'ga ulanib bo'lmadi:", exc)
    else:
        print("DIQQAT: SUPABASE_URL/SUPABASE_SERVICE_KEY yo'q, products.json ishlatiladi (Render'da o'chib ketadi).")
    if not PASSWORD:
        print("DIQQAT: ADMIN_PASSWORD o'rnatilmagan, admin panel ishlamaydi.")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
