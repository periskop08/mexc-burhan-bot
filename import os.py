import os
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

app = Flask(__name__)

# === ENV değişkenleri ===
API_KEY = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_SECRET_KEY")
API_URL = os.getenv("MEXC_API_URL")

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Sabit işlem değeri ===
SABIT_POZISYON_USDT = 400

# === Telegram log fonksiyonu ===
def log_to_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram log hatası: {e}")

# === MEXC'de market order aç ===
def place_mexc_order(symbol, side, quantity):
    endpoint = "/api/v1/private/order/place"
    url = API_URL + endpoint
    headers = {
        "Content-Type": "application/json",
        "ApiKey": API_KEY
    }

    data = {
        "symbol": symbol,
        "price": "0",  # Market order olduğu için 0
        "vol": str(quantity),
        "side": side.lower(),  # "buy" veya "sell"
        "type": "market",
        "open_type": "isolated",
        "position_id": 0,
        "leverage": 10,
        "external_oid": "order_" + symbol,
        "stop_loss_price": "",
        "take_profit_price": ""
    }

    try:
        res = requests.post(url, headers=headers, json=data)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

# === Webhook endpoint ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        symbol = data["symbol"].split(":")[1]  # MEXC:BTCUSDT → BTCUSDT
        side = data["side"]  # Buy/Sell
        entry = Decimal(str(data["entry"]))
        sl = data.get("sl")
        tp = data.get("tp")

        quantity = round(SABIT_POZISYON_USDT / float(entry), 3)

        log_to_telegram(f"🟡 MEXC sinyali alındı: `{symbol}`\nSide: *{side}*\nEntry: {entry}\nLot: {quantity}")

        result = place_mexc_order(symbol, side, quantity)

        if "error" in result:
            log_to_telegram(f"❌ Emir gönderilemedi: `{result['error']}`")
        else:
            log_to_telegram(f"✅ İşlem açıldı: `{symbol}` {side} {quantity} lot\nYanıt: `{result}`")

        return jsonify({"status": "ok", "result": result})

    except Exception as e:
        log_to_telegram(f"🚨 Hata oluştu:\n{str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)