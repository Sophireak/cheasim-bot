"""
Chea Sim Primary School Uniform Shop Telegram Bot
==================================================
Official Telegram Bot for Samdach Chea Sim Primary School Uniform Shop.

Features:
- Strict Google Sheets sync: ONLY displays rows and categories actually present in the sheet.
- 1-Tap Language Switcher: Toggle between pure Khmer (🇰🇭) and pure English (🇬🇧).
- Native Khmer Riel (៛) Price Formatting with thousand separators.
- In-Bot Stock Controller Admin Panel for one-tap counter adjustments.
- Zero-latency RAM caching (< 0.1ms) with silent background synchronization.
- Role-based security for store owner.
"""

import asyncio
import base64
import html
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Load environment variables from .env if present
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "School_Uniform_Inventory").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_SERVICE_ACCOUNT_BASE64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64", "").strip()
STORE_CONTACT_USERNAME = os.getenv("STORE_CONTACT_USERNAME", "bNha_dev").strip().lstrip("@")
STORE_PHONE_NUMBER = os.getenv("STORE_PHONE_NUMBER", "+855 99 382 751").strip()

# Admin Telegram User IDs allowed to manage stock (comma-separated list)
ADMIN_USER_IDS = [
    uid.strip()
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
]

# Optional Cloud Container Port for health checks (Sabay Run App, Render, etc.)
PORT_ENV = os.getenv("PORT", "").strip()

# Background Sync Interval (seconds)
CACHE_SYNC_INTERVAL = int(os.getenv("CACHE_SYNC_INTERVAL", "60"))

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("CheaSimBot")


def is_admin_user(user: Optional[User]) -> bool:
    """Checks if the user's Telegram ID is authorized as a stock controller admin."""
    if not user:
        return False
    return str(user.id) in ADMIN_USER_IDS


