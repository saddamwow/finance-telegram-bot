from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from threading import Thread
from flask import Flask
import os
import re
import json
import urllib.request
import urllib.parse

keep_alive_app = Flask(__name__)

@keep_alive_app.route("/")
def home():
    return "Bot is alive"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    keep_alive_app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_DB_URL = os.getenv("REPLIT_DB_URL")


class _ReplitDB:
    def __contains__(self, key):
        return self[key] is not None

    def __getitem__(self, key):
        try:
            url = f"{_DB_URL}/{urllib.parse.quote(key, safe='')}"
            with urllib.request.urlopen(url) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    def __setitem__(self, key, value):
        data = urllib.parse.urlencode({key: json.dumps(value)}).encode()
        req = urllib.request.Request(_DB_URL, data=data, method="POST")
        urllib.request.urlopen(req)

db = _ReplitDB()

if "saldo" not in db:
    db["saldo"] = 0

if "history" not in db:
    db["history"] = []

if "learned_categories" not in db:
    db["learned_categories"] = {}


def format_rupiah(n):
    return f"Rp{n:,}".replace(",", ".")


def parse_nominal(text):
    text = text.lower().replace(".", "").replace(",", "")
    patterns = re.findall(r"(\d+)\s?(rb|ribu|k|jt|juta)?", text)

    if not patterns:
        return None

    angka, satuan = patterns[-1]
    nominal = int(angka)

    if satuan in ["rb", "ribu", "k"]:
        nominal *= 1000
    elif satuan in ["jt", "juta"]:
        nominal *= 1000000

    return nominal


def detect_tipe(text):
    text = text.lower()

    income_words = [
        "gaji", "gajian", "salary", "bonus", "thr", "cashback",
        "refund", "dibayar", "bayaran", "masuk", "transfer masuk",
        "dapat", "dapet", "terima", "saldo awal"
    ]

    if any(word in text for word in income_words):
        return "IN"

    return "OUT"


def detect_kategori(text):
    text = text.lower()

    learned = db["learned_categories"] or {}
    for keyword, kategori in learned.items():
        if keyword.lower() in text:
            return kategori

    kategori_map = {
        "makan": ["makan", "mie", "ayam", "nasi", "bakso", "ramen", "seblak", "warteg", "resto"],
        "minum": ["kopi", "matcha", "teh", "boba", "minum", "starbucks", "janji jiwa", "mixue"],
        "transport": ["bensin", "grab", "gojek", "ojol", "parkir", "tol", "kereta", "lrt", "bus", "krl"],
        "belanja": ["belanja", "shopee", "tokopedia", "lazada", "tiktok shop", "skincare"],
        "rumah": ["listrik", "air", "kontrakan", "sewa", "ipl", "wifi", "internet"],
        "kesehatan": ["obat", "dokter", "klinik", "vitamin", "apotek"],
        "hiburan": ["bioskop", "netflix", "spotify", "game", "jalan"],
        "investasi": ["saham", "reksadana", "bibit", "stock", "bbca", "bmri", "antm"],
        "income": ["gaji", "gajian", "bonus", "thr", "cashback", "refund", "saldo awal"]
    }

    for kategori, keywords in kategori_map.items():
        if any(word in text for word in keywords):
            return kategori

    return "lainnya"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot keuangan aktif 😭\n\n"
        "Langsung ketik aja:\n"
        "makan mie ayam 30rb\n"
        "gajian 6 juta\n"
        "beli bensin 25000\n"
        "saldo awal 3250000\n\n"
        "Command:\n"
        "/saldo\n"
        "/history\n"
        "/report\n"
        "/monthly\n"
        "/setkategori keyword kategori\n"
        "/kategori\n"
        "/reset"
    )


async def cek_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💳 Saldo sekarang:\n{format_rupiah(db['saldo'] or 0)}"
    )


async def reset_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["saldo"] = 0
    db["history"] = []

    await update.message.reply_text(
        "🔄 Saldo & history berhasil direset jadi kosong.\n"
        "Kategori custom tetap aman.\n\n"
        "Masukin saldo awal real, contoh:\n"
        "saldo awal 3250000"
    )


async def set_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Format salah bor 😭\n"
            "Contoh:\n"
            "/setkategori krl transport\n"
            "/setkategori saham investasi\n"
            "/setkategori skincare belanja"
        )
        return

    keyword = context.args[0].lower()
    kategori = context.args[1].lower()

    learned = db["learned_categories"] or {}
    learned[keyword] = kategori
    db["learned_categories"] = learned

    await update.message.reply_text(
        f"✅ Bot belajar:\n'{keyword}' sekarang masuk kategori '{kategori}'"
    )


