# Finance Tracker Bot (Flask)

A Telegram bot that tracks expenses using AI-powered receipt analysis with Google Gemini and logs data to Google Sheets.

## Features

- 📷 Receipt photo analysis
- 💸 Text expense parsing
- 📊 Monthly summaries
- 🔗 Google Sheets integration
- 🤖 AI-powered categorization

## Setup

### 1. Environment Variables

Create a `.env` file:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SHEETS_ID=your_google_sheets_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
PORT=5000
DEBUG=False
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Locally

```bash
python app.py
```

### 4. Set Telegram Webhook

```bash
curl -X POST http://localhost:5000/set_webhook \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-domain.com/webhook"}'
```

## Deployment

### Heroku

```bash
git add .
git commit -m "Deploy Flask app"
git push heroku main
```

### Railway/Render

1. Connect your GitHub repo
2. Set environment variables
3. Deploy automatically

## Bot Commands

- `/start` - Welcome message
- `/summary` - Monthly expense summary
- `/setup` - Initialize Google Sheets

## Usage

Send the bot:

- 📷 Receipt photos
- 💸 Text like "Lunch $15"
- 📄 Bill screenshots

The bot will automatically categorize and log expenses to your Google Sheet.
