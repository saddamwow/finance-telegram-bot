from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from threading import Thread
from flask import Flask
import os
import re
import json

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

# =========================
# LOCAL JSON DATABASE
# =========================

DB_FILE = "database.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "saldo": 0,
            "history": [],
            "learned_categories": {},
            "budget": {}
        }

    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "saldo": 0,
            "history": [],
            "learned_categories": {},
            "budget": {}
        }


def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f)


db = load_db()

# =========================
# HELPER
# =========================

def format_rupiah(n):
    return f"Rp{n:,}".replace(",", ".")


def parse_nominal(text):
    try:
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

    except:
        return None


def detect_tipe(text):
    text = text.lower()

    income_words = [
        "gaji", "gajian", "salary", "bonus", "thr",
        "cashback", "refund", "dibayar", "bayaran",
        "masuk", "transfer masuk", "dapat", "dapet",
        "terima", "saldo awal"
    ]

    if any(word in text for word in income_words):
        return "IN"

    return "OUT"


def detect_kategori(text):
    text = text.lower()

    learned = db.get("learned_categories", {})

    for keyword, kategori in learned.items():
        if keyword.lower() in text:
            return kategori

    kategori_map = {
        "makan": [
            "makan", "mie", "ayam", "nasi", "bakso",
            "ramen", "seblak", "warteg", "resto"
        ],

        "minum": [
            "kopi", "matcha", "teh", "boba",
            "starbucks", "mixue", "janji jiwa"
        ],

        "transport": [
            "bensin", "grab", "gojek", "ojol",
            "parkir", "tol", "kereta", "krl",
            "lrt", "bus"
        ],

        "belanja": [
            "shopee", "tokopedia", "lazada",
            "tiktok shop", "skincare", "belanja"
        ],

        "investasi": [
            "saham", "reksadana", "bibit",
            "stock", "bbca", "bmri", "antm"
        ],

        "hiburan": [
            "spotify", "netflix", "bioskop",
            "game", "steam"
        ],

        "rumah": [
            "wifi", "internet", "listrik",
            "air", "ipl", "kontrakan"
        ],

        "kesehatan": [
            "dokter", "obat", "apotek",
            "vitamin", "klinik"
        ],

        "income": [
            "gaji", "bonus", "thr",
            "refund", "cashback"
        ]
    }

    for kategori, keywords in kategori_map.items():
        if any(word in text for word in keywords):
            return kategori

    return "lainnya"

# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Finance aktif\n\n"
        "Contoh:\n"
        "makan mie ayam 30rb\n"
        "bensin 25rb\n"
        "gajian 6 juta\n\n"
        "Command:\n"
        "/saldo\n"
        "/history\n"
        "/report\n"
        "/monthly\n"
        "/setkategori keyword kategori\n"
        "/kategori\n"
        "/budget kategori nominal\n"
        "/reset"
    )


async def cek_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo = db.get("saldo", 0)

    await update.message.reply_text(
        f"💳 Saldo sekarang:\n{format_rupiah(saldo)}"
    )


async def reset_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["saldo"] = 0
    db["history"] = []

    save_db()

    await update.message.reply_text(
        "🔄 Saldo & history berhasil direset.\n"
        "Kategori custom tetap aman 😭"
    )


async def set_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Format:\n"
            "/setkategori saham investasi"
        )
        return

    keyword = context.args[0].lower()
    kategori = context.args[1].lower()

    learned = db.get("learned_categories", {})
    learned[keyword] = kategori

    db["learned_categories"] = learned

    save_db()

    await update.message.reply_text(
        f"✅ '{keyword}' sekarang masuk kategori '{kategori}'"
    )


async def lihat_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    learned = db.get("learned_categories", {})

    if not learned:
        await update.message.reply_text("Belum ada kategori custom.")
        return

    msg = "🧠 Kategori custom:\n\n"

    for keyword, kategori in learned.items():
        msg += f"- {keyword} → {kategori}\n"

    await update.message.reply_text(msg)


