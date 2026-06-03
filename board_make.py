import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import unicodedata
import os  # 新增：用於讀取環境變數
import sys
import io

# ==========================================
# 0. 排版工具函數 (後台處理用，不影響 Telegram 輸出)
# ==========================================
def display_width(text):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in str(text))

def pad_string(text, width, align='left'):
    text = str(text)
    w = display_width(text)
    padding = width - w
    if padding < 0: 
        padding = 0
    if align == 'left':
        return text + ' ' * padding
    elif align == 'right':
        return ' ' * padding + text
    else:
        return ' ' * (padding // 2) + text + ' ' * (padding - padding // 2)

# ==========================================
# 1. 戰略監控目標 (已同步 board.py 最新標的)
# ==========================================
TICKERS = {
    "PLTR (Palantir)": "PLTR",
    "NVDA (輝達-算力核心)": "NVDA",      # 新增
    "SOX (費半ETF)": "SOXX",
    "QQQ (納斯達克100)": "QQQ",
    "WTI原油期貨": "CL=F",
    "MU (美光-記憶體先導)": "MU",
    "HYG (垃圾債-流動性)": "HYG",
    "009816.TW (凱基TOP50)": "009816.TW",
    "006208.TW (富邦台50)": "006208.TW",
    "0050.TW (元大台50)": "0050.TW",       # 新增
    "00757.TW (統一 FANG+)": "00757.TW",   # 新增
    "2454.TW (聯發科)": "2454.TW",
    "2330.TW (台積電)": "2330.TW",
    "TSM (台積電ADR)": "TSM",
    "VIX (恐慌指數)": "^VIX",
    "TNX (10年美債)": "^TNX",
    "TWD=X (美元兌台幣)": "TWD=X"
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
            
            # --- 009816 特殊處理 ---
            if "009816" in ticker and pd.isna(ma60):
                ma60 = 10.35

            volatility_5 = (std5 / ma5) * 100 if pd.notna(std5) and pd.notna(ma5) and ma5 != 0 else 0
            bias_60 = ((latest_price - ma60) / ma60) * 100 if pd.notna(ma60) and ma60 != 0 else 0
            
            # --- 通用防守位階 ---
            status = "[ 觀測中 ]"
            if bias_60 > 20:
                status = "[!!! 過衝警報 !!!]"
            elif bias_60 > 10:
                status = "[ 高位警戒 ]"
            elif bias_60 < -10:
                status = "[ 深度回撤 ]"
            elif bias_60 < -5:
                status = "[ 底部尋求 ]"
            
            # --- 標的專屬覆蓋判定 ---
            if name.startswith("PLTR"):
                if bias_60 < -10:
                    status = "[ 滿足狙擊乖離 ]"
            elif "009816" in name:
                if bias_60 < 0:
                    status = "[ 獵殺啟動授權 ]" # 隱去金額，純發送信號
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
                "5日標準差(%)": f"{volatility_5:.2f}",
                "季線乖離率(%)": f"{bias_60:.2f}",
                "戰略狀態": status
            })
            
        except Exception as e:
            results.append({
                "指標名稱": name, 
                "最新報價": "Error", 
                "5日標準差(%)": "-", 
                "季線乖離率(%)": "-",
                "戰略狀態": "Data Error"
            })
            
    return pd.DataFrame(results)

