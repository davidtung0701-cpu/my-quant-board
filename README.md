# 📊 Quant Tactical Dashboard (量化戰術儀表板)

An automated, lightweight quantitative market monitoring system. This Python-based dashboard tracks cross-market leading indicators, macroeconomic liquidity, and specific US/TW equities. It calculates moving averages, volatility, and bias (乖離率) to generate actionable tactical alerts, which are then pushed to Telegram via Make.com and GitHub Actions.

## ✨ Features
* **Cross-Market Monitoring**: Tracks US semiconductors (SOXX, NVDA), memory (MU), liquidity (HYG, 10Y Treasury), and Taiwan equities (009816, 2330).
* **Automated Risk Control**: Calculates 60-day moving average bias and 5-day volatility to detect overbought conditions or liquidity crunches.
* **Zero-Maintenance Execution**: Runs entirely in the cloud using GitHub Actions (cron scheduled).
* **High Signal-to-Noise Push**: Sends a minimalist, easy-to-read text report to Telegram via Make.com webhooks.

---

## 🚀 Setup Guide

To set up your own automated pipeline, follow these steps:

### Phase 1: Set up Make.com (The Gateway & Telegram Bot)
Make.com acts as the bridge between the GitHub script and your Telegram app.

1.  Log in to [Make.com](https://www.make.com/) and click **Create a new scenario**.
2.  **Add the Webhook Module**:
    * Click the `+` button and search for **Webhooks**.
    * Select **Custom webhook**.
    * Click **Add**, name your webhook (e.g., `Quant-Board-Hook`), and click **Save**.
    * **Copy the generated URL** (e.g., `https://hook.us2.make.com/...`). Keep this safe; you will need it for GitHub.
    * Click **OK**.
3.  **Add the Telegram Module**:
    * Add another module next to the Webhook and search for **Telegram Bot**.
    * Select **Send a Text Message or a Reply**.
    * Connect your Telegram Bot by providing your Bot Token (obtained from [@BotFather](https://t.me/botfather) on Telegram).
    * In the **Chat ID** field, enter your personal Chat ID (you can find this via [@userinfobot](https://t.me/userinfobot)).
    * In the **Text** field, map the `text` variable coming from the Webhook module.
4.  Turn the Scenario **ON** (switch at the bottom left) and click the **Save** icon.

### Phase 2: Set up GitHub (The Engine)
1.  **Fork or Clone this repository** to your own GitHub account.
2.  **Secure your Webhook URL**:
    * In your GitHub repository, go to **Settings**.
    * On the left sidebar, scroll down to **Security** > **Secrets and variables** > **Actions**.
    * Click the green button **New repository secret**.
    * **Name**: Enter exactly `MAKE_WEBHOOK_URL`.
    * **Secret**: Paste the Make.com Webhook URL you copied in Phase 1.
    * Click **Add secret**.
3.  **Enable GitHub Actions**:
    * Go to the **Actions** tab at the top of your repository.
    * If prompted, click **I understand my workflows, go ahead and enable them**.
    * Click on **Run Quant Board Daily** on the left sidebar.
    * Click the **Run workflow** dropdown on the right and click the green button to trigger a manual test run.

### Phase 3: Verification
Once the GitHub Action completes successfully (showing a green checkmark), check your Telegram app. You should receive the automated minimalist quantitative report. 

Going forward, GitHub Actions will automatically run the script and send you the report daily based on the schedule defined in `.github/workflows/run_board.yml`.

---

## 🛠️ Customization

You can modify the tracked assets by editing the `TICKERS` dictionary in `board_make.py`:

```python
TICKERS = {
    "Your Asset Name": "TICKER_SYMBOL",
    "NVDA (Nvidia)": "NVDA",
    "BTC (Bitcoin)": "BTC-USD"
}