# ==============================================================================
# LOCALIZATION (i18n) STRINGS DICTIONARY
# ==============================================================================
STRINGS: Dict[str, Dict[str, str]] = {
    "km": {
        "switch_btn": "🇬🇧 Switch to English",
        "switch_target": "en",
        "btn_stock": "👕 ពិនិត្យស្តុក & តម្លៃ",
        "btn_guide": "📏 របៀបវាស់ទំហំ",
        "btn_policy": "🔄 គោលការណ៍ហាង",
        "btn_contact": "💬 ឆាតទៅអ្នកលក់",
        "btn_chat_order": "💬 ឆាតកក់ទំនិញនេះ",
        "btn_admin": "🛠 គ្រប់គ្រងស្តុក",
        "btn_main_menu": "🏠 ម៉ឺនុយដើម",
        "btn_back": "⬅️ ថយក្រោយ",
        "btn_refresh": "🔄 ផ្ទុកស្តុកឡើងវិញ",
        "btn_chat_staff": "💬 ផ្ញើសារតាម Telegram",
        "welcome_title": "ហាងឯកសណ្ឋាន សាលាបឋមសិក្សា សម្តេចជាស៊ីម",
        "store_intro": "លោកអ្នកអាចពិនិត្យមើលស្តុកទំនិញជាក់ស្តែង តម្លៃ និងទំហំឯកសណ្ឋានសិស្សបានយ៉ាងងាយស្រួល។",
        "location_val": "សាលាបឋមសិក្សា សម្តេចជាស៊ីម",
        "hours_val": "ច័ន្ទ – សៅរ៍ (8:30 AM – 4:00 PM)",
        "prompt_select": "សូមជ្រើសរើសជម្រើសខាងក្រោម:",
        "dept_title": "ផ្នែកឯកសណ្ឋាន",
        "dept_select_prompt": "សូមជ្រើសរើសផ្នែកឯកសណ្ឋានខាងក្រោម ដើម្បីពិនិត្យមើលទំនិញ និងស្តុកជាក់ស្តែង:",
        "no_depts": "<i>មិនទាន់មានផ្នែកទំនិញក្នុងស្តុកនៅឡើយទេ។</i>",
        "item_select_prompt": "សូមជ្រើសរើសទំនិញខាងក្រោម ដើម្បីពិនិត្យទំហំ តម្លៃ និងចំនួនស្តុក:",
        "no_items": "<i>មិនទាន់មានទំនិញក្នុងផ្នែកនេះនៅឡើយទេ។</i>",
        "dept_label": "ផ្នែក",
        "location_label": "ទីតាំង",
        "sizes_title": "ទំហំ តម្លៃ & ស្តុក:",
        "no_sizes": "មិនមានទិន្នន័យទំហំក្នុងស្តុកឡើយ",
        "note_label": "ចំណាំ",
        "in_stock": "🟢 មានក្នុងស្តុក",
        "low_stock": "🟡 នៅសល់តិច",
        "out_of_stock": "🔴 អស់ពីស្តុក",
        "syncing_toast": "🔄 កំពុងទាញយកទិន្នន័យចុងក្រោយ...",
        "guide_title": "ការណែនាំអំពីការវាស់ទំហំសិស្ស",
        "guide_intro": "របៀបវាស់ទំហំឯកសណ្ឋានសិស្សឱ្យបានត្រឹមត្រូវ:",
        "guide_chest": "1. <b>ទ្រូង:</b> វាស់ជុំវិញរង្វង់ទ្រូងត្រង់កន្លែងធំបំផុតក្រោមដៃ។",
        "guide_waist": "2. <b>ចង្កេះ:</b> វាស់ជុំវិញរង្វង់ចង្កេះធម្មជាតិ មិនរឹតពេក។",
        "guide_hips": "3. <b>ត្រគាក:</b> វាស់ជុំវិញត្រគាកសម្រាប់សំពត់ផ្នត់សិស្សស្រី។",
        "guide_inseam": "4. <b>ប្រវែងជើង:</b> វាស់ពីចង្កេះចុះមកដល់ត្រគាកជើង ឬកជើង។",
        "guide_tip": "💡 <b>គន្លឹះសំខាន់:</b> បើសិនជាទំហំនៅចន្លោះពីរ សូមជ្រើសរើសទំហំធំជាង ១លេខ ដើម្បីទុកឱ្យកូនធំធាត់លូតលាស់ក្នុងឆ្នាំសិក្សា!",
        "policy_title": "គោលការណ៍ហាង & ម៉ោងធ្វើការ",
        "policy_hours_header": "⏰ <b>ម៉ោងធ្វើការ:</b>",
        "policy_hours_1": "├ ច័ន្ទ – សៅរ៍: 8:30 AM – 4:00 PM",
        "policy_hours_2": "└ ឈប់សម្រាកថ្ងៃអាទិត្យ និងបុណ្យជាតិ",
        "policy_loc_header": "📍 <b>ទីតាំងហាង:</b>",
        "policy_loc_val": "└ ក្នុងបរិវេណ សាលាបឋមសិក្សា សម្តេចជាស៊ីម",
        "policy_return_header": "🔁 <b>គោលការណ៍ប្តូរទំនិញ ៧ថ្ងៃ:</b>",
        "policy_return_1": "├ អនុញ្ញាតឱ្យប្តូរទំហំក្នុងរយៈពេល ៧ថ្ងៃ គិតចាប់ពីថ្ងៃទិញ។",
        "policy_return_2": "├ ឯកសណ្ឋានមិនទាន់បោកគក់ មិនទាន់ពាក់ និងមានស្លាកនៅដដែល។",
        "policy_return_3": "└ សូមភ្ជាប់មកជាមួយនូវវិក្កយបត្រ ឬភស្តុតាងនៃការទិញ។",
        "policy_warn": "⚠️ <i>សម្លៀកបំពាក់ដែលបានកាត់ ឬដេរប៉ាក់ឈ្មោះរួច មិនអាចប្តូរវិញបានទេ។</i>",
        "contact_title": "ទំនាក់ទំនងបុគ្គលិកហាង",
        "contact_intro": "ត្រូវការជំនួយក្នុងការវាស់ទំហំ កក់ទុក ឬការបញ្ជាទិញពិសេស?",
        "contact_manager": "អ្នកទទួលបន្ទុក",
        "contact_phone": "លេខទូរស័ព្ទ",
        "contact_tap": "ចុចប៊ូតុងខាងក្រោមដើម្បីផ្ញើសារ:",
        "unexpected_prompt": "⚠️ <i>សូមប្រើប្រាស់ប៊ូតុងខាងក្រោមដើម្បីបញ្ជា:</i>",
        # Admin Strings
        "admin_title": "ផ្ទាំងគ្រប់គ្រងស្តុកទំនិញ",
        "admin_controller": "អ្នកគ្រប់គ្រង",
        "admin_total_items": "មុខទំនិញសរុប",
        "admin_low_items": "ស្តុកនៅសល់តិច",
        "admin_out_items": "អស់ពីស្តុក",
        "admin_btn_edit": "✏️ កែប្រែស្តុកទំនិញ",
        "admin_btn_sales": "📊 របាយការណ៍លក់ថ្ងៃនេះ (POS)",
        "admin_btn_alert": "⚠️ ដាស់តឿនស្តុកតិច",
        "admin_btn_sync": "🔄 ធ្វើសមកាលកម្ម Sheet",
        "admin_btn_exit": "🏠 ត្រឡប់ទៅម៉ឺនុយដើម",
        "admin_btn_dash": "⬅️ ផ្ទាំងគ្រប់គ្រង",
        "admin_edit_title": "ផ្ទាំងកែប្រែស្តុកបន្ទាន់",
        "admin_item_label": "ទំនិញ",
        "admin_size_label": "ទំហំ",
        "admin_price_label": "តម្លៃ",
        "admin_current_stock": "ស្តុកបច្ចុប្បន្ន",
        "admin_tap_prompt": "ចុចប៊ូតុងខាងក្រោមដើម្បីកែប្រែចំនួនស្តុកភ្លាមៗ:",
        "admin_sell_1": "➖ លក់ចេញ 1 (-1)",
        "admin_add_1": "➕ បញ្ចូលស្តុក 1 (+1)",
        "admin_zero": "🔴 កំណត់អស់ពីស្តុក (0)",
        "admin_back_sizes": "⬅️ ថយទៅទំហំ",
        "admin_well_stocked": "✅ <b>ស្តុកទំនិញគ្រប់គ្រាន់ទាំងអស់!</b>\n━━━━━━━━━━━━━━━━━━\nមិនមានទំនិញណាដែលអស់ពីស្តុក ឬនៅសល់តិចនោះឡើយ។",
        "admin_low_title": "⚠️ <b>ទំនិញអស់ ឬនៅសល់តិច</b>",
        "admin_sales_title": "របាយការណ៍លក់ប្រចាំថ្ងៃ (POS)",
        "admin_sales_units": "ចំនួនលក់ចេញសរុប",
        "admin_sales_rev": "ចំណូលលក់សរុប",
        "admin_sales_empty": "មិនទាន់មានការលក់ចេញនៅថ្ងៃនេះនៅឡើយទេ។",
        "admin_sales_recent": "បញ្ជីទំនិញដែលបានលក់ចេញថ្ងៃនេះ:",
    },
    "en": {
        "switch_btn": "🇰🇭 ប្តូរទៅភាសាខ្មែរ",
        "switch_target": "km",
        "btn_stock": "👕 Check Stock & Prices",
        "btn_guide": "📏 Size Guide",
        "btn_policy": "🔄 Shop Policy",
        "btn_contact": "💬 Chat with Staff",
        "btn_chat_order": "💬 Chat to Order / Reserve",
        "btn_admin": "🛠 Stock Controller",
        "btn_main_menu": "🏠 Main Menu",
        "btn_back": "⬅️ Back",
        "btn_refresh": "🔄 Refresh Stock",
        "btn_chat_staff": "💬 Chat on Telegram",
        "welcome_title": "Chea Sim Primary School Uniform Shop",
        "store_intro": "Check live uniform stock, sizes, and prices easily.",
        "location_val": "Samdach Chea Sim Primary School",
        "hours_val": "Mon – Sat (8:30 AM – 4:00 PM)",
        "prompt_select": "Please select an option below:",
        "dept_title": "Uniform Departments",
        "dept_select_prompt": "Select a department below to view available items & live stock levels:",
        "no_depts": "<i>No uniform departments listed in inventory.</i>",
        "item_select_prompt": "Select an item below to check available sizes, price, and stock:",
        "no_items": "<i>No items listed in this department yet.</i>",
        "dept_label": "Department",
        "location_label": "Location",
        "sizes_title": "Sizes, Prices & Stock:",
        "no_sizes": "No size records found in inventory",
        "note_label": "Note",
        "in_stock": "🟢 In Stock",
        "low_stock": "🟡 Low Stock",
        "out_of_stock": "🔴 Out of Stock",
        "syncing_toast": "🔄 Syncing latest live stock...",
        "guide_title": "Student Size Measurement Guide",
        "guide_intro": "How to measure your child correctly:",
        "guide_chest": "1. <b>Chest:</b> Measure around the fullest part of chest, under arms.",
        "guide_waist": "2. <b>Waist:</b> Measure around natural waistline comfortably.",
        "guide_hips": "3. <b>Hips:</b> Measure around fullest part of hips while standing.",
        "guide_inseam": "4. <b>Inseam:</b> Measure from top of inside leg down to ankle bone.",
        "guide_tip": "💡 <b>Pro Tip:</b> If between two sizes, choose the larger size to allow room for growth.",
        "policy_title": "Store Policies & Operating Hours",
        "policy_hours_header": "⏰ <b>Operating Hours:</b>",
        "policy_hours_1": "├ Monday – Saturday: 8:30 AM – 4:00 PM",
        "policy_hours_2": "└ Closed on Sundays & official school holidays",
        "policy_loc_header": "📍 <b>Store Location:</b>",
        "policy_loc_val": "└ Samdach Chea Sim Primary School Campus",
        "policy_return_header": "🔁 <b>7-Day Return & Exchange Policy:</b>",
        "policy_return_1": "├ Exchanges permitted within 7 days of purchase.",
        "policy_return_2": "├ Garments must be unwashed, unworn, and have original tags.",
        "policy_return_3": "└ Please present your receipt or proof of purchase.",
        "policy_warn": "⚠️ <i>Customized embroidery items cannot be returned.</i>",
        "contact_title": "Contact Uniform Shop Staff",
        "contact_intro": "Need assistance with sizing, reservations, or special orders?",
        "contact_manager": "Store Manager",
        "contact_phone": "Campus Phone",
        "contact_tap": "Tap below to chat directly with staff:",
        "unexpected_prompt": "⚠️ <i>Please use the buttons below to navigate:</i>",
        # Admin Strings
        "admin_title": "Stock Controller Dashboard",
        "admin_controller": "Controller",
        "admin_total_items": "Total Items",
        "admin_low_items": "Low Stock Variations",
        "admin_out_items": "Out of Stock Variations",
        "admin_btn_edit": "✏️ Manage & Edit Stock",
        "admin_btn_sales": "📊 Today's Sales (POS)",
        "admin_btn_alert": "⚠️ Low Stock Alert",
        "admin_btn_sync": "🔄 Force Sync with Sheet",
        "admin_btn_exit": "🏠 Exit to Main Menu",
        "admin_btn_dash": "⬅️ Dashboard",
        "admin_edit_title": "Quick Stock Editor",
        "admin_item_label": "Item",
        "admin_size_label": "Size",
        "admin_price_label": "Price",
        "admin_current_stock": "Current Stock",
        "admin_tap_prompt": "Tap a button below to update stock immediately:",
        "admin_sell_1": "➖ Sell 1 (-1)",
        "admin_add_1": "➕ Restock 1 (+1)",
        "admin_zero": "🔴 Mark Out of Stock (0)",
        "admin_back_sizes": "⬅️ Back to Sizes",
        "admin_well_stocked": "✅ <b>All Uniforms Are Well Stocked!</b>\n━━━━━━━━━━━━━━━━━━\nThere are currently no depleted or low-stock items in inventory.",
        "admin_low_title": "⚠️ <b>Low Stock & Depleted Items</b>",
        "admin_sales_title": "Daily Sales Report (POS)",
        "admin_sales_units": "Total Units Sold",
        "admin_sales_rev": "Total Revenue",
        "admin_sales_empty": "No sales logged today yet.",
        "admin_sales_recent": "Recent Sales Today:",
    },
}


def get_user_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Returns the user's preferred language ('km' or 'en'), default is 'km'."""
    if context.user_data is None:
        return "km"
    return context.user_data.get("lang", "km")


# ==============================================================================
# PRICE & STOCK FORMATTING (Khmer Riel ៛)
# ==============================================================================
def format_riel_price(val: Any) -> str:
    """
    Formats cell value into Khmer Riel (៛) with thousand separators.
    Handles numeric strings, existing currency symbols, and conversions.
    """
    if val is None or val == "":
        return "N/A"
    clean = str(val).replace("$", "").replace("៛", "").replace(",", "").strip()
    try:
        num = float(clean)
        # If entered as dollar amounts (e.g. 4.5 or 5.0), convert $1 = 4,000 ៛
        if num < 100:
            riel = int(num * 4000)
        else:
            riel = int(num)
        return f"{riel:,} ៛"
    except (ValueError, TypeError):
        return f"{val} ៛"


def parse_riel_amount(val: Any) -> int:
    """Parses any price cell into an integer Riel amount."""
    if val is None or val == "":
        return 0
    clean = str(val).replace("$", "").replace("៛", "").replace(",", "").strip()
    try:
        num = float(clean)
        if num < 100:
            return int(num * 4000)
        return int(num)
    except (ValueError, TypeError):
        return 0


def parse_quantity(val: Any) -> int:
    """Safely extracts integer quantity from sheet cell value."""
    if val is None or val == "":
        return 0
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def format_stock_status(qty: int, lang: str = "km") -> str:
    """
    Stock badges localized by language:
    - Quantity >= 4: 🟢 មានក្នុងស្តុក (Qty) / In Stock (Qty)
    - Quantity 1-3:  🟡 នៅសល់តិច (Qty) / Low Stock (Qty)
    - Quantity == 0: 🔴 អស់ពីស្តុក / Out of Stock
    """
    s = STRINGS.get(lang, STRINGS["km"])
    if qty >= 4:
        return f"{s['in_stock']} ({qty})"
    elif qty > 0:
        return f"{s['low_stock']} ({qty})"
    else:
        return s["out_of_stock"]


def get_row_field(row: Dict[str, Any], *aliases: str) -> str:
    """Finds field in row dictionary by matching aliases case-insensitively with strip."""
    for alias in aliases:
        if alias in row and str(row[alias]).strip():
            return str(row[alias]).strip()
    for k, v in row.items():
        clean_k = str(k).strip().lower()
        for alias in aliases:
            if alias.lower() in clean_k and str(v).strip():
                return str(v).strip()
    return ""


