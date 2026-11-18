import os
import requests
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LamixBot:
 def __init__(self):
     self.main_url = "https://panel.lamix.org" # Default Main Panel
     self.main_token = os.getenv("MAIN_API_TOKEN")
     self.headers = {
     "Authorization": f"Bearer {self.main_token}", 
     "Content-Type": "application/json"
     }
     self.session = requests.Session()
 
 # Load saved external panels from a local file
 self.panels_file = "external_panels.json"
 self.external_panels = self._load_panels()

 def _load_panels(self) -> List[Dict]:
     """Load saved external panels from JSON file."""
     if os.path.exists(self.panels_file):
         try:
             with open(self.panels_file, 'r') as f:
                 return json.load(f)
 except:
     return []
     return []

 def _save_panels(self):
     """Save external panels to JSON file."""
     with open(self.panels_file, 'w') as f:
         json.dump(self.external_panels, f, indent=4)

 def _api_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, panel_url: str = None, panel_token: str = None) -> Dict:
     """Generic request handler for all panels."""
     url = f"{panel_url}{endpoint}" if panel_url else f"{self.main_url}{endpoint}"
     headers = {
     "Authorization": f"Bearer {panel_token}" if panel_token else self.headers["Authorization"],
     "Content-Type": "application/json"
     }
 
 try:
     if method.upper() == "GET":
         response = self.session.get(url, headers=headers, params=params, timeout=10)
 elif method.upper() == "POST":
     response = self.session.post(url, headers=headers, json=data, timeout=10)
 else:
     raise ValueError(f"Unsupported method: {method}")

 if response.status_code == 429:
     retry_after = response.headers.get("Retry-After", 60)
     logger.info(f"Rate limited. Waiting {retry_after}s.")
     import time
     time.sleep(int(retry_after))
     return self._api_request(method, endpoint, params, data, panel_url, panel_token)

 response.raise_for_status()
 return response.json()

 except Exception as e:
     logger.error(f"API Error: {e}")
     return {"error": str(e)}

 def get_all_numbers(self, search_query: str = None) -> List[Dict]:
     """Fetches numbers from Main Panel and all External Panels."""
     all_numbers = []
 
 # Fetch from Main Panel
 try:
     params = {"limit": 500}
     if search_query:
         params["search"] = search_query
         data = self._api_request("GET", "/api/v1/numbers", params=params)
         if "records" in data:
             for num in data["records"]:
                 num["source"] = "Main Panel"
                 all_numbers.extend(data["records"])
 except Exception as e:
     logger.error(f"Error fetching main numbers: {e}")

 # Fetch from External Panels
 for panel in self.external_panels:
     try:
         data = self._api_request("GET", "/api/v1/numbers", limit=500, panel_url=panel["url"], panel_token=panel["token"])
         if "records" in data:
             for num in data["records"]:
                 num["source"] = f"Ext: {panel['name']}"
                 all_numbers.extend(data["records"])
 except Exception as e:
     logger.error(f"Error fetching from {panel['name']}: {e}")

 return all_numbers

