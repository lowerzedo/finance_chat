# Finance Chat Bot

A Telegram bot that automatically logs expenses to Google Sheets using AI-powered receipt analysis.

## Features

- 📷 **Photo Receipt Analysis** - Send receipt photos for automatic expense extraction
- 💬 **Text Expense Logging** - Send text like "Coffee $5.50" for quick logging
- 🤖 **AI-Powered Categorization** - Uses Gemini Flash API for smart categorization
- 📊 **Google Sheets Integration** - Automatic logging and monthly summaries
- 📱 **Real-time Feedback** - Instant confirmation with expense details

## Architecture

```
Telegram Bot → AWS Lambda → Gemini Flash API → Google Sheets
```

## Prerequisites

1. **Telegram Bot Token** - Create via [@BotFather](https://t.me/botfather)
2. **Google AI Studio API Key** - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. **Google Sheets** - Create a new spreadsheet and get the ID
4. **Google Service Account** - For Sheets API access
5. **AWS Account** - For Lambda deployment

## Setup Instructions

### 1. Google Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Sheets API
4. Create a service account:
   - Go to IAM & Admin → Service Accounts
   - Create Service Account
   - Download JSON key file
5. Share your Google Sheet with the service account email

### 2. Environment Variables

Set these environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export GEMINI_API_KEY="your_gemini_api_key"
export GOOGLE_SHEETS_ID="your_sheet_id_from_url"
export GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'  # JSON content
```

### 3. Installation

```bash
# Clone/download the project
cd finance_chat

# Install dependencies
pip install -r requirements.txt

# Install Zappa for deployment
pip install zappa
```

### 4. Deployment

```bash
# Deploy to development
python deploy.py dev

# Deploy to production
python deploy.py production
```

Or manually:

```bash
# First time deployment
zappa deploy dev

# Updates
zappa update dev

# Set Telegram webhook
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "YOUR_LAMBDA_URL"}'
```

## Usage

### Bot Commands

- `/start` - Welcome message and instructions
- `/summary` - Get current month expense summary
- `/setup` - Initialize Google Sheets structure

### Expense Logging

1. **Photo Receipts**: Send any receipt photo
2. **Text Expenses**: Send messages like:
   - "Lunch $15.50"
   - "Gas station $40"
   - "Grocery shopping $85.20"

### Example Response

```
✅ Expense Logged!

💰 Amount: $15.50
📂 Category: Food
📝 Description: Lunch
📅 Date: 2024-01-15
🏪 Merchant: Restaurant ABC
```

## Google Sheets Structure

### Expenses Sheet

| Date       | Amount | Category | Description | Merchant       | Month   |
| ---------- | ------ | -------- | ----------- | -------------- | ------- |
| 2024-01-15 | 15.50  | food     | Lunch       | Restaurant ABC | 2024-01 |

### Monthly_Totals Sheet

| Month   | Total_Amount | Food   | Transport | Utilities | Shopping | Entertainment | Healthcare | Other |
| ------- | ------------ | ------ | --------- | --------- | -------- | ------------- | ---------- | ----- |
| 2024-01 | 250.75       | 120.50 | 45.25     | 85.00     | 0        | 0             | 0          | 0     |

## Configuration

### Categories

- `food` - Restaurants, groceries, dining
- `transport` - Gas, parking, rideshare
- `utilities` - Electric, water, internet
- `shopping` - Retail purchases
- `entertainment` - Movies, games, events
- `healthcare` - Medical, pharmacy
- `other` - Miscellaneous expenses

### Zappa Settings

Modify `zappa_settings.json` for custom configuration:

- Memory size (512MB dev, 1024MB prod)
- Timeout (30s dev, 60s prod)
- AWS region and S3 bucket

## Local Testing

```bash
python app.py
```

Test with sample event:

```python
test_event = {
    "body": json.dumps({
        "message": {
            "chat": {"id": 123456789},
            "text": "Coffee $5.50"
        }
    })
}
```

## Troubleshooting

### Common Issues

1. **"Failed to download image"**

   - Check Telegram bot token
   - Verify Lambda has internet access

2. **"Processing failed"**

   - Check Gemini API key
   - Verify API quota limits

3. **"Failed to log expense"**
   - Check Google credentials
   - Verify Sheet ID and permissions

### Logs

View Lambda logs:

```bash
zappa tail dev
```

## Security Notes

- Store credentials as environment variables
- Use IAM roles with minimal permissions
- Enable CloudWatch logging for monitoring
- Consider VPC deployment for enhanced security

## Cost Estimation

- **Lambda**: ~$0.20/month (1000 requests)
- **Gemini API**: ~$1.50/month (1000 requests)
- **Google Sheets API**: Free tier sufficient
- **Data Transfer**: Minimal costs

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

MIT License - see LICENSE file for details