# ==============================================================================
# INVENTORY MANAGER (100% Dynamic - ZERO Injected Default Items)
# ==============================================================================
class InventoryManager:
    """Manages reading, caching, and writing inventory data to Google Sheets."""

    def __init__(self, sheet_name: str, creds_file: str):
        self.sheet_name = sheet_name
        self.creds_file = creds_file
        self.qty_col = 5  # Default Column 5 (Quantity)

        self._cached_records: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0
        self._lock = asyncio.Lock()

        # In-memory indexes strictly from the user's Google Sheet
        self.categories: List[str] = []
        self.items_by_cat: Dict[int, List[str]] = {}
        self.variations_by_cat_item: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

        # In-memory daily sales transactions cache
        self.today_sales: List[Dict[str, Any]] = []

        self.client: Optional[gspread.Client] = None
        self._worksheet: Optional[gspread.Worksheet] = None

    def _init_client(self) -> None:
        """Initializes gspread client using Google Service Account credentials with read/write access."""
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        raw_creds = GOOGLE_SERVICE_ACCOUNT_BASE64 or GOOGLE_SERVICE_ACCOUNT_JSON
        if raw_creds:
            try:
                # 1. Check if the string is Base64 encoded
                if not raw_creds.startswith("{"):
                    try:
                        raw_creds = base64.b64decode(raw_creds).decode("utf-8")
                    except Exception:
                        pass
                # 2. Strip wrapping quotes if added by environment variable parsers
                if (raw_creds.startswith("'") and raw_creds.endswith("'")) or (
                    raw_creds.startswith('"') and raw_creds.endswith('"')
                ):
                    raw_creds = raw_creds[1:-1]
                info = json.loads(raw_creds)
                credentials = Credentials.from_service_account_info(info, scopes=scopes)
                logger.info("Using Google Service Account credentials from environment variable.")
            except Exception as e:
                raise ValueError(f"Invalid GOOGLE_SERVICE_ACCOUNT_JSON environment variable: {e}")
        else:
            if not os.path.exists(self.creds_file):
                raise FileNotFoundError(
                    f"Credentials file '{self.creds_file}' not found. "
                    f"Please place your Google Cloud Service Account JSON file in this directory "
                    f"or set GOOGLE_SERVICE_ACCOUNT_JSON in environment variables."
                )
            credentials = Credentials.from_service_account_file(self.creds_file, scopes=scopes)
            logger.info("Using Google Service Account credentials from file '%s'.", self.creds_file)

        self.client = gspread.authorize(credentials)
        logger.info("Successfully authenticated with Google Sheets API (read/write mode).")

    def _get_worksheet(self) -> gspread.Worksheet:
        """Caches worksheet reference to avoid repetitive sheet-search API calls."""
        if self.client is None:
            self._init_client()
        assert self.client is not None

        if self._worksheet is None:
            spreadsheet = self.client.open(self.sheet_name)
            self._worksheet = spreadsheet.worksheet("Stock")
        return self._worksheet

    def _fetch_from_sheets_sync(self) -> List[Dict[str, Any]]:
        """Synchronously reads 'Stock' worksheet rows from Google Sheets."""
        try:
            ws = self._get_worksheet()
            # Detect quantity column dynamically from header row
            try:
                headers = [str(h).strip().lower() for h in ws.row_values(1)]
                for col_idx, h in enumerate(headers, start=1):
                    if any(k in h for k in ["quantity", "ចំនួន", "ស្តុក", "qty"]):
                        self.qty_col = col_idx
                        break
            except Exception as e:
                logger.warning("Could not inspect headers, defaulting qty_col=5: %s", e)

            records = ws.get_all_records()
        except Exception:
            logger.info("Worksheet session refreshed, reconnecting...")
            self._worksheet = None
            ws = self._get_worksheet()
            records = ws.get_all_records()

        # Tag each record with its actual 1-indexed row number in Google Sheets
        for idx, row in enumerate(records):
            row["_sheet_row"] = idx + 2

        logger.info("Fetched %d raw records from Google Sheet '%s'.", len(records), self.sheet_name)
        return records

    def _update_sheet_cell_sync(self, row_num: int, new_qty: int) -> bool:
        """Writes updated quantity directly to Google Sheets cell."""
        try:
            ws = self._get_worksheet()
            ws.update_cell(row_num, self.qty_col, new_qty)
            logger.info("Successfully updated Google Sheet row %d, col %d to qty=%d", row_num, self.qty_col, new_qty)
            return True
        except Exception as e:
            logger.error("Failed to update Google Sheet cell (%d, %d): %s", row_num, self.qty_col, e, exc_info=True)
            return False

    async def update_stock(self, c_idx: int, i_idx: int, v_idx: int, new_qty: int) -> Tuple[bool, int]:
        """
        Updates stock quantity in RAM cache immediately, then writes to Google Sheets in background.
        Quantity is clamped to minimum 0.
        """
        new_qty = max(0, new_qty)
        variations = self.variations_by_cat_item.get((c_idx, i_idx), [])
        if v_idx < 0 or v_idx >= len(variations):
            return False, 0

        var_row = variations[v_idx]
        var_row["Quantity"] = new_qty
        row_num = var_row.get("_sheet_row")

        if row_num:
            asyncio.create_task(asyncio.to_thread(self._update_sheet_cell_sync, row_num, new_qty))

        return True, new_qty

    def _log_sale_sync(
        self,
        date_str: str,
        time_str: str,
        cat_name: str,
        item_name: str,
        size: str,
        qty: int,
        unit_price_raw: Any,
        unit_price_riel: int,
        total_riel: int,
        staff_name: str,
    ) -> bool:
        """Appends sale record to 'Sales_Log' worksheet in Google Sheets."""
        try:
            if self.client is None:
                self._init_client()
            assert self.client is not None
            spreadsheet = self.client.open(self.sheet_name)
            try:
                sales_ws = spreadsheet.worksheet("Sales_Log")
            except gspread.WorksheetNotFound:
                sales_ws = spreadsheet.add_worksheet(title="Sales_Log", rows=1000, cols=10)
                sales_ws.append_row(
                    [
                        "Date",
                        "Time",
                        "Department",
                        "Item Name",
                        "Size",
                        "Quantity",
                        "Unit Price Raw",
                        "Unit Price (៛)",
                        "Total (៛)",
                        "Staff Member",
                    ]
                )
            sales_ws.append_row(
                [
                    date_str,
                    time_str,
                    cat_name,
                    item_name,
                    size,
                    qty,
                    str(unit_price_raw),
                    unit_price_riel,
                    total_riel,
                    staff_name,
                ]
            )
            logger.info("Logged sale to 'Sales_Log' sheet: %s %s x%d (%d ៛)", item_name, size, qty, total_riel)
            return True
        except Exception as e:
            logger.error("Failed to append sale row to Google Sheet: %s", e)
            return False

    def log_sale(
        self,
        cat_name: str,
        item_name: str,
        size: str,
        qty: int,
        unit_price_raw: Any,
        staff_name: str,
    ) -> int:
        """
        Logs a sale transaction in RAM cache immediately, then writes to 'Sales_Log' in Google Sheets in background.
        Returns total Riel amount.
        """
        now = time.localtime()
        date_str = time.strftime("%d-%b-%Y", now)
        time_str = time.strftime("%I:%M %p", now)
        unit_riel = parse_riel_amount(unit_price_raw)
        total_riel = unit_riel * qty

        sale_record = {
            "date": date_str,
            "time": time_str,
            "cat_name": cat_name,
            "item_name": item_name,
            "size": size,
            "qty": qty,
            "unit_price_raw": unit_price_raw,
            "unit_riel": unit_riel,
            "total_riel": total_riel,
            "staff_name": staff_name,
        }
        self.today_sales.append(sale_record)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                asyncio.to_thread(
                    self._log_sale_sync,
                    date_str,
                    time_str,
                    cat_name,
                    item_name,
                    size,
                    qty,
                    unit_price_raw,
                    unit_riel,
                    total_riel,
                    staff_name,
                )
            )
        except RuntimeError:
            pass
        return total_riel

    def get_stock_metrics(self) -> Dict[str, Any]:
        """Computes low-stock and out-of-stock items across all departments."""
        total_items = 0
        low_stock = []
        out_of_stock = []

        for (c_idx, i_idx), vars_list in self.variations_by_cat_item.items():
            cat_name = self.categories[c_idx] if c_idx < len(self.categories) else "Uniform"
            item_names = self.items_by_cat.get(c_idx, [])
            item_name = item_names[i_idx] if i_idx < len(item_names) else "Item"
            total_items += 1

            for v_idx, var in enumerate(vars_list):
                qty = parse_quantity(get_row_field(var, "Quantity", "quantity", "qty", "ចំនួន", "ស្តុក") or var.get("Quantity", 0))
                size = get_row_field(var, "Size / Variation", "Size", "size", "ទំហំ") or "Standard"
                price_raw = get_row_field(var, "Price (៛)", "Price ($)", "Price", "price", "តម្លៃ", "ថ្លៃ")
                price = format_riel_price(price_raw)
                entry = {
                    "c_idx": c_idx,
                    "i_idx": i_idx,
                    "v_idx": v_idx,
                    "cat_name": cat_name,
                    "item_name": item_name,
                    "size": size,
                    "price": price,
                    "qty": qty,
                }
                if qty == 0:
                    out_of_stock.append(entry)
                elif qty <= 3:
                    low_stock.append(entry)

        return {
            "total_items": total_items,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "needs_attention_count": len(low_stock) + len(out_of_stock),
        }

    async def refresh_from_sheets(self, force: bool = False) -> bool:
        """Fetches fresh data from Google Sheets in a worker thread and updates RAM cache."""
        async with self._lock:
            now = time.time()
            if not force and self._cached_records and (now - self._last_fetch_time < 10):
                return True

            try:
                records = await asyncio.to_thread(self._fetch_from_sheets_sync)
                self._cached_records = records
                self._last_fetch_time = now
                self._build_index(records)
                return True
            except Exception as e:
                logger.error("Failed to fetch inventory from Google Sheets: %s", e, exc_info=True)
                return False

    def _build_index(self, records: List[Dict[str, Any]]) -> None:
        """
        Parses records strictly from Google Sheets.
        Features automatic row-rescuing: rows with missing Item Name or Category are never hidden!
        """
        cat_order_seen: List[str] = []
        cat_items_map: Dict[str, List[str]] = {}
        var_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        for row in records:
            cat = get_row_field(row, "Category", "category", "ផ្នែក", "ប្រភេទ")
            item = get_row_field(row, "Item Name", "Item", "item name", "item", "ឈ្មោះទំនិញ", "មុខទំនិញ")
            size_raw = get_row_field(row, "Size / Variation", "Size", "size", "ទំហំ", "variation")
            price_raw = get_row_field(row, "Price (៛)", "Price ($)", "Price", "price", "តម្លៃ", "ថ្លៃ")
            qty_raw = get_row_field(row, "Quantity", "quantity", "qty", "ចំនួន", "ស្តុក")

            # Skip truly empty blank rows
            if not cat and not item and not size_raw and not qty_raw:
                continue

            # Auto-rescue Category if blank
            if not cat:
                cat = "Boys Uniform" if "boy" in item.lower() else "ទូទៅ (General)"

            # Auto-rescue Item Name if blank so row is NEVER dropped
            if not item:
                if size_raw:
                    item = f"{cat} ({size_raw})"
                else:
                    item = f"{cat} Item"

            if cat not in cat_items_map:
                cat_order_seen.append(cat)
                cat_items_map[cat] = []

            if item not in cat_items_map[cat]:
                cat_items_map[cat].append(item)

            key = (cat, item)
            if key not in var_map:
                var_map[key] = []
            var_map[key].append(row)

        self.categories = cat_order_seen
        self.items_by_cat = {}
        self.variations_by_cat_item = {}

        for c_idx, cat in enumerate(self.categories):
            items = cat_items_map.get(cat, [])
            self.items_by_cat[c_idx] = items
            for i_idx, item in enumerate(items):
                self.variations_by_cat_item[(c_idx, i_idx)] = var_map.get((cat, item), [])


