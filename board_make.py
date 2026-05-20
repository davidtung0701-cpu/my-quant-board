import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import unicodedata

# ==========================================
# 0. 排版工具函數
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

def print_aligned_table(df, col_widths, aligns):
    cols = list(df.columns)
    header = "| " + " | ".join(pad_string(c, w, a) for c, w, a in zip(cols, col_widths, aligns)) + " |"
    print(header)
    separator = "|" + "-" * (sum(col_widths) + len(col_widths) * 3 - 1) + "|"
    print(separator)
    for _, row in df.iterrows():
        row_str = "| " + " | ".join(pad_string(row[c], w, a) for c, w, a in zip(cols, col_widths, aligns)) + " |"
        print(row_str)

# ==========================================
# 1. 戰略監控目標 (擴增美股先導與流動性觀測)
# ==========================================
TICKERS = {
    "PLTR (Palantir)": "PLTR",
    "SOX (費半ETF)": "SOXX",
    "QQQ (納斯達克100)": "QQQ",
    "WTI原油期貨": "CL=F",
    "MU (美光-記憶體先導)": "MU",        # 跨市場引力源：記憶體超級週期中樞
    "HYG (垃圾債-流動性)": "HYG",        # 黑天鵝防禦：系統性流動性枯竭偵測
    "009816.TW (凱基TOP50)": "009816.TW",  # 新核心動能引擎
    "006208.TW (富邦台50)": "006208.TW",  # 廣譜防禦對照組
    "2454.TW (聯發科)": "2454.TW",      # 動能核心觀測
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
    print("正在抓取每日市場數據與計算乖離矩陣...")
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
            
            # --- 009816 特殊處理：若上市未滿60日，以 10.35 基準價作為代理季線 ---
            if "009816" in ticker and pd.isna(ma60):
                ma60 = 10.35

            volatility_5 = (std5 / ma5) * 100 if pd.notna(std5) and pd.notna(ma5) and ma5 != 0 else 0
            bias_60 = ((latest_price - ma60) / ma60) * 100 if pd.notna(ma60) and ma60 != 0 else 0
            
            # --- 戰略狀態自動判定邏輯 (通用防守位階) ---
            status = "[ 觀測中 ]"
            if bias_60 > 20:
                status = "[!!! 過衝警報 !!!]"
            elif bias_60 > 10:
                status = "[ 高位警戒 ]"
            elif bias_60 < -10:
                status = "[ 深度回撤 ]"
            elif bias_60 < -5:
                status = "[ 底部尋求 ]"
            
            # --- 標的專屬覆蓋判定：消弭心理幻覺，強行鎖定操作鐵律 ---
            if name.startswith("PLTR"):
                # 僅提示乖離達標，防範 VIX 未達標時的衝動扣動扳機
                if bias_60 < -10:
                    status = "[ 滿足狙擊乖離 ]" # 仍需系統共振確認 VIX > 25
            elif "009816" in name:
                if bias_60 < 0:
                    status = "[ 獵殺啟動授權 ]" # 解鎖實體 24.3 萬現金池的唯一信號
            elif "VIX" in name:
                if bias_60 > 20:
                    status = "[$$ 恐慌收割 $$]"
                elif bias_60 < -15:
                    status = "[ 暴風雨前夕 ]"
            elif "HYG" in name:
                # 若高收益債單日標準差暴增且跌破季線，觸發全域黑天鵝警報
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
# 3. 獲取情緒指標 (修復與擴增)
# ==========================================
def get_sentiment_indicators():
    headers = {'User-Agent': 'Mozilla/5.0'}
    sentiments = []
    print("正在掃描市場情緒指標...")
    
    # AAII
    try:
        res = requests.get("https://www.aaii.com/sentiment-survey", headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            bullish = soup.find(string=lambda text: "Bullish" in text if text else False)
            sentiments.append({"指標": "AAII 牛熊狀態", "數值/狀態": "需至 AAII 官網確認" if not bullish else "已更新"})
        else:
            sentiments.append({"指標": "AAII 牛熊狀態", "數值/狀態": "爬蟲受限，需手動確認"})
    except:
        sentiments.append({"指標": "AAII 牛熊狀態", "數值/狀態": "連線異常"})

    # NAAIM & BofA
    sentiments.append({"指標": "NAAIM 持倉指數", "數值/狀態": "需至 naaim.org 確認最新數值"})
    sentiments.append({"指標": "BofA Bull & Bear", "數值/狀態": "建議透過財經新聞手動確認"})

    return pd.DataFrame(sentiments)

# ==========================================
# 4. 輸出與格式化 (手機 Telegram 極簡高信噪比版本)
# ==========================================
def main():
    import sys
    import io
    import requests

    # --- 1. 物理攔截器啟動 ---
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        df_market = get_daily_market_data()
        
        # 提取核心判斷變數
        pltr_status = df_market[df_market['指標名稱'].str.contains("PLTR")]['戰略狀態'].values[0]
        kgi_status = df_market[df_market['指標名稱'].str.contains("009816")]['戰略狀態'].values[0]
        vix_price = float(df_market[df_market['指標名稱'].str.contains("VIX")]['最新報價'].values[0])
        wti_price = float(df_market[df_market['指標名稱'].str.contains("WTI")]['最新報價'].values[0])
        mtk_bias = float(df_market[df_market['指標名稱'].str.contains("2454")]['季線乖離率(%)'].values[0])
        
        # 判定全域狀態
        is_hunting = "[ 獵殺啟動 ]" in kgi_status or "[ 滿足狙擊乖離 ]" in pltr_status
        
        # --- 建立極簡手機排版文本 ---
        if is_hunting:
            print(f"🚨 【執行官戰術重擊授權核心】")
        else:
            print(f"📊 【執行官量化巡航日報】")
            
        print(f"時間座標：{today_str}")
        print(f"宏觀阻尼：WTI原油 {wti_price:.2f} USD | VIX恐慌 {vix_price:.2f}")
        print(f"聯發科過衝：{mtk_bias:.2f}%")
        print("-" * 35)

        # 僅輸出核心資產的真實狀態，絕不拖泥帶水
        print("【核心戰備資產狀態】")
        for _, row in df_market.iterrows():
            name = row['指標名稱'].split(" ")[0] # 僅取代碼，壓縮寬度
            price = row['最新報價']
            bias = row['季線乖離率(%)']
            status = row['戰略狀態']
            
            # 僅針對特定核心資產或觸發非警報狀態時輸出
            if "009816" in name or "PLTR" in name or "2330" in name:
                print(f"• {name}：{price} | 乖離 {bias}% \n  {status}")
                
        print("-" * 35)
        
        # 自動化極簡決策導航
        if is_hunting:
            print("🔥 [戰術判決]：引信已觸發！請核對硬性紀律：")
            print(f"  1. 009816 破季線 -> 24.3萬現金池解鎖。")
            print(f"  2. PLTR 滿足狙擊 -> VIX 是否大於 25？當前為 {vix_price}。")
        else:
            print("⚪ [戰術判決]：安全巡航。")
            print("  重力場處於常態高位。24.3萬現金池絕對鎖死。")
            print("  日常雙週引擎定時導航，繼續保持鱷魚潛伏。")

    finally:
        # --- 2. 還原標準控制台輸出並截取純文字 ---
        final_output_text = buffer.getvalue()
        sys.stdout = old_stdout
        print(final_output_text)

    # --- 3. 實體發送端 (無縫對接 Make 雲端管線) ---
    WEBHOOK_URL = "https://hook.us2.make.com/8chtd5ab53nga7phwmc45d8lf2esw5a9"
    try:
        payload = {"text": final_output_text}
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code == 200:
            print("🚀 成功：極簡手機版報表已同步發送。")
        else:
            print(f"❌ 失敗：錯誤碼：{response.status_code}")
    except Exception as e:
        print(f"⚠️ 通訊層異常：{str(e)}")

if __name__ == "__main__":
    main()