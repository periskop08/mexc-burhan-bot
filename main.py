# main_mexc.py – MEXC uyumlu Burhan-Bot (config.py destekli)

import json
import traceback
import requests
from flask import Flask, request, jsonify
import decimal
import time
import threading
from queue import Queue

from config import MEXC_API_KEY, MEXC_SECRET_KEY, MEXC_API_URL
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

app = Flask(__name__)

# === Telegram Ayarları ===
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# === Telegram mesaj kuyruğu ===
telegram_message_queue = Queue()
LAST_TELEGRAM_MESSAGE_TIME = 0
TELEGRAM_RATE_LIMIT_DELAY = 1.0

def telegram_message_sender():
    global LAST_TELEGRAM_MESSAGE_TIME
    while True:
        if not telegram_message_queue.empty():
            current_time = time.time()
            time_since_last_message = current_time - LAST_TELEGRAM_MESSAGE_TIME
            if time_since_last_message >= TELEGRAM_RATE_LIMIT_DELAY:
                message_text = telegram_message_queue.get()
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message_text,
                    "parse_mode": "HTML"
                }
                try:
                    requests.post(TELEGRAM_URL, json=payload)
                    LAST_TELEGRAM_MESSAGE_TIME = time.time()
                except Exception as e:
                    print(f"Telegram hatası: {e}")
                telegram_message_queue.task_done()
            else:
                time.sleep(TELEGRAM_RATE_LIMIT_DELAY - time_since_last_message)
        else:
            time.sleep(0.1)

telegram_thread = threading.Thread(target=telegram_message_sender, daemon=True)
telegram_thread.start()

def send_telegram_message_to_queue(message_text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_message_queue.put(message_text)

# === Yuvarlama Fonksiyonları ===
def round_to_precision(value, precision_step):
    if value is None or precision_step <= 0:
        return float(value)
    return float(decimal.Decimal(str(value)).quantize(decimal.Decimal(str(precision_step)), rounding=decimal.ROUND_HALF_UP))

def round_quantity(value):
    return str(round(float(value), 3))  # MEXC çoğu parite için 3 ondalık hassasiyet yeterlidir

# === Webhook ===
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        symbol = data["symbol"].split(":")[-1].replace(".P", "").upper()
        side = data["side"].lower()
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])

        qty = round(40.0 / entry, 3)  # 40 USDT sabit pozisyon değeri
        send_telegram_message_to_queue(f"📩 MEXC sinyali alındı: {symbol}, {side.upper()}, Entry: {entry}, SL: {sl}, TP: {tp}, Qty: {qty}")

        response = place_mexc_order(symbol, side, qty)
        if response.get("code") == 0:
            send_telegram_message_to_queue(f"✅ MEXC işlemi başarıyla açıldı: {response}")
            return jsonify({"status": "ok", "mexc_response": response})
        else:
            send_telegram_message_to_queue(f"❌ MEXC işlem hatası: {response}")
            return jsonify({"status": "error", "mexc_response": response}), 500

    except Exception as e:
        tb = traceback.format_exc()
        send_telegram_message_to_queue(f"🚨 HATA: {e}\n<pre>{tb}</pre>")
        return jsonify({"status": "error", "message": str(e)}), 500

# === MEXC Market Order Gönderimi ===
def place_mexc_order(symbol, side, quantity):
    url = f"{MEXC_API_URL}/api/v1/private/order/place"
    headers = {
        "Content-Type": "application/json",
        "ApiKey": MEXC_API_KEY
    }
    data = {
        "symbol": symbol,
        "price": "0",
        "vol": str(quantity),
        "side": side,
        "type": "market",
        "open_type": "isolated",
        "position_id": 0,
        "leverage": 10,
        "external_oid": f"order_{symbol}_{int(time.time())}",
        "stop_loss_price": "",
        "take_profit_price": ""
    }
    try:
        res = requests.post(url, headers=headers, json=data)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

@app.route("/", methods=["GET"])
def home():
    return "MEXC-BurhanBot aktif 💹"

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))