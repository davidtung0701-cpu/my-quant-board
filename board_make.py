import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import os
import sys
import io

# ==========================================
# 1. 戰略監控目標 (維持全域監控，但僅輸出核心變數)
# ==========================================
TICKERS = {
    "PLTR (Palantir)": "PLTR",
    "NVDA (輝達-算力核心)": "NVDA",      
    "SOX (費半ETF)": "SOXX",
    "QQQ (納斯達克100)": "QQQ",
    "MU (美光-記憶體先導)": "MU",
    "HYG (垃圾債-流動性)": "HYG",
    "009816.TW (凱基TOP50)": "009816.TW",
    "00757.TW (統一 FANG+)": "00757.TW",   
    "VIX (恐慌指數)": "^VIX",
    "TNX (10年美債)": "^TNX"
}

# ==========================================
# 2. 量化運算與戰略狀態判定
# ==========================================
def get_daily_market_data():
    results = []
    for name, ticker in TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if hist.empty:
                raise ValueError("無資料")
            
            hist_close = hist['Close'].ffill() 
            latest_price = hist_close.iloc[-1]
            
            ma5 = hist_close.rolling(window=5).mean().iloc[-1]
            std5 = hist_close.rolling(window=5).std().iloc[-1]
            ma60 = hist_close.rolling(window=60).mean().iloc[-1]
            
            if "009816" in ticker and pd.isna(ma60):
                ma60 = 10.35

            volatility_5 = (std5 / ma5) * 100 if pd.notna(std5) and pd.notna(ma5) and ma5 != 0 else 0
            bias_60 = ((latest_price - ma60) / ma60) * 100 if pd.notna(ma60) and ma60 != 0 else 0
            
            status = "[ 觀測中 ]"
            if bias_60 > 20:
                status = "[!!! 過衝警報 !!!]"
            elif bias_60 > 10:
                status = "[ 高位警戒 ]"
            elif bias_60 < -10:
                status = "[ 深度回撤 ]"
            elif bias_60 < -5:
                status = "[ 底部尋求 ]"
            
            if name.startswith("PLTR") and bias_60 < -10:
                status = "[ 滿足狙擊乖離 ]"
            elif "009816" in name and bias_60 < 0:
                status = "[ 獵殺啟動授權 ]" 
            elif "VIX" in name:
                if bias_60 > 20:
                    status = "[$$ 恐慌收割 $$]"
                elif bias_60 < -15:
                    status = "[ 暴風雨前夕 ]"
            elif "HYG" in name:
                if std5 > 1.5 and bias_60 < -3:
                    status = "[!!! 流動性枯竭 !!!]"

            results.append({
                "指標名稱": name,
                "最新報價": f"{latest_price:.2f}" if pd.notna(latest_price) else "-",
                "季線乖離率(%)": f"{bias_60:.2f}",
                "戰略狀態": status
            })
            
        except Exception as e:
            results.append({
                "指標名稱": name, 
                "最新報價": "Error", 
                "季線乖離率(%)": "-",
                "戰略狀態": "Data Error"
            })
            
    return pd.DataFrame(results)

# ==========================================
# 3. 輸出與格式化 (無縫對接 Telegram 極簡版)
# ==========================================
def main():
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        df_market = get_daily_market_data()
        
        def get_val(df, kw, col):
            try:
                return float(df[df['指標名稱'].str.contains(kw)][col].values[0])
            except:
                return 0.0

        vix_price = get_val(df_market, "VIX", '最新報價')
        tnx_price = get_val(df_market, "TNX", '最新報價')
        hyg_price = get_val(df_market, "HYG", '最新報價')
        sox_bias  = get_val(df_market, "SOX", '季線乖離率(%)')
        mu_bias   = get_val(df_market, "MU", '季線乖離率(%)')
        nvda_bias = get_val(df_market, "NVDA", '季線乖離率(%)')
        pltr_bias = get_val(df_market, "PLTR", '季線乖離率(%)')
        fang_bias = get_val(df_market, "00757", '季線乖離率(%)')
        kgi_bias  = get_val(df_market, "009816", '季線乖離率(%)')
        
        pltr_status = df_market[df_market['指標名稱'].str.contains("PLTR")]['戰略狀態'].values[0] if not df_market[df_market['指標名稱'].str.contains("PLTR")].empty else ""
        
        is_hunting = (kgi_bias < 0) or ("[ 滿足狙擊乖離 ]" in pltr_status) or (fang_bias < -15 and vix_price > 30)
        
        # 標題與阻尼
        if is_hunting:
            print(f"🚨 【戰術重擊授權】{today_str}")
        else:
            print(f"📊 【量化巡航日報】{today_str}")
            
        print(f"⚖️ 阻尼：VIX {vix_price:.2f} | TNX {tnx_price:.2f}% | HYG {hyg_price:.2f}")
        print("-" * 27)

        # 核心戰備狀態映射表
        print("【核心戰備狀態】")
        label_map = {
            "NVDA": "NVDA (算力)",
            "MU": "MU   (記憶)",
            "PLTR": "PLTR (防禦)",
            "00757": "00757(跨海)",
            "009816": "009816(台股)"
        }
        
        for key, label in label_map.items():
            try:
                row = df_market[df_market['指標名稱'].str.contains(key)].iloc[0]
                # 排版對齊
                print(f"• {label}: {row['最新報價']} | 乖離 {row['季線乖離率(%)']}%")
            except:
                pass
                
        print("-" * 27)

        # 系統動態警報
        print("【系統動態警報】")
        alert_triggered = False

        if sox_bias > 20.0 or mu_bias > 25.0:
            print("🔴 [上游鎖死] 美光乖離仍處極端，大盤隨時拖拽。")
            alert_triggered = True
            
        if nvda_bias > 25.0 and pltr_bias > 15.0:
            print("⚠️ [算力超載] NVDA與PLTR雙飆，嚴禁追價。")
            alert_triggered = True
            
        if tnx_price > 4.60 or (df_market[df_market['指標名稱'].str.contains("HYG")]['戰略狀態'].values[0] == "[!!! 流動性枯竭 !!!]"):
            print("⚠️ [流動性警告] 資金成本跨越紅線，嚴防高估值下殺。")
            alert_triggered = True

        if not alert_triggered:
            print("⚪ 狀態中性，無極端引力干涉。")

        print("-" * 27)
        
        # 戰術判決 (金額隱去，純輸出手令)
        if is_hunting:
            print("🔥 [戰術判決]：引信已觸發！核對硬性紀律：")
            if kgi_bias < 0:
                print("  -> 009816 破線，【戰略現金池】授權解鎖第一階段。")
            if fang_bias < -15 and vix_price > 30:
                print("  -> 00757 末日條件達成，授權實體核武重擊。")
            if "[ 滿足狙擊乖離 ]" in pltr_status:
                print(f"  -> PLTR 滿足狙擊，VIX 是否 > 25？(當前 {vix_price:.2f})")
        else:
            print("⚪ [戰術判決]：安全巡航。")
            print("戰略現金池鎖死。維持 12、18、26、28 日履帶推進。")

    finally:
        final_output_text = buffer.getvalue()
        sys.stdout = old_stdout
        print(final_output_text)

    # 發送端 
    WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
    
    if not WEBHOOK_URL:
        print("⚠️ 測試模式：未偵測到 WEBHOOK_URL。")
        return

    try:
        payload = {"text": final_output_text}
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code == 200:
            print("🚀 成功發送至 Make.com")
        else:
            print(f"❌ 發送失敗，錯誤碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 通訊異常：{str(e)}")

if __name__ == "__main__":
    main()