async def lihat_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    learned = db["learned_categories"] or {}

    if not learned:
        await update.message.reply_text("Belum ada kategori custom bor.")
        return

    msg = "🧠 Kategori custom yang sudah dipelajari:\n\n"

    for keyword, kategori in learned.items():
        msg += f"- {keyword} → {kategori}\n"

    await update.message.reply_text(msg)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = (db["history"] or [])[-10:]

    if not data:
        await update.message.reply_text("Belum ada transaksi bor.")
        return

    msg = "📜 10 transaksi terakhir:\n\n"

    for item in reversed(data):
        tanda = "+" if item["tipe"] == "IN" else "-"
        msg += (
            f"{item['tanggal']} | {item['user']}\n"
            f"{tanda} {format_rupiah(item['nominal'])} - {item['kategori']}\n"
            f"{item['catatan']}\n\n"
        )

    await update.message.reply_text(msg)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db["history"] or []

    if not data:
        await update.message.reply_text("Belum ada transaksi bor 😭")
        return

    total_in = 0
    total_out = 0
    kategori_out = {}

    for item in data:
        if item["tipe"] == "IN":
            total_in += item["nominal"]
        else:
            total_out += item["nominal"]
            kategori = item["kategori"]
            kategori_out[kategori] = kategori_out.get(kategori, 0) + item["nominal"]

    top_kategori = sorted(kategori_out.items(), key=lambda x: x[1], reverse=True)[:5]

    msg = (
        "📊 Report Keuangan\n\n"
        f"💰 Total Pemasukan: {format_rupiah(total_in)}\n"
        f"💸 Total Pengeluaran: {format_rupiah(total_out)}\n"
        f"💳 Saldo Sekarang: {format_rupiah(db['saldo'] or 0)}\n\n"
        "🔥 Top Pengeluaran:\n"
    )

    if top_kategori:
        for kategori, nominal in top_kategori:
            msg += f"- {kategori}: {format_rupiah(nominal)}\n"
    else:
        msg += "- Belum ada pengeluaran\n"

    await update.message.reply_text(msg)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db["history"] or []
    bulan_ini = datetime.now().strftime("%Y-%m")

    transaksi_bulan_ini = [
        item for item in data
        if item["tanggal"].startswith(bulan_ini)
    ]

    if not transaksi_bulan_ini:
        await update.message.reply_text("Belum ada transaksi bulan ini bor 😭")
        return

    total_in = 0
    total_out = 0
    kategori_out = {}
    transaksi_terbesar = None

    for item in transaksi_bulan_ini:
        if item["tipe"] == "IN":
            total_in += item["nominal"]
        else:
            total_out += item["nominal"]
            kategori = item["kategori"]
            kategori_out[kategori] = kategori_out.get(kategori, 0) + item["nominal"]

            if transaksi_terbesar is None or item["nominal"] > transaksi_terbesar["nominal"]:
                transaksi_terbesar = item

    top_kategori = sorted(kategori_out.items(), key=lambda x: x[1], reverse=True)[:5]

    msg = (
        f"📅 Report Bulan Ini ({bulan_ini})\n\n"
        f"💰 Pemasukan: {format_rupiah(total_in)}\n"
        f"💸 Pengeluaran: {format_rupiah(total_out)}\n"
        f"💳 Saldo Sekarang: {format_rupiah(db['saldo'] or 0)}\n\n"
        "🔥 Top Pengeluaran:\n"
    )

    if top_kategori:
        for kategori, nominal in top_kategori:
            msg += f"- {kategori}: {format_rupiah(nominal)}\n"
    else:
        msg += "- Belum ada pengeluaran\n"

    if transaksi_terbesar:
        msg += (
            "\n📌 Transaksi Terbesar:\n"
            f"{transaksi_terbesar['catatan']} - {format_rupiah(transaksi_terbesar['nominal'])}"
        )

    await update.message.reply_text(msg)


async def catat_otomatis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    nominal = parse_nominal(text)

    if nominal is None:
        await update.message.reply_text(
            "Nominalnya belum kebaca bor 😭\n"
            "Contoh:\n"
            "makan mie ayam 30rb\n"
            "gajian 6 juta"
        )
        return

    tipe = detect_tipe(text)
    kategori = detect_kategori(text)
    user = update.effective_user.first_name or "Unknown"
    tanggal = datetime.now().strftime("%Y-%m-%d %H:%M")

    saldo = db["saldo"] or 0

    if tipe == "IN":
        saldo += nominal
        emoji = "💰"
        label = "Pemasukan"
    else:
        saldo -= nominal
        emoji = "💸"
        label = "Pengeluaran"

    db["saldo"] = saldo

    transaksi = {
        "tanggal": tanggal,
        "user": user,
        "tipe": tipe,
        "kategori": kategori,
        "nominal": nominal,
        "catatan": text,
        "saldo_akhir": saldo
    }

    h = db["history"] or []
    h.append(transaksi)
    db["history"] = h

    await update.message.reply_text(
        f"{emoji} {label} tercatat\n"
        f"User: {user}\n"
        f"Kategori: {kategori}\n"
        f"Catatan: {text}\n"
        f"Nominal: {format_rupiah(nominal)}\n"
        f"Saldo sekarang: {format_rupiah(saldo)}"
    )


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("saldo", cek_saldo))
app.add_handler(CommandHandler("history", history))
app.add_handler(CommandHandler("report", report))
app.add_handler(CommandHandler("monthly", monthly))
app.add_handler(CommandHandler("setkategori", set_kategori))
app.add_handler(CommandHandler("kategori", lihat_kategori))
app.add_handler(CommandHandler("reset", reset_saldo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catat_otomatis))

keep_alive()
print("Bot jalan...")

app.run_polling()