# --- Telegram Bot Implementation ---
# Note: Requires python-telegram-bot library
try:
 from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
 from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

 # Load Configuration
 ADMIN_ID = int(os.getenv("ADMIN_ID", "987654321"))
 BOT_TOKEN = os.getenv("BOT_TOKEN")
 MAIN_TOKEN = os.getenv("MAIN_API_TOKEN")

 bot_instance = LamixBot()

 # Admin Menu
 def get_admin_menu():
     keyboard = [
     [InlineKeyboardButton("📊 Numbers Panel", callback_data='show_numbers')],
     [InlineKeyboardButton("📩 Messages", callback_data='show_messages')],
     [InlineKeyboardButton("👥 Client Management", callback_data='show_clients')],
     [InlineKeyboardButton("⚙️ Panel Manager (Add Panels)", callback_data='panel_manager')],
     [InlineKeyboardButton("❌ Stop Bot", callback_data='stop_bot')]
     ]
     return InlineKeyboardMarkup(keyboard)

 async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
     user_id = update.effective_user.id
     if user_id == ADMIN_ID:
         await update.message.reply_text(
         "🚀 **Admin Panel Activated**\n"
         "Welcome back! Use the buttons below to control your numbers.",
         reply_markup=get_admin_menu()
         )
 else:
     await update.message.reply_text("👋 Hello! I am your Lamix Bot. Please wait for Admin login.")

 async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
     query = update.callback_query
     await query.answer()
 
 if query.data == 'show_numbers':
     await query.edit_message_text(text="🔍 **Searching Numbers Across All Panels...**", parse_mode='Markdown')
     numbers = bot_instance.get_all_numbers()
 
 if not numbers:
     await query.edit_message_text(text="❌ **No numbers found.**")
     return

 text = "📱 **Global Numbers Report:**\n"
 text += f"Found: {len(numbers)} Records\n"
 text += "-" * 30
 for num in numbers[:10]: # Limit to first 10 for readability
     text += f"\n🔹 {num.get('number', 'Unknown')}\n"
     text += f" Source: {num.get('source', 'Unknown')}\n"
     text += f" Plan: {num.get('plan', 'Unknown')}\n"
 
 await query.edit_message_text(text=text, parse_mode='Markdown')

 elif query.data == 'show_messages':
     data = bot_instance._api_request("GET", "/api/v1/messages", limit=10)
     if "error" in data or not data.get("records"): 
         text = "📭 No messages."
 else:
     text = "📩 **Latest Messages:**\n"
     for msg in data["records"]:
         text += f"\nFrom: {msg.get('cli', 'Unknown')}\n"
         text += f"Msg: {msg.get('content', 'Unknown')}\n"
         text += f"Status: {msg.get('status', 'Unknown')}"
         await query.edit_message_text(text=text)

 elif query.data == 'panel_manager':
     await query.edit_message_text(
     text="🌐 **Panel Manager**\n\n"
     "1. **Add New Panel**\n"
     "2. **List Current Panels**\n"
     "3. **Remove Panel**\n"
     "4. **Back**",
     reply_markup=InlineKeyboardMarkup([
     [InlineKeyboardButton("➕ Add Panel", callback_data='panel_add')],
     [InlineKeyboardButton("👁️ List Panels", callback_data='panel_list')],
     [InlineKeyboardButton("🔙 Back", callback_data='show_numbers')]
     ])
     )

 elif query.data == 'panel_add':
     await query.edit_message_text(
     text="➕ **Add New Panel**\n\n"
     "Please send me the details in this order:\n"
     "1. Panel Name (e.g., UK Panel 1)\n"
     "2. Panel URL (e.g., https://panel1.lamix.org)\n"
     "3. API Token\n\n"
     "Example:\n"
     "Name: UK1\n"
     "URL: https://uk.panel.com\n"
     "Token: abc123",
     parse_mode='Markdown'
     )
     # Set a flag in context to indicate next message is add panel data
     context.user_data['action'] = 'add_panel'

 elif query.data == 'panel_list':
     panels = bot_instance.external_panels
     if not panels:
         text = "❌ No external panels added yet."
 else:
     text = "📋 **Current External Panels:**\n"
     for p in panels:
         text += f"🔹 {p['name']}\n URL: {p['url']}\n"
         await query.edit_message_text(text=text)

 elif query.data == 'stop_bot':
     await query.edit_message_text("🛑 Bot Stopped by Admin.")
     # In real scenario, you would stop the application
     # context.application.stop()

 # Message Handler for Text (Dynamic Panel Addition)
 async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
     user_id = update.effective_user.id
     if user_id != ADMIN_ID: return

 text = update.message.text.strip()
 action = context.user_data.get('action')

 if action == 'add_panel':
     parts = text.split('\n')
     if len(parts) >= 3:
         name = parts[0].split('Name:')[1].strip()
         url = parts[1].split('URL:')[1].strip()
         token = parts[2].split('Token:')[1].strip()
 
 # Add to list
 bot_instance.external_panels.append({"name": name, "url": url, "token": token})
 bot_instance._save_panels()
 
 await update.message.reply_text(f"✅ **Panel Added Successfully!**\nName: {name}")
 context.user_data['action'] = None
 else:
     await update.message.reply_text("⚠️ Invalid format. Please use the format shown above.")

 if __name__ == '__main__':
     if not BOT_TOKEN:
         print("❌ Error: BOT_TOKEN not found in.env")
         exit()
 
 app = ApplicationBuilder().token(BOT_TOKEN).build()
 app.add_handler(CommandHandler("start", start))
 app.add_handler(CallbackQueryHandler(handle_callback))
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
 
 print("🤖 Bot is running...")
 app.run_polling()

except ImportError:
 print("❌ Error: 'python-telegram-bot' library not found.")
 print("Install command: pip install python-telegram-bot")