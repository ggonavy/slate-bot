# SlateBot_XRP_Sniper.py
# XRP sniper bot — ride retail hype, dump the bags, convert to BTC later

import time
import math
import os
import json
from datetime import datetime
from binance.client import Client
from binance.enums import *

# === CONFIGURATION ===
CHECK_INTERVAL = 15  # seconds
PAIR = 'XRPUSDT'
DECIMALS = 1  # XRP typically uses 1 decimal
TRADE_FEE_PCT = 0.001  # 0.1% Binance fee

# === Ladder Config ===
BUY_LADDER = [
    {"drop_pct": 2.5, "amount_pct": 0.25, "sell_trigger_pct": 2.5},
    {"drop_pct": 3.5, "amount_pct": 0.35, "sell_trigger_pct": 3.5},
    {"drop_pct": 4.5, "amount_pct": 0.40, "sell_trigger_pct": 4.5},
]

# === Environment Vars ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# === State ===
high_price = 0.0
buys = []
INITIAL_FIAT = 25000.0
available_fiat = INITIAL_FIAT
LOG_FILE = "xrp_sniper_log.json"

# === Load existing log ===
def load_log():
    global high_price, buys, available_fiat
    try:
        with open(LOG_FILE, 'r') as f:
            state = json.load(f)
            high_price = state.get("high_price", 0.0)
            buys.extend(state.get("buys", []))
            available_fiat = state.get("available_fiat", INITIAL_FIAT)
    except FileNotFoundError:
        pass

# === Save log ===
def save_log():
    with open(LOG_FILE, 'w') as f:
        json.dump({
            "high_price": high_price,
            "buys": buys,
            "available_fiat": available_fiat
        }, f, indent=2)

# === Get current XRP price ===
def get_price():
    ticker = client.get_symbol_ticker(symbol=PAIR)
    return float(ticker['price'])

# === Execute market buy ===
def execute_buy(usdt_amount):
    price = get_price()
    qty = round((usdt_amount * (1 - TRADE_FEE_PCT)) / price, DECIMALS)
    # client.order_market_buy(symbol=PAIR, quantity=qty)  # Uncomment to go live
    return price, qty

# === Execute market sell ===
def execute_sell(xrp_amount):
    price = get_price()
    qty = round(xrp_amount * (1 - TRADE_FEE_PCT), DECIMALS)
    # client.order_market_sell(symbol=PAIR, quantity=qty)  # Uncomment to go live
    return price, qty

# === Main Loop ===
load_log()
print("SlateBot_XRP_Sniper is active.\n")

while True:
    try:
        price = get_price()

        # Update dynamic high
        if not buys or price > high_price:
            high_price = price

        # Buy Logic
        for i, ladder in enumerate(BUY_LADDER):
            target = high_price * (1 - ladder['drop_pct'] / 100)
            already_bought = any(b['level'] == i for b in buys)
            if price <= target and not already_bought:
                fiat_to_use = INITIAL_FIAT * ladder['amount_pct']
                if available_fiat >= fiat_to_use:
                    buy_price, qty = execute_buy(fiat_to_use)
                    buys.append({
                        "level": i,
                        "buy_price": buy_price,
                        "xrp": qty,
                        "sell_price": high_price * (1 + ladder['sell_trigger_pct'] / 100),
                        "timestamp": str(datetime.utcnow())
                    })
                    available_fiat -= fiat_to_use
                    print(f"[BUY] Level {i} - {qty} XRP at ${buy_price:.4f}")

        # Sell Logic
        for b in buys[:]:
            if price >= b['sell_price']:
                sell_price, sold_qty = execute_sell(b['xrp'])
                profit = (sell_price - b['buy_price']) * b['xrp'] * (1 - TRADE_FEE_PCT)
                available_fiat += sold_qty * sell_price
                print(f"[SELL] Sold {sold_qty} XRP at ${sell_price:.4f}, Profit: ${profit:.2f}")
                buys.remove(b)

        # Reset Cycle
        if not buys:
            print("[CYCLE RESET] All XRP sold. Resetting high.")
            high_price = price
            available_fiat = INITIAL_FIAT

        save_log()
        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("[ERROR]", e)
        time.sleep(5)