# ==========================================
# 3. 輸出與格式化 (整合最新邏輯的 Telegram 極簡版)
# ==========================================
def main():
    # --- 1. 物理攔截器啟動 ---
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        df_market = get_daily_market_data()
        
        # 提取核心判斷變數
        def get_val(df, kw, col):
            try:
                return float(df[df['指標名稱'].str.contains(kw)][col].values[0])
            except:
                return 0.0

        vix_price = get_val(df_market, "VIX", '最新報價')
        wti_price = get_val(df_market, "WTI", '最新報價')
        tnx_price = get_val(df_market, "TNX", '最新報價')
        sox_bias  = get_val(df_market, "SOX", '季線乖離率(%)')
        mu_bias   = get_val(df_market, "MU", '季線乖離率(%)')
        nvda_bias = get_val(df_market, "NVDA", '季線乖離率(%)')
        pltr_bias = get_val(df_market, "PLTR", '季線乖離率(%)')
        fang_bias = get_val(df_market, "00757", '季線乖離率(%)')
        kgi_bias  = get_val(df_market, "009816", '季線乖離率(%)')
        
        pltr_status = df_market[df_market['指標名稱'].str.contains("PLTR")]['戰略狀態'].values[0] if not df_market[df_market['指標名稱'].str.contains("PLTR")].empty else ""
        
        # 判定全域狀態 (新增 00757 條件)
        is_hunting = (kgi_bias < 0) or ("[ 滿足狙擊乖離 ]" in pltr_status) or (fang_bias < -15 and vix_price > 30)
        
        # --- 建立極簡手機排版文本 ---
        if is_hunting:
            print(f"🚨 【戰術重擊授權核心】")
        else:
            print(f"📊 【量化巡航日報】")
            
        print(f"時間：{today_str}")
        print(f"宏觀阻尼：WTI {wti_price:.1f} | VIX {vix_price:.2f} | 10Y美債 {tnx_price:.2f}%")
        print("-" * 35)

        # 輸出核心資產
        print("【核心戰備狀態】")
        for _, row in df_market.iterrows():
            name = row['指標名稱'].split(" ")[0]
            price = row['最新報價']
            bias = row['季線乖離率(%)']
            status = row['戰略狀態']
            
            # 挑選關鍵標的顯示於 Telegram
            if name in ["009816.TW", "00757.TW", "PLTR", "NVDA", "2330.TW"]:
                print(f"• {name.replace('.TW', '')}：{price} | 乖離 {bias}% \n  {status}")
                
        print("-" * 35)

        # 跨市場引力與系統自動警報 (精簡化)
        print("【系統動態警報】")
        alert_triggered = False

        if sox_bias > 20.0 or mu_bias > 25.0:
            print("🔴 [上游鎖死] 費半/美光乖離膨脹，承受向下拖拽重力。")
            alert_triggered = True
        elif (sox_bias < -5.0 or mu_bias < -8.0) and vix_price < 24.0:
            print("🟢 [先行洗盤] 美股上游修正至低位。若台股破線即為利空出盡。")
            alert_triggered = True
            
        if nvda_bias > 25.0 and pltr_bias > 15.0:
            print("⚠️ [算力超載] NVDA與PLTR雙飆，00757嚴禁追價。")
            alert_triggered = True
            
        if tnx_price > 4.60:
            print("⚠️ [流動性警告] 10年美債突破4.6%，嚴防高估值下殺。")
            alert_triggered = True

        if not alert_triggered:
            print("⚪ 狀態中性，無極端引力干涉。")

        print("-" * 35)
        
        # 自動化極簡決策導航
        if is_hunting:
            print("🔥 [戰術判決]：引信已觸發！核對硬性紀律：")
            if kgi_bias < 0:
                print(f"  1. 009816 破季線 -> 【核心預備金】解鎖。")
            if fang_bias < -15 and vix_price > 30:
                print(f"  2. 00757 末日條件達成 -> 授權極端重擊。")
            if "[ 滿足狙擊乖離 ]" in pltr_status:
                print(f"  3. PLTR 滿足狙擊 -> VIX 是否 > 25？(當前 {vix_price})")
        else:
            print("⚪ [戰術判決]：安全巡航。")
            print("  【戰略現金池】絕對鎖死。")
            print("  維持日常雙週引擎定時扣款。")

    finally:
        # --- 2. 還原標準控制台輸出並截取純文字 ---
        final_output_text = buffer.getvalue()
        sys.stdout = old_stdout
        print(final_output_text)

    # --- 3. 實體發送端 (無縫對接 Make 雲端管線) ---
    WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
    
    if not WEBHOOK_URL:
        print("⚠️ 本地端防護機制：未偵測到環境變數 MAKE_WEBHOOK_URL，取消發送。請確保已設定環境變數。")
        return

    try:
        payload = {"text": final_output_text}
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code == 200:
            print("🚀 成功：極簡手機版報表已同步發送至 Make。")
        else:
            print(f"❌ 失敗：錯誤碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 通訊層異常：{str(e)}")

if __name__ == "__main__":
    main()