async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Format:\n"
            "/budget makan 1000000"
        )
        return

    kategori = context.args[0].lower()

    try:
        nominal = int(context.args[1])
    except:
        await update.message.reply_text("Nominal budget invalid 😭")
        return

    budget = db.get("budget", {})
    budget[kategori] = nominal

    db["budget"] = budget

    save_db()

    await update.message.reply_text(
        f"🎯 Budget kategori '{kategori}' diset:\n"
        f"{format_rupiah(nominal)}"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db.get("history", [])[-10:]

    if not data:
        await update.message.reply_text("Belum ada transaksi.")
        return

    msg = "📜 10 transaksi terakhir:\n\n"

    for item in reversed(data):
        tanda = "+" if item["tipe"] == "IN" else "-"

        msg += (
            f"{item['tanggal']}\n"
            f"{tanda} {format_rupiah(item['nominal'])}\n"
            f"{item['kategori']} • {item['catatan']}\n\n"
        )

    await update.message.reply_text(msg)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db.get("history", [])

    if not data:
        await update.message.reply_text("Belum ada transaksi 😭")
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

            kategori_out[kategori] = (
                kategori_out.get(kategori, 0)
                + item["nominal"]
            )

    top_kategori = sorted(
        kategori_out.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    msg = (
        "📊 REPORT KEUANGAN\n\n"
        f"💰 Pemasukan : {format_rupiah(total_in)}\n"
        f"💸 Pengeluaran : {format_rupiah(total_out)}\n"
        f"💳 Saldo : {format_rupiah(db.get('saldo', 0))}\n\n"
        "🔥 Top Pengeluaran:\n"
    )

    for kategori, nominal in top_kategori:
        msg += f"- {kategori}: {format_rupiah(nominal)}\n"

    await update.message.reply_text(msg)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db.get("history", [])

    bulan_ini = datetime.now().strftime("%Y-%m")

    transaksi = [
        x for x in data
        if x["tanggal"].startswith(bulan_ini)
    ]

    if not transaksi:
        await update.message.reply_text(
            "Belum ada transaksi bulan ini 😭"
        )
        return

    total_in = 0
    total_out = 0
    kategori_out = {}

    for item in transaksi:
        if item["tipe"] == "IN":
            total_in += item["nominal"]

        else:
            total_out += item["nominal"]

            kategori = item["kategori"]

            kategori_out[kategori] = (
                kategori_out.get(kategori, 0)
                + item["nominal"]
            )

    top_kategori = sorted(
        kategori_out.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    msg = (
        f"📅 MONTHLY REPORT ({bulan_ini})\n\n"
        f"💰 Income : {format_rupiah(total_in)}\n"
        f"💸 Expense : {format_rupiah(total_out)}\n"
        f"💳 Saldo : {format_rupiah(db.get('saldo', 0))}\n\n"
        "🔥 Top Category:\n"
    )

    for kategori, nominal in top_kategori:
        msg += f"- {kategori}: {format_rupiah(nominal)}\n"

    await update.message.reply_text(msg)

# =========================
# AUTO TRANSACTION
# =========================

async def catat_otomatis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text

        nominal = parse_nominal(text)

        if nominal is None:
            await update.message.reply_text(
                "Nominal belum kebaca 😭"
            )
            return

        tipe = detect_tipe(text)
        kategori = detect_kategori(text)

        user = (
            update.effective_user.first_name
            or "Unknown"
        )

        tanggal = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

        saldo = db.get("saldo", 0)

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

        history = db.get("history", [])
        history.append(transaksi)

        db["history"] = history

        save_db()

        msg = (
            f"{emoji} {label} tercatat\n\n"
            f"Kategori: {kategori}\n"
            f"Catatan: {text}\n"
            f"Nominal: {format_rupiah(nominal)}\n"
            f"Saldo: {format_rupiah(saldo)}"
        )

        # =========================
        # BUDGET WARNING
        # =========================

        budget = db.get("budget", {})

        if kategori in budget:
            limit = budget[kategori]

            total_kategori = 0

            bulan_ini = datetime.now().strftime("%Y-%m")

            for item in history:
                if (
                    item["kategori"] == kategori
                    and item["tipe"] == "OUT"
                    and item["tanggal"].startswith(bulan_ini)
                ):
                    total_kategori += item["nominal"]

            persen = int((total_kategori / limit) * 100)

            if persen >= 80:
                msg += (
                    f"\n\n⚠️ Budget {kategori} "
                    f"sudah {persen}%"
                )

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error:\n{str(e)}"
        )

# =========================
# RUN BOT
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("saldo", cek_saldo))
app.add_handler(CommandHandler("history", history))
app.add_handler(CommandHandler("report", report))
app.add_handler(CommandHandler("monthly", monthly))
app.add_handler(CommandHandler("setkategori", set_kategori))
app.add_handler(CommandHandler("kategori", lihat_kategori))
app.add_handler(CommandHandler("budget", set_budget))
app.add_handler(CommandHandler("reset", reset_saldo))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        catat_otomatis
    )
)

keep_alive()

print("Bot jalan 😭🔥")

app.run_polling()