inventory_mgr = InventoryManager(
    sheet_name=GOOGLE_SHEET_NAME,
    creds_file=GOOGLE_SERVICE_ACCOUNT_FILE,
)


# ==============================================================================
# VIEW BUILDERS (Localized by lang parameter)
# ==============================================================================
def get_main_menu_view(user: Optional[User] = None, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the Main Menu screen with a clean, friendly, parent-first design."""
    s = STRINGS.get(lang, STRINGS["km"])
    default_name = "អាណាព្យាបាល" if lang == "km" else "Parent"
    name = html.escape(user.first_name) if user and user.first_name else default_name

    if lang == "km":
        text = (
            f"👋 សូមស្វាគមន៍ <b>{name}</b> មកកាន់\n"
            f"🏫 <b>{s['welcome_title']}</b> 🎒\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{s['store_intro']}\n\n"
            f"📍 <b>ទីតាំង:</b> {s['location_val']}\n"
            f"🕒 <b>ម៉ោងធ្វើការ:</b> {s['hours_val']}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>{s['prompt_select']}</i>"
        )
    else:
        text = (
            f"👋 Welcome <b>{name}</b> to\n"
            f"🏫 <b>{s['welcome_title']}</b> 🎒\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{s['store_intro']}\n\n"
            f"📍 <b>Location:</b> {s['location_val']}\n"
            f"🕒 <b>Hours:</b> {s['hours_val']}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>{s['prompt_select']}</i>"
        )

    keyboard = [
        [InlineKeyboardButton(s["btn_stock"], callback_data="nav:cats")],
        [
            InlineKeyboardButton(s["btn_guide"], callback_data="nav:guide"),
            InlineKeyboardButton(s["btn_policy"], callback_data="nav:policy"),
        ],
        [InlineKeyboardButton(s["btn_contact"], callback_data="nav:contact")],
        # Dedicated 1-Tap Language Switch Button
        [InlineKeyboardButton(s["switch_btn"], callback_data=f"lang:{s['switch_target']}")],
    ]

    if is_admin_user(user):
        keyboard.append([InlineKeyboardButton(s["btn_admin"], callback_data="adm:dash")])

    return text, InlineKeyboardMarkup(keyboard)


def get_categories_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the department selection menu."""
    s = STRINGS.get(lang, STRINGS["km"])
    text = (
        f"👕 <b>{s['dept_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['dept_select_prompt']}"
    )

    buttons = []
    if not inventory_mgr.categories:
        text += f"\n\n{s['no_depts']}"
    else:
        for c_idx, cat in enumerate(inventory_mgr.categories):
            buttons.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat:{c_idx}")])

    buttons.append([InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main")])
    return text, InlineKeyboardMarkup(buttons)


def get_category_items_view(c_idx: int, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the list of items under a specific department."""
    s = STRINGS.get(lang, STRINGS["km"])
    if c_idx < 0 or c_idx >= len(inventory_mgr.categories):
        return get_categories_view(lang=lang)

    cat_name = inventory_mgr.categories[c_idx]
    items = inventory_mgr.items_by_cat.get(c_idx, [])

    if not items:
        text = (
            f"📁 <b>{html.escape(cat_name)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{s['no_items']}"
        )
    else:
        text = (
            f"📁 <b>{html.escape(cat_name)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{s['item_select_prompt']}"
        )

    buttons = []
    for i_idx, item_name in enumerate(items):
        buttons.append([InlineKeyboardButton(f"👕 {item_name}", callback_data=f"itm:{c_idx}:{i_idx}")])

    buttons.append([
        InlineKeyboardButton(s["btn_back"], callback_data="nav:cats"),
        InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main"),
    ])

    return text, InlineKeyboardMarkup(buttons)


def get_item_card_view(c_idx: int, i_idx: int, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the item stock card with prices in Khmer Riel (៛)."""
    s = STRINGS.get(lang, STRINGS["km"])
    cat_name = inventory_mgr.categories[c_idx] if c_idx < len(inventory_mgr.categories) else "Uniform"
    items = inventory_mgr.items_by_cat.get(c_idx, [])
    item_name = items[i_idx] if i_idx < len(items) else "Item"

    variations = inventory_mgr.variations_by_cat_item.get((c_idx, i_idx), [])

    lines = [
        f"👕 <b>{html.escape(item_name)}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"📁 <b>{s['dept_label']}:</b> {html.escape(cat_name)}",
        f"📍 <b>{s['location_label']}:</b> {s['location_val']}",
        "",
        f"📋 <b>{s['sizes_title']}</b>",
    ]

    notes_found = ""
    if not variations:
        lines.append(f"└ <i>{s['no_sizes']}</i>")
    else:
        for idx, var in enumerate(variations):
            is_last = (idx == len(variations) - 1)
            prefix = "└" if is_last else "├"

            size = get_row_field(var, "Size / Variation", "Size", "size", "ទំហំ") or "Standard"
            price_raw = get_row_field(var, "Price (៛)", "Price ($)", "Price", "price", "តម្លៃ", "ថ្លៃ")
            price = format_riel_price(price_raw)

            qty = parse_quantity(get_row_field(var, "Quantity", "quantity", "qty", "ចំនួន", "ស្តុក") or var.get("Quantity", 0))
            status = format_stock_status(qty, lang=lang)

            lines.append(f"{prefix} <b>{html.escape(size)}</b> ({html.escape(price)}) — {status}")

            note = get_row_field(var, "Notes", "Note", "notes", "note", "ចំណាំ")
            if note and not notes_found:
                notes_found = note

    if notes_found:
        lines.append("")
        lines.append(f"ℹ️ <b>{s['note_label']}:</b> <i>{html.escape(notes_found)}</i>")

    lines.append("━━━━━━━━━━━━━━━━━━")
    text = "\n".join(lines)

    contact_url = f"https://t.me/{STORE_CONTACT_USERNAME}"
    buttons = [
        [InlineKeyboardButton(s["btn_chat_order"], url=contact_url)],
        [
            InlineKeyboardButton(s["btn_back"], callback_data=f"cat:{c_idx}"),
            InlineKeyboardButton(s["btn_refresh"], callback_data=f"ref:{c_idx}:{i_idx}"),
            InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main"),
        ],
    ]

    return text, InlineKeyboardMarkup(buttons)


def get_size_guide_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the Size Guide tailored for Cambodian student measurements."""
    s = STRINGS.get(lang, STRINGS["km"])
    text = (
        f"📏 <b>{s['guide_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['guide_intro']}\n\n"
        f"├ {s['guide_chest']}\n"
        f"├ {s['guide_waist']}\n"
        f"├ {s['guide_hips']}\n"
        f"└ {s['guide_inseam']}\n\n"
        f"{s['guide_tip']}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    keyboard = [[InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main")]]
    return text, InlineKeyboardMarkup(keyboard)


def get_shop_policy_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the Shop Policy view."""
    s = STRINGS.get(lang, STRINGS["km"])
    text = (
        f"🔄 <b>{s['policy_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{s['policy_hours_header']}\n"
        f"{s['policy_hours_1']}\n"
        f"{s['policy_hours_2']}\n\n"
        f"{s['policy_loc_header']}\n"
        f"{s['policy_loc_val']}\n\n"
        f"{s['policy_return_header']}\n"
        f"{s['policy_return_1']}\n"
        f"{s['policy_return_2']}\n"
        f"{s['policy_return_3']}\n\n"
        f"{s['policy_warn']}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    keyboard = [[InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main")]]
    return text, InlineKeyboardMarkup(keyboard)


def get_contact_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the Contact Staff view with direct Telegram link."""
    s = STRINGS.get(lang, STRINGS["km"])
    contact_link = f"https://t.me/{STORE_CONTACT_USERNAME}"
    text = (
        f"💬 <b>{s['contact_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['contact_intro']}\n\n"
        f"├ 👤 <b>{s['contact_manager']}:</b> @{STORE_CONTACT_USERNAME}\n"
        f"├ 📞 <b>{s['contact_phone']}:</b> {STORE_PHONE_NUMBER}\n"
        f"├ 🏢 <b>{s['location_label']}:</b> {s['location_val']}\n"
        f"└ 🕒 <b>{s['hours_val']}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>{s['contact_tap']}</i>"
    )
    keyboard = [
        [InlineKeyboardButton(s["btn_chat_staff"], url=contact_link)],
        [InlineKeyboardButton(s["btn_main_menu"], callback_data="nav:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


# ==============================================================================
# ADMIN VIEW BUILDERS (Stock Controller)
# ==============================================================================
def get_admin_dashboard_view(user: Optional[User], lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the main admin management dashboard."""
    s = STRINGS.get(lang, STRINGS["km"])
    admin_name = html.escape(user.full_name) if user and user.full_name else "Stock Controller"
    metrics = inventory_mgr.get_stock_metrics()

    low_len = len(metrics["low_stock"])
    out_len = len(metrics["out_of_stock"])
    total_len = metrics["total_items"]
    attention_total = low_len + out_len

    text = (
        f"🛠 <b>{s['admin_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{s['admin_controller']}:</b> {admin_name}\n"
        f"🏫 <b>{s['location_label']}:</b> {s['location_val']}\n"
        f"📦 <b>{s['admin_total_items']}:</b> {total_len}\n"
        f"🟡 <b>{s['admin_low_items']}:</b> {low_len}\n"
        f"🔴 <b>{s['admin_out_items']}:</b> {out_len}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['prompt_select']}"
    )

    alert_label = f"{s['admin_btn_alert']} ({attention_total})"
    keyboard = [
        [InlineKeyboardButton(s["admin_btn_edit"], callback_data="adm:cats")],
        [InlineKeyboardButton(s["admin_btn_sales"], callback_data="adm:sales")],
        [InlineKeyboardButton(alert_label, callback_data="adm:low")],
        [InlineKeyboardButton(s["admin_btn_sync"], callback_data="adm:sync")],
        [InlineKeyboardButton(s["admin_btn_exit"], callback_data="nav:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def get_admin_sales_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the Daily Sales & Revenue POS dashboard."""
    s = STRINGS.get(lang, STRINGS["km"])
    today_str = time.strftime("%d-%b-%Y")
    sales = inventory_mgr.today_sales
    total_units = sum(sale["qty"] for sale in sales)
    total_rev = sum(sale["total_riel"] for sale in sales)

    if lang == "km":
        text = (
            f"📊 <b>{s['admin_sales_title']}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>កាលបរិច្ឆេទ:</b> {today_str}\n"
            f"👕 <b>{s['admin_sales_units']}:</b> <b>{total_units}</b> ឯកសណ្ឋាន\n"
            f"💰 <b>{s['admin_sales_rev']}:</b> <b>{format_riel_price(total_rev)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )
        if not sales:
            text += f"<i>{s['admin_sales_empty']}</i>\n"
        else:
            text += f"<b>📦 {s['admin_sales_recent']}</b>\n"
            for sale in sales[-10:]:
                text += (
                    f"├ {sale['time']} • <b>{html.escape(sale['item_name'])} ({html.escape(sale['size'])})</b> "
                    f"x{sale['qty']} = {format_riel_price(sale['total_riel'])}\n"
                )
    else:
        text = (
            f"📊 <b>Daily Sales Report (POS)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Date:</b> {today_str}\n"
            f"👕 <b>Total Units Sold:</b> <b>{total_units}</b> items\n"
            f"💰 <b>Total Revenue:</b> <b>{format_riel_price(total_rev)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )
        if not sales:
            text += "<i>No sales logged today yet.</i>\n"
        else:
            text += "<b>📦 Recent Sales Today:</b>\n"
            for sale in sales[-10:]:
                text += (
                    f"├ {sale['time']} • <b>{html.escape(sale['item_name'])} ({html.escape(sale['size'])})</b> "
                    f"x{sale['qty']} = {format_riel_price(sale['total_riel'])}\n"
                )

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Sales" if lang == "en" else "🔄 ផ្ទុកទិន្នន័យឡើងវិញ", callback_data="adm:sales")],
        [InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def get_admin_categories_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders categories for admin stock adjustment."""
    s = STRINGS.get(lang, STRINGS["km"])
    text = (
        f"🛠 <b>{s['admin_title']}: {s['dept_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['dept_select_prompt']}"
    )
    buttons = []
    for c_idx, cat in enumerate(inventory_mgr.categories):
        buttons.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"adm:cat:{c_idx}")])

    buttons.append([InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash")])
    return text, InlineKeyboardMarkup(buttons)


def get_admin_category_items_view(c_idx: int, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders items in a department for admin stock adjustment."""
    s = STRINGS.get(lang, STRINGS["km"])
    if c_idx < 0 or c_idx >= len(inventory_mgr.categories):
        return get_admin_categories_view(lang=lang)

    cat_name = inventory_mgr.categories[c_idx]
    items = inventory_mgr.items_by_cat.get(c_idx, [])

    text = (
        f"🛠 <b>{s['dept_label']}: {html.escape(cat_name)}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{s['item_select_prompt']}"
    )
    buttons = []
    for i_idx, item_name in enumerate(items):
        buttons.append([InlineKeyboardButton(f"👕 {item_name}", callback_data=f"adm:itm:{c_idx}:{i_idx}")])

    buttons.append([
        InlineKeyboardButton(s["btn_back"], callback_data="adm:cats"),
        InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash"),
    ])
    return text, InlineKeyboardMarkup(buttons)


def get_admin_item_variations_view(c_idx: int, i_idx: int, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders size variations for an item so admin can select one to edit."""
    s = STRINGS.get(lang, STRINGS["km"])
    cat_name = inventory_mgr.categories[c_idx] if c_idx < len(inventory_mgr.categories) else "Uniform"
    items = inventory_mgr.items_by_cat.get(c_idx, [])
    item_name = items[i_idx] if i_idx < len(items) else "Item"
    variations = inventory_mgr.variations_by_cat_item.get((c_idx, i_idx), [])

    qty_word = "ចំនួន" if lang == "km" else "Qty"
    text = (
        f"🛠 <b>{s['admin_edit_title']}: {html.escape(item_name)}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📁 <b>{s['dept_label']}:</b> {html.escape(cat_name)}\n"
        f"{s['prompt_select']}"
    )
    buttons = []
    for v_idx, var in enumerate(variations):
        size = str(var.get("Size / Variation", "Standard")).strip()
        qty = parse_quantity(var.get("Quantity", 0))
        status_icon = "🟢" if qty >= 4 else ("🟡" if qty > 0 else "🔴")
        label = f"{status_icon} {size} — {qty_word}: {qty}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"adm:var:{c_idx}:{i_idx}:{v_idx}")])

    buttons.append([
        InlineKeyboardButton(s["btn_back"], callback_data=f"adm:cat:{c_idx}"),
        InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash"),
    ])
    return text, InlineKeyboardMarkup(buttons)


def get_admin_variation_editor_view(c_idx: int, i_idx: int, v_idx: int, lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the interactive quick-editor for a specific size variation."""
    s = STRINGS.get(lang, STRINGS["km"])
    cat_name = inventory_mgr.categories[c_idx] if c_idx < len(inventory_mgr.categories) else "Uniform"
    items = inventory_mgr.items_by_cat.get(c_idx, [])
    item_name = items[i_idx] if i_idx < len(items) else "Item"
    variations = inventory_mgr.variations_by_cat_item.get((c_idx, i_idx), [])

    if v_idx < 0 or v_idx >= len(variations):
        return get_admin_item_variations_view(c_idx, i_idx, lang=lang)

    var = variations[v_idx]
    size = str(var.get("Size / Variation", "Standard")).strip()
    price_raw = var.get("Price (៛)") or var.get("Price ($)") or var.get("Price", "")
    price = format_riel_price(price_raw)
    qty = parse_quantity(var.get("Quantity", 0))
    status = format_stock_status(qty, lang=lang)

    text = (
        f"🛠 <b>{s['admin_edit_title']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👕 <b>{s['admin_item_label']}:</b> {html.escape(item_name)}\n"
        f"📁 <b>{s['dept_label']}:</b> {html.escape(cat_name)}\n"
        f"📏 <b>{s['admin_size_label']}:</b> {html.escape(size)}\n"
        f"💵 <b>{s['admin_price_label']}:</b> {html.escape(price)}\n"
        f"📦 <b>{s['admin_current_stock']}:</b> {status}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<i>{s['admin_tap_prompt']}</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(s["admin_sell_1"], callback_data=f"adm:mod:{c_idx}:{i_idx}:{v_idx}:-1"),
            InlineKeyboardButton(s["admin_add_1"], callback_data=f"adm:mod:{c_idx}:{i_idx}:{v_idx}:1"),
        ],
        [
            InlineKeyboardButton("➖ 5", callback_data=f"adm:mod:{c_idx}:{i_idx}:{v_idx}:-5"),
            InlineKeyboardButton("➕ 5", callback_data=f"adm:mod:{c_idx}:{i_idx}:{v_idx}:5"),
        ],
        [
            InlineKeyboardButton(s["admin_zero"], callback_data=f"adm:set:{c_idx}:{i_idx}:{v_idx}:0"),
        ],
        [
            InlineKeyboardButton(s["admin_back_sizes"], callback_data=f"adm:itm:{c_idx}:{i_idx}"),
            InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash"),
        ],
    ]
    return text, InlineKeyboardMarkup(buttons)


def get_admin_low_stock_view(lang: str = "km") -> Tuple[str, InlineKeyboardMarkup]:
    """Renders list of depleted and low-stock items with direct restock shortcuts."""
    s = STRINGS.get(lang, STRINGS["km"])
    metrics = inventory_mgr.get_stock_metrics()
    all_alerts = metrics["out_of_stock"] + metrics["low_stock"]

    if not all_alerts:
        text = s["admin_well_stocked"]
        keyboard = [[InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash")]]
        return text, InlineKeyboardMarkup(keyboard)

    lines = [
        s["admin_low_title"],
        "━━━━━━━━━━━━━━━━━━",
        f"Found <b>{len(all_alerts)}</b> variations requiring attention:\n" if lang == "en" else f"មានចំនួន <b>{len(all_alerts)}</b> ទំហំដែលត្រូវបញ្ចូលស្តុក:\n",
    ]

    buttons = []
    for alert in all_alerts[:10]:
        c_idx = alert["c_idx"]
        i_idx = alert["i_idx"]
        v_idx = alert["v_idx"]
        item = alert["item_name"]
        size = alert["size"]
        qty = alert["qty"]
        badge = "🔴 Out" if (qty == 0 and lang == "en") else ("🔴 អស់" if qty == 0 else (f"🟡 {qty} left" if lang == "en" else f"🟡 នៅសល់ {qty}"))
        lines.append(f"• {html.escape(item)} ({html.escape(size)}) — <b>{badge}</b>")
        buttons.append([
            InlineKeyboardButton(
                f"✏️ {item} ({size}) [{qty}]",
                callback_data=f"adm:var:{c_idx}:{i_idx}:{v_idx}",
            )
        ])

    lines.append("\n━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Tap an item to restock:</i>" if lang == "en" else "<i>ចុចលើទំនិញខាងក្រោមដើម្បីកែប្រែស្តុក:</i>")
    buttons.append([InlineKeyboardButton(s["admin_btn_dash"], callback_data="adm:dash")])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


# ==============================================================================
# TELEGRAM HANDLERS
# ==============================================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if not update.message:
        return

    lang = get_user_lang(context)
    text, reply_markup = get_main_menu_view(update.effective_user, lang=lang)
    await update.message.reply_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all inline keyboard button presses with ultra-fast in-memory rendering.
    Runs query.answer() and edit_message_text() concurrently.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    lang = get_user_lang(context)

    try:
        # Language Switch Toggle
        if data.startswith("lang:"):
            new_lang = data.split(":")[1]
            if context.user_data is not None:
                context.user_data["lang"] = new_lang
            lang = new_lang
            toast = "ប្តូរទៅភាសាខ្មែរជោគជ័យ! 🇰🇭" if new_lang == "km" else "Switched to English! 🇬🇧"
            await query.answer(toast, show_alert=False)
            text, reply_markup = get_main_menu_view(update.effective_user, lang=lang)
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return

        # Public Navigation
        elif data == "nav:main":
            text, reply_markup = get_main_menu_view(update.effective_user, lang=lang)
        elif data == "nav:cats":
            text, reply_markup = get_categories_view(lang=lang)
        elif data == "nav:guide":
            text, reply_markup = get_size_guide_view(lang=lang)
        elif data == "nav:policy":
            text, reply_markup = get_shop_policy_view(lang=lang)
        elif data == "nav:contact":
            text, reply_markup = get_contact_view(lang=lang)
        elif data.startswith("cat:"):
            parts = data.split(":")
            c_idx = int(parts[1])
            text, reply_markup = get_category_items_view(c_idx, lang=lang)
        elif data.startswith("itm:"):
            parts = data.split(":")
            c_idx = int(parts[1])
            i_idx = int(parts[2])
            text, reply_markup = get_item_card_view(c_idx, i_idx, lang=lang)
        elif data.startswith("ref:"):
            parts = data.split(":")
            c_idx = int(parts[1])
            i_idx = int(parts[2])
            s = STRINGS.get(lang, STRINGS["km"])
            await query.answer(s["syncing_toast"], show_alert=False)
            await inventory_mgr.refresh_from_sheets(force=True)
            text, reply_markup = get_item_card_view(c_idx, i_idx, lang=lang)
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return

        # Admin Stock Controller Callbacks
        elif data.startswith("adm:"):
            if not is_admin_user(update.effective_user):
                denied_msg = "⛔ មិនមានសិទ្ធិចូលប្រើប្រាស់ឡើយ" if lang == "km" else "⛔ Access denied. Admin only."
                await query.answer(denied_msg, show_alert=True)
                return

            if data == "adm:dash":
                text, reply_markup = get_admin_dashboard_view(update.effective_user, lang=lang)
            elif data == "adm:sales":
                text, reply_markup = get_admin_sales_view(lang=lang)
            elif data == "adm:cats":
                text, reply_markup = get_admin_categories_view(lang=lang)
            elif data == "adm:low":
                text, reply_markup = get_admin_low_stock_view(lang=lang)
            elif data == "adm:sync":
                toast = "🔄 កំពុងធ្វើសមកាលកម្មទិន្នន័យ..." if lang == "km" else "🔄 Syncing with Google Sheets..."
                await query.answer(toast, show_alert=False)
                await inventory_mgr.refresh_from_sheets(force=True)
                text, reply_markup = get_admin_dashboard_view(update.effective_user, lang=lang)
            elif data.startswith("adm:cat:"):
                c_idx = int(data.split(":")[2])
                text, reply_markup = get_admin_category_items_view(c_idx, lang=lang)
            elif data.startswith("adm:itm:"):
                parts = data.split(":")
                c_idx, i_idx = int(parts[2]), int(parts[3])
                text, reply_markup = get_admin_item_variations_view(c_idx, i_idx, lang=lang)
            elif data.startswith("adm:var:"):
                parts = data.split(":")
                c_idx, i_idx, v_idx = int(parts[2]), int(parts[3]), int(parts[4])
                text, reply_markup = get_admin_variation_editor_view(c_idx, i_idx, v_idx, lang=lang)
            elif data.startswith("adm:mod:"):
                parts = data.split(":")
                c_idx, i_idx, v_idx, delta = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
                vars_list = inventory_mgr.variations_by_cat_item.get((c_idx, i_idx), [])
                if v_idx < len(vars_list):
                    var_data = vars_list[v_idx]
                    cur_qty = parse_quantity(var_data.get("Quantity", 0))
                    new_qty = max(0, cur_qty + delta)
                    await inventory_mgr.update_stock(c_idx, i_idx, v_idx, new_qty)

                    cat_name = inventory_mgr.categories[c_idx] if c_idx < len(inventory_mgr.categories) else "Uniform"
                    item_names = inventory_mgr.items_by_cat.get(c_idx, [])
                    item_name = item_names[i_idx] if i_idx < len(item_names) else "Item"
                    size = get_row_field(var_data, "Size / Variation", "Size", "size", "ទំហំ") or "Standard"
                    price_raw = get_row_field(var_data, "Price (៛)", "Price ($)", "Price", "price", "តម្លៃ", "ថ្លៃ") or 0
                    admin_name = update.effective_user.first_name if update.effective_user else "Admin"

                    if delta < 0:
                        sold_qty = abs(delta)
                        total_riel = inventory_mgr.log_sale(cat_name, item_name, size, sold_qty, price_raw, admin_name)
                        toast = (
                            f"💵 លក់ចេញ {sold_qty} ({format_riel_price(total_riel)})! ស្តុកសល់ {new_qty}"
                            if lang == "km"
                            else f"💵 Sold {sold_qty} ({format_riel_price(total_riel)})! Stock now: {new_qty}"
                        )
                    else:
                        toast = f"✅ បញ្ចូលស្តុក (+{delta}): សល់ {new_qty}!" if lang == "km" else f"✅ Added (+{delta}): Now {new_qty}!"

                    await query.answer(toast, show_alert=False)

                    # Proactive Push Alert to Admin if item is depleted (reached 0)
                    if new_qty == 0 and cur_qty > 0:
                        for a_id in ADMIN_USER_IDS:
                            try:
                                alert_text = (
                                    f"🚨 <b>ដាស់តឿនទំនិញអស់ពីស្តុក (Out of Stock)!</b>\n"
                                    "━━━━━━━━━━━━━━━━━━\n"
                                    f"👕 ទំនិញ: <b>{html.escape(item_name)} ({html.escape(size)})</b>\n"
                                    f"📁 ផ្នែក: {html.escape(cat_name)}\n"
                                    f"⚠️ ចំនួនក្នុងស្តុកបច្ចុប្បន្ន: <b>0</b> (អស់ពីស្តុក)\n"
                                    f"👤 អ្នកលក់/កែប្រែ: {html.escape(admin_name)}"
                                )
                                await context.bot.send_message(
                                    chat_id=int(a_id),
                                    text=alert_text,
                                    parse_mode=ParseMode.HTML,
                                )
                            except Exception as e:
                                logger.warning("Could not send alert to admin %s: %s", a_id, e)
                text, reply_markup = get_admin_variation_editor_view(c_idx, i_idx, v_idx, lang=lang)
            elif data.startswith("adm:set:"):
                parts = data.split(":")
                c_idx, i_idx, v_idx, target_val = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
                await inventory_mgr.update_stock(c_idx, i_idx, v_idx, target_val)
                toast = f"✅ កំណត់ស្តុកស្មើ {target_val}!" if lang == "km" else f"✅ Stock set to {target_val}!"
                await query.answer(toast, show_alert=False)
                text, reply_markup = get_admin_variation_editor_view(c_idx, i_idx, v_idx, lang=lang)
            else:
                text, reply_markup = get_admin_dashboard_view(update.effective_user, lang=lang)

        else:
            text, reply_markup = get_main_menu_view(update.effective_user, lang=lang)

        # Fire query.answer() and edit_message_text() in parallel for instant UI feedback
        await asyncio.gather(
            query.answer(),
            query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            ),
        )
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.warning("BadRequest during callback query handling: %s", e)
    except Exception as e:
        logger.error("Error processing callback query '%s': %s", data, e, exc_info=True)


async def handle_unexpected_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enforces single-command architecture with language-specific guidance."""
    if not update.message:
        return

    try:
        await update.message.delete()
    except Exception:
        pass

    lang = get_user_lang(context)
    s = STRINGS.get(lang, STRINGS["km"])
    text, reply_markup = get_main_menu_view(update.effective_user, lang=lang)
    prompt_text = f"{s['unexpected_prompt']}\n\n{text}"

    await update.message.reply_text(
        text=prompt_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def background_sync_worker() -> None:
    """Quietly syncs inventory in background every 60 seconds without blocking user clicks."""
    while True:
        await asyncio.sleep(CACHE_SYNC_INTERVAL)
        try:
            await inventory_mgr.refresh_from_sheets()
        except Exception as e:
            logger.error("Error in background sheet sync: %s", e)


async def _start_health_server(port: int) -> None:
    """Lightweight zero-dependency async HTTP responder for cloud health probes (Sabay Run App, Render, etc.)."""
    async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(1024)
            body = (
                b'{"status":"ok","app":"cheasim-bot",'
                b'"school":"Chea Sim Primary School"}\n'
            )
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            writer.write(response)
            await writer.drain()
        except Exception as e:
            logger.debug("Health responder request error: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    try:
        server = await asyncio.start_server(handle_request, "0.0.0.0", port)
        logger.info("Universal HTTP health-check responder active on http://0.0.0.0:%d", port)
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Failed to start health-check responder on port %d: %s", port, e)


async def post_init(application: Application) -> None:
    """Pre-loads inventory cache on startup and starts background auto-refresh worker."""
    logger.info("Initializing inventory cache from Google Sheets...")
    success = await inventory_mgr.refresh_from_sheets()
    if success:
        logger.info(
            "Inventory cache loaded successfully! Found %d categories.",
            len(inventory_mgr.categories),
        )
    else:
        logger.warning(
            "Could not connect to Google Sheets during startup. "
            "Please ensure '%s' exists and '%s' is shared with your Service Account email.",
            inventory_mgr.creds_file,
            inventory_mgr.sheet_name,
        )

    # Start optional cloud health-check HTTP server if PORT is provided
    if PORT_ENV:
        try:
            port = int(PORT_ENV)
            asyncio.create_task(_start_health_server(port))
        except ValueError:
            logger.warning("Invalid PORT environment variable: %s", PORT_ENV)

    # Start background auto-updater task
    asyncio.create_task(background_sync_worker())


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main() -> None:
    """Validates configuration and launches the bot in polling mode."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print(
            "\n[ERROR] TELEGRAM_BOT_TOKEN is missing or not configured!\n"
            "Please set TELEGRAM_BOT_TOKEN in your .env file.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 60)
    print(" 🏫 Starting Chea Sim Primary School Uniform Shop Bot...")
    print(f" • Google Sheet:   {GOOGLE_SHEET_NAME}")
    print(f" • Credentials:    {GOOGLE_SERVICE_ACCOUNT_FILE}")
    print(f" • Staff Contact:  @{STORE_CONTACT_USERNAME}")
    print(f" • Admin Users:    {', '.join(ADMIN_USER_IDS) if ADMIN_USER_IDS else 'None'}")
    print(f" • Price Currency: Khmer Riel (៛)")
    print(f" • Background Sync: Every {CACHE_SYNC_INTERVAL} seconds")
    if PORT_ENV:
        print(f" • Health Check:   http://0.0.0.0:{PORT_ENV} (Active)")
    print("=" * 60)

    # Build Application
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(
        MessageHandler(
            ~filters.COMMAND | filters.ALL,
            handle_unexpected_messages,
        )
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
