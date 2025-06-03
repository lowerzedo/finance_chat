import json
import os
import logging
import base64
import io
from datetime import datetime
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import requests
from PIL import Image
from sheets_integration import SheetsManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Environment variables - with safe defaults
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID')
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON')

# Configure Gemini only if API key is available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class ExpenseTracker:
    def __init__(self):
        # Only initialize if required env vars are present
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not found - AI features disabled")
            self.model = None
        else:
            self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Sheets manager will be initialized lazily
        self._sheets_manager = None
        
    @property
    def sheets_manager(self):
        """Lazy initialization of SheetsManager"""
        if self._sheets_manager is None and GOOGLE_CREDENTIALS_JSON and GOOGLE_SHEETS_ID:
            try:
                self._sheets_manager = SheetsManager(
                    credentials_json=GOOGLE_CREDENTIALS_JSON,
                    spreadsheet_id=GOOGLE_SHEETS_ID
                )
            except Exception as e:
                logger.error(f"Failed to initialize SheetsManager: {e}")
        return self._sheets_manager

    def extract_expense_data(self, text_content=None, image_data=None):
        """Extract expense information using Gemini 2.5 Flash"""
        if not self.model:
            return {"error": "AI service not available"}
        
        prompt = """
        Analyze this receipt/expense and extract the following information in JSON format:
        {
          "amount": float (just the number),
          "category": "one of: food, transport, utilities, shopping, entertainment, healthcare, other",
          "description": "brief description of the expense",
          "date": "YYYY-MM-DD format, use today if not clear",
          "merchant": "store/company name if available"
        }
        
        If this is not a valid expense or receipt, return: {"error": "Not a valid expense"}
        """
        
        try:
            if image_data:
                # Create image part for Gemini API - Fix: Don't log the image_data
                image_part = {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(image_data).decode()
                }
                
                # Process image with text
                response = self.model.generate_content([prompt, image_part])
            else:
                # Process text only
                response = self.model.generate_content(f"{prompt}\n\nText: {text_content}")
            
            # Fix: Check if response exists and has text
            if not response or not hasattr(response, 'text') or not response.text:
                logger.error("Empty response from Gemini API")
                return {"error": "No response from AI"}
            
            # Extract JSON from response
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            elif response_text.startswith('```'):
                response_text = response_text[3:-3]
            
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"error": "Failed to parse AI response"}
        except Exception as e:
            logger.error(f"Error processing with Gemini: {e}")
            return {"error": f"Processing failed: {str(e)}"}

    def log_to_sheets(self, expense_data):
        """Log expense to Google Sheets"""
        if not self.sheets_manager:
            logger.warning("Sheets not configured")
            return False
        
        try:
            return self.sheets_manager.log_expense(expense_data)
        except Exception as e:
            logger.error(f"Error logging to sheets: {e}")
            return False
    
    def get_monthly_summary(self, month_str=None):
        """Get monthly expense summary"""
        try:
            return self.sheets_manager.get_monthly_total(month_str)
        except Exception as e:
            logger.error(f"Error getting monthly summary: {e}")
            return None

