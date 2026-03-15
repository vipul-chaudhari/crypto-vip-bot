import ccxt
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime
import time

import os

# --- TELEGRAM CONFIGURATION (FROM GITHUB SECRETS) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ----------------------------------------------------

class MegaScannerBot:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Telegram Error: {e}")

    def get_all_usdt_symbols(self):
        try:
            tickers = self.exchange.fetch_tickers()
            usdt_pairs = []
            for symbol, ticker in tickers.items():
                if symbol.endswith('/USDT') and ticker['quoteVolume'] and ticker['quoteVolume'] > 150000:
                    usdt_pairs.append({'symbol': symbol, 'volume': ticker['quoteVolume']})
            sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
            return [p['symbol'] for p in sorted_pairs[:150]]
        except Exception as e:
            print(f"Error fetching symbols: {e}")
            return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

    def fetch_data(self, symbol, timeframe, limit=100):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        except:
            return pd.DataFrame()

    def calculate_levels(self, df, trade_type):
        close = df['close'].iloc[-1]
        atr_series = ta.atr(df['high'], df['low'], df['close'], length=14)
        atr = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty else close * 0.02
        m = {'Intraday': 1.5, 'Short-term': 2.5}[trade_type]
        
        def fmt(val): return round(val, 6) if val < 1 else round(val, 2)
        
        buy = fmt(close)
        sl = fmt(close - (atr * m))
        tp = fmt(close + (atr * (m * 2)))
        
        risk = abs(buy - sl)
        reward = abs(tp - buy)
        rr = round(reward / risk, 1) if risk != 0 else 0
        
        return buy, sl, tp, rr

    def analyze_symbol(self, symbol):
        trades = []
        # 1. INTRADAY SCALP (15M)
        df15 = self.fetch_data(symbol, '15m')
        if not df15.empty:
            rsi_series = ta.rsi(df15['close'], length=14)
            if rsi_series is not None and not rsi_series.empty:
                rsi = rsi_series.iloc[-1]
                if rsi < 33:
                    buy, sl, tp, rr = self.calculate_levels(df15, 'Intraday')
                    strength = "High 🔥" if rsi < 25 else "Medium ⚡"
                    trades.append({
                        "type": "SHORT-TERM SCALP",
                        "buy": buy, "sl": sl, "tp": tp, "rr": rr,
                        "strength": strength,
                        "note": f"Oversold (RSI: {round(rsi,1)})"
                    })

        # 2. SWING TRADE (4H)
        df4h = self.fetch_data(symbol, '4h')
        if not df4h.empty:
            ema9_series = ta.ema(df4h['close'], length=9)
            ema21_series = ta.ema(df4h['close'], length=21)
            if ema9_series is not None and ema21_series is not None and len(ema9_series) > 0:
                ema9 = ema9_series.iloc[-1]
                ema21 = ema21_series.iloc[-1]
                if ema9 > ema21 and df4h['close'].iloc[-1] > ema9:
                    buy, sl, tp, rr = self.calculate_levels(df4h, 'Short-term')
                    trades.append({
                        "type": "POSITION SWING",
                        "buy": buy, "sl": sl, "tp": tp, "rr": rr,
                        "strength": "Solid 📈",
                        "note": "Bullish Trend Confirmed"
                    })
        return trades

    def format_signal(self, symbol, trade):
        coin_name = symbol.replace('/USDT', '')
        return (
            f"🌟 *VIP SIGNAL: {coin_name}* 🌟\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 **STRATEGY:** `{trade['type']}`\n"
            f"📊 **STRENGTH:** `{trade['strength']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 **ENTRY:** `{trade['buy']}`\n"
            f"🎯 **TARGET:** `{trade['tp']}`\n"
            f"🛑 **STOP LOSS:** `{trade['sl']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ **R/R RATIO:** `{trade['rr']}`\n"
            f"💡 **ANALYSIS:** _{trade['note']}_"
        )

    def run_report(self):
        symbols = self.get_all_usdt_symbols()
        print(f"Scanning {len(symbols)} symbols...")
        
        all_signals = []
        for symbol in symbols:
            analysis = self.analyze_symbol(symbol)
            for trade in analysis:
                all_signals.append(self.format_signal(symbol, trade))
            time.sleep(0.05)

        if all_signals:
            header = (
                f"🔥 **CRYPTO GURU VIP REPORT** 🔥\n"
                f"📅 _{datetime.now().strftime('%Y-%m-%d | %H:%M')}_\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Scanned {len(symbols)} Assets\n"
                f"✅ Found {len(all_signals)} High-Probability Setups"
            )
            self.send_telegram(header)
            
            for signal in all_signals:
                self.send_telegram(signal)
                time.sleep(1)
        else:
            self.send_telegram("🔍 *SCAN COMPLETE*\n_No high-conviction signals found at this hour. Waiting for next window._")

if __name__ == "__main__":
    bot = MegaScannerBot()
    bot.run_report() # Run once and exit (for GitHub Actions)