def send_telegram_message(chat_id, text):
    """Send message back to Telegram user"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return None

def download_telegram_file(file_id):
    """Download file from Telegram"""
    try:
        # Get file path
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
        response = requests.get(url, params={"file_id": file_id})
        file_info = response.json()
        
        if not file_info.get('ok'):
            return None
            
        file_path = file_info['result']['file_path']
        
        # Download file
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        file_response = requests.get(file_url)
        
        return file_response.content
    except Exception as e:
        logger.error(f"Error downloading Telegram file: {e}")
        return None

# Flask Routes
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return jsonify({"status": "OK", "message": "Finance Tracker Bot is running"}), 200

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Main webhook endpoint for Telegram"""
    try:
        # Validate environment
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return jsonify({"error": "Bot not configured"}), 500
        
        # Get request data
        data = request.get_json()
        
        if not data or 'message' not in data:
            logger.info("Not a message event or invalid data")
            return jsonify({"status": "OK"}), 200
            
        message = data.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        
        if not chat_id:
            logger.warning("No chat_id found in message")
            return jsonify({"status": "OK"}), 200
        
        # Initialize tracker
        tracker = ExpenseTracker()
        expense_data = None
        
        # Handle different message types
        if 'photo' in message:
            # Handle photo
            photo = message['photo'][-1]  # Get highest resolution
            file_content = download_telegram_file(photo['file_id'])
            
            if file_content:
                # Convert to JPEG format if needed
                try:
                    image = Image.open(io.BytesIO(file_content))
                    # Convert to RGB if necessary (for PNG with transparency)
                    if image.mode in ('RGBA', 'LA', 'P'):
                        image = image.convert('RGB')
                    
                    # Save as JPEG bytes
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='JPEG', quality=85)
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    expense_data = tracker.extract_expense_data(image_data=img_byte_arr)
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
                    send_telegram_message(chat_id, "❌ Failed to process image")
                    return jsonify({"status": "OK"}), 200
            else:
                send_telegram_message(chat_id, "❌ Failed to download image")
                return jsonify({"status": "OK"}), 200
                
        elif 'document' in message:
            # Handle document
            document = message['document']
            if document['mime_type'].startswith('image/'):
                file_content = download_telegram_file(document['file_id'])
                if file_content:
                    try:
                        image = Image.open(io.BytesIO(file_content))
                        # Convert to RGB if necessary
                        if image.mode in ('RGBA', 'LA', 'P'):
                            image = image.convert('RGB')
                        
                        # Save as JPEG bytes
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='JPEG', quality=85)
                        img_byte_arr = img_byte_arr.getvalue()
                        
                        expense_data = tracker.extract_expense_data(image_data=img_byte_arr)
                    except Exception as e:
                        logger.error(f"Error processing document image: {e}")
                        send_telegram_message(chat_id, "❌ Failed to process document")
                        return jsonify({"status": "OK"}), 200
                else:
                    send_telegram_message(chat_id, "❌ Failed to download document")
                    return jsonify({"status": "OK"}), 200
            else:
                send_telegram_message(chat_id, "📄 Please send an image file")
                return jsonify({"status": "OK"}), 200
                
        elif 'text' in message:
            # Handle text message
            text_content = message['text']
            
            # Handle bot commands
            if text_content.startswith('/'):
                if text_content == '/start':
                    welcome_msg = """
🤖 <b>Finance Tracker Bot</b>

Send me:
📷 Receipt photos
💸 Text expenses (e.g., "Lunch $15")
📄 Bill screenshots

<b>Commands:</b>
/summary - Current month summary
/setup - Setup Google Sheets
                    """
                    send_telegram_message(chat_id, welcome_msg)
                
                elif text_content == '/summary':
                    summary = tracker.get_monthly_summary()
                    if summary:
                        summary_msg = f"""
📊 <b>Monthly Summary ({summary['month']})</b>

💰 <b>Total:</b> ${summary['total']:.2f}

<b>By Category:</b>
🍔 Food: ${summary['food']:.2f}
🚗 Transport: ${summary['transport']:.2f}
⚡ Utilities: ${summary['utilities']:.2f}
🛍️ Shopping: ${summary['shopping']:.2f}
🎬 Entertainment: ${summary['entertainment']:.2f}
🏥 Healthcare: ${summary['healthcare']:.2f}
📋 Other: ${summary['other']:.2f}
                        """
                        send_telegram_message(chat_id, summary_msg)
                    else:
                        send_telegram_message(chat_id, "❌ Failed to get summary")
                
                elif text_content == '/setup':
                    if tracker.sheets_manager:
                        success = tracker.sheets_manager.setup_sheets()
                        if success:
                            send_telegram_message(chat_id, "✅ Google Sheets setup completed!")
                        else:
                            send_telegram_message(chat_id, "❌ Failed to setup Google Sheets")
                    else:
                        send_telegram_message(chat_id, "❌ Google Sheets not configured")
                
                return jsonify({"status": "OK"}), 200
            
            expense_data = tracker.extract_expense_data(text_content=text_content)
        
        # Process expense data
        if expense_data:
            if 'error' in expense_data:
                send_telegram_message(chat_id, f"❌ {expense_data['error']}")
            else:
                # Log to sheets
                success = tracker.log_to_sheets(expense_data)
                
                if success:
                    response_msg = f"""
✅ <b>Expense Logged!</b>

💰 Amount: ${expense_data.get('amount', 'N/A')}
📂 Category: {expense_data.get('category', 'N/A').title()}
📝 Description: {expense_data.get('description', 'N/A')}
📅 Date: {expense_data.get('date', 'N/A')}
🏪 Merchant: {expense_data.get('merchant', 'N/A')}
                    """
                    send_telegram_message(chat_id, response_msg)
                else:
                    send_telegram_message(chat_id, "❌ Failed to log expense")
        else:
            send_telegram_message(chat_id, "❌ Could not process your message")
        
        return jsonify({"status": "OK"}), 200
        
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """Set Telegram webhook URL"""
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not configured"}), 500
    
    data = request.get_json()
    webhook_url = data.get('webhook_url')
    
    if not webhook_url:
        return jsonify({"error": "webhook_url required"}), 400
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        response = requests.post(url, json={"url": webhook_url})
        result = response.json()
        
        if result.get('ok'):
            return jsonify({"status": "success", "message": "Webhook set successfully"}), 200
        else:
            return jsonify({"status": "error", "message": result.get('description', 'Unknown error')}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# For local testing
if __name__ == "__main__":
    # Check for required environment variables
    missing_vars = []
    if not TELEGRAM_BOT_TOKEN:
        missing_vars.append("TELEGRAM_BOT_TOKEN")
    if not GEMINI_API_KEY:
        missing_vars.append("GEMINI_API_KEY")
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.warning("Some features may be disabled")
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug) 