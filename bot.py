import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import logging
from src.utils import load_config
from src.db import init_db, get_configs_by_protocol, cleanup_old_configs, clear_all_configs, get_db_connection
from src.link_collector import collect_v2ray_links
from src.proxy_collector import collect_proxies
from src.proxy_tester import test_all_proxies
import asyncio
from dotenv import load_dotenv
import sqlite3

# تنظیم لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# لود متغیرهای محیطی
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def is_admin(user_id):
    """بررسی اینکه آیا کاربر ادمین است یا خیر"""
    try:
        config = load_config()
        return user_id in config["telegram"]["admin_ids"]
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع ربات با منوی گرافیکی"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    keyboard = [
        [
            InlineKeyboardButton("انتخاب پروتکل 📡", callback_data="cmd_protocol"),
            InlineKeyboardButton("به‌روزرسانی کانفیگ‌ها 🔄", callback_data="cmd_update"),
        ],
        [
            InlineKeyboardButton("دریافت پروکسی‌ها 🌐", callback_data="cmd_proxies"),
            InlineKeyboardButton("به‌روزرسانی پروکسی‌ها 🔄", callback_data="cmd_update_proxies"),
        ],
        [
            InlineKeyboardButton("تست پروکسی‌ها 🧪", callback_data="cmd_test_proxies"),
            InlineKeyboardButton("آمار کانفیگ‌ها 📊", callback_data="cmd_stats"),
        ],
        [
            InlineKeyboardButton("راهنما ❓", callback_data="cmd_help"),
            InlineKeyboardButton("پاک کردن همه کانفیگ‌ها 🗑️", callback_data="cmd_clear"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات کانفیگ V2Ray و پروکسی خوش اومدی! 😊\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور نمایش راهنمای ربات"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    help_text = (
        "📋 راهنمای دستورات ربات:\n\n"
        "/start - شروع کار با ربات و نمایش منوی اصلی\n"
        "/help - نمایش این راهنما\n"
        "/protocol - انتخاب پروتکل و دریافت کانفیگ‌ها\n"
        "/stats - نمایش آمار کانفیگ‌ها و پروکسی‌ها\n"
        "/clear - پاک کردن همه کانفیگ‌ها و پروکسی‌ها (نیاز به تأیید)\n\n"
        "⚠️ از منوی گرافیکی برای دریافت، به‌روزرسانی یا تست پروکسی‌ها استفاده کن!\n"
        "⚠️ فقط ادمین‌ها می‌تونن از این دستورات استفاده کنن!"
    )
    await update.message.reply_text(help_text)

async def protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور انتخاب پروتکل"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    protocols = ["vmess", "vless", "hysteria2"]
    keyboard = [[InlineKeyboardButton(protocol, callback_data=f"protocol_{protocol}") for protocol in protocols]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("یه پروتکل انتخاب کن:", reply_markup=reply_markup)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور پاک کردن همه کانفیگ‌ها و پروکسی‌ها با تأیید"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    keyboard = [
        [InlineKeyboardButton("بله، پاک کن 🗑️", callback_data="confirm_clear")],
        [InlineKeyboardButton("خیر، لغو کن ❌", callback_data="cancel_clear")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "مطمئنی می‌خوای همه کانفیگ‌ها و پروکسی‌ها رو پاک کنی؟ این کار قابل بازگشت نیست! 😳",
        reply_markup=reply_markup
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور نمایش آمار دیتابیس"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    try:
        config = load_config()
        db_path = config["database"]["path"]
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            # بررسی وجود جدول configs
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configs'")
            if not c.fetchone():
                logger.error("جدول configs در دیتابیس وجود ندارد!")
                await update.message.reply_text("جدول کانفیگ‌ها در دیتابیس وجود ندارد! 😓")
                return
            # شمارش کل کانفیگ‌ها
            c.execute("SELECT COUNT(*) FROM configs")
            result = c.fetchone()
            total_configs = result[0] if result else 0
            # شمارش کانفیگ‌ها بر اساس پروتکل
            c.execute("SELECT protocol, COUNT(*) FROM configs GROUP BY protocol")
            protocols = c.fetchall() or []
            # شمارش پروکسی‌ها
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxies'")
            total_proxies = 0
            if c.fetchone():
                c.execute("SELECT COUNT(*) FROM proxies")
                result = c.fetchone()
                total_proxies = result[0] if result else 0
            # ساخت پیام آمار
            message = f"📊 آمار کانفیگ‌ها و پروکسی‌ها:\n\nتعداد کل کانفیگ‌ها: {total_configs}\n"
            for protocol, count in protocols:
                message += f"{protocol}: {count} کانفیگ\n"
            message += f"\nتعداد پروکسی‌های HTTP: {total_proxies}"
            await update.message.reply_text(message)
            logger.info("آمار با موفقیت ارسال شد")
    except sqlite3.Error as e:
        logger.error(f"خطا در دریافت آمار از دیتابیس: {e}")
        await update.message.reply_text("خطایی در دریافت آمار رخ داد! 😓")
    except Exception as e:
        logger.error(f"خطا در تابع stats: {e}")
        await update.message.reply_text("خطایی رخ داد! 😓 لطفاً دوباره امتحان کن.")

async def protocol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت انتخاب پروتکل و دستورات منوی اصلی"""
    file_path = None
    try:
        if not is_admin(update.effective_user.id):
            await update.callback_query.answer("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
            return

        query = update.callback_query
        await query.answer()
        command = query.data

        if command == "cmd_protocol":
            protocols = ["vmess", "vless", "hysteria2"]
            keyboard = [[InlineKeyboardButton(protocol, callback_data=f"protocol_{protocol}") for protocol in protocols]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("یه پروتکل انتخاب کن:", reply_markup=reply_markup)
            return
        elif command == "cmd_update":
            config = load_config()
            db_path = config["database"]["path"]
            await query.message.reply_text("در حال به‌روزرسانی کانفیگ‌ها... ⏳")
            await collect_v2ray_links(db_path)
            await query.message.reply_text("کانفیگ‌ها با موفقیت به‌روزرسانی شدن! 🎉")
            return
        elif command == "cmd_proxies":
            file_path = "cache/proxies.txt"
            if not os.path.exists(file_path):
                await query.message.reply_text("هیچ پروکسی‌ای پیدا نشد! 😕\nلطفاً ابتدا پروکسی‌ها را به‌روزرسانی کنید.")
                return
            with open(file_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    caption=f"لیست پروکسی‌های HTTP 🌐"
                )
            return
        elif command == "cmd_update_proxies":
            await query.message.reply_text("در حال به‌روزرسانی پروکسی‌ها... ⏳")
            config = load_config()
            db_path = config["database"]["path"]
            file_path, count = collect_proxies(db_path)
            await query.message.reply_text(f"پروکسی‌ها با موفقیت به‌روزرسانی شدند! {count} پروکسی جمع‌آوری شد. 🎉")
            return
        elif command == "cmd_test_proxies":
            config = load_config()
            db_path = config["database"]["path"]
            await query.message.reply_text("در حال تست پروکسی‌ها... ⏳")
            results = await test_all_proxies(db_path, use_file=True)
            valid_count = len([r for r in results if r["status"] == "active"])
            file_path = "cache/valid_proxies.txt"
            if valid_count > 0 and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await query.message.reply_document(
                        document=f,
                        caption=f"تست پروکسی‌ها کامل شد! {valid_count} پروکسی معتبر یافت شد. 🧪"
                    )
            else:
                await query.message.reply_text("هیچ پروکسی معتبری یافت نشد! 😕")
            return
        elif command == "cmd_stats":
            config = load_config()
            db_path = config["database"]["path"]
            with get_db_connection(db_path) as conn:
                c = conn.cursor()
                # بررسی وجود جدول configs
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configs'")
                if not c.fetchone():
                    logger.error("جدول configs در دیتابیس وجود ندارد!")
                    await query.message.reply_text("جدول کانفیگ‌ها در دیتابیس وجود ندارد! 😓")
                    return
                # شمارش کل کانفیگ‌ها
                c.execute("SELECT COUNT(*) FROM configs")
                result = c.fetchone()
                total_configs = result[0] if result else 0
                # شمارش کانفیگ‌ها بر اساس پروتکل
                c.execute("SELECT protocol, COUNT(*) FROM configs GROUP BY protocol")
                protocols = c.fetchall() or []
                # شمارش پروکسی‌ها
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxies'")
                total_proxies = 0
                if c.fetchone():
                    c.execute("SELECT COUNT(*) FROM proxies")
                    result = c.fetchone()
                    total_proxies = result[0] if result else 0
                # ساخت پیام آمار
                message = f"📊 آمار کانفیگ‌ها و پروکسی‌ها:\n\nتعداد کل کانفیگ‌ها: {total_configs}\n"
                for protocol, count in protocols:
                    message += f"{protocol}: {count} کانفیگ\n"
                message += f"\nتعداد پروکسی‌های HTTP: {total_proxies}"
                await query.message.reply_text(message)
                logger.info("آمار با موفقیت ارسال شد")
            return
        elif command == "cmd_help":
            help_text = (
                "📋 راهنمای دستورات ربات:\n\n"
                "/start - شروع کار با ربات و نمایش منوی اصلی\n"
                "/help - نمایش این راهنما\n"
                "/protocol - انتخاب پروتکل و دریافت کانفیگ‌ها\n"
                "/stats - نمایش آمار کانفیگ‌ها و پروکسی‌ها\n"
                "/clear - پاک کردن همه کانفیگ‌ها و پروکسی‌ها (نیاز به تأیید)\n\n"
                "⚠️ از منوی گرافیکی برای دریافت، به‌روزرسانی یا تست پروکسی‌ها استفاده کن!\n"
                "⚠️ فقط ادمین‌ها می‌تونن از این دستورات استفاده کنن!"
            )
            await query.message.reply_text(help_text)
            return
        elif command == "cmd_clear":
            keyboard = [
                [InlineKeyboardButton("بله، پاک کن 🗑️", callback_data="confirm_clear")],
                [InlineKeyboardButton("خیر، لغو کن ❌", callback_data="cancel_clear")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "مطمئنی می‌خوای همه کانفیگ‌ها و پروکسی‌ها رو پاک کنی؟ این کار قابل بازگشت نیست! 😳",
                reply_markup=reply_markup
            )
            return
        elif command == "confirm_clear":
            config = load_config()
            db_path = config["database"]["path"]
            clear_all_configs(db_path)
            await query.message.reply_text("همه کانفیگ‌ها و پروکسی‌ها با موفقیت پاک شدن! 🗑️")
            return
        elif command == "cancel_clear":
            await query.message.reply_text("عملیات پاکسازی لغو شد! 😊")
            return

        # مدیریت انتخاب پروتکل
        protocol = command.replace("protocol_", "")
        config = load_config()
        db_path = config["database"]["path"]
        max_configs = config["limits"]["max_configs_per_protocol"]

        configs = get_configs_by_protocol(db_path, protocol, max_configs)
        if not configs:
            await query.message.reply_text(
                f"هیچ کانفیگی برای پروتکل {protocol} پیدا نشد! 😕\nبا /update کانفیگ‌ها رو به‌روزرسانی کن."
            )
            return

        file_path = f"cache/{protocol}_configs.txt"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for config in configs:
                f.write(config + "\n")

        with open(file_path, "rb") as f:
            await query.message.reply_document(
                document=f,
                caption=f"کانفیگ‌های پروتکل {protocol} ({len(configs)} تا) 🚀"
            )
    except Exception as e:
        logger.error(f"خطا در protocol_callback: {e}")
        await query.message.reply_text("خطایی رخ داد! 😓 لطفاً دوباره امتحان کن.")
    finally:
        if file_path and file_path.endswith("_configs.txt") and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"فایل موقت {file_path} حذف شد.")

async def update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور به‌روزرسانی دستی کانفیگ‌ها"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    try:
        config = load_config()
        db_path = config["database"]["path"]
        await update.message.reply_text("در حال به‌روزرسانی کانفیگ‌ها... ⏳")
        await collect_v2ray_links(db_path)
        await update.message.reply_text("کانفیگ‌ها با موفقیت به‌روزرسانی شدن! 🎉")
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی کانفیگ‌ها: {e}")
        await update.message.reply_text("خطایی در به‌روزرسانی رخ داد! 😓")

async def update_configs(context: ContextTypes.DEFAULT_TYPE):
    """تابع دوره‌ای برای به‌روزرسانی و پاکسازی کانفیگ‌ها و پروکسی‌ها"""
    try:
        config = load_config()
        db_path = config["database"]["path"]
        cleanup_old_configs(db_path, config["schedule"]["cleanup_interval"])
        await collect_v2ray_links(db_path)
        file_path, _ = collect_proxies(db_path)
        logger.info("جمع‌آوری و پاکسازی لینک‌ها و پروکسی‌ها انجام شد.")
    except Exception as e:
        logger.error(f"خطا در update_configs: {e}")

def main():
    """نقطه ورود اصلی ربات"""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN در فایل .env تنظیم نشده است!")
        sys.exit(1)

    try:
        config = load_config()
        db_path = config["database"]["path"]
        init_db(db_path)

        app = Application.builder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("protocol", protocol))
        app.add_handler(CommandHandler("update", update))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(CommandHandler("clear", clear))
        app.add_handler(CallbackQueryHandler(protocol_callback, pattern="^(protocol_|cmd_|confirm_clear|cancel_clear)"))

        app.job_queue.run_repeating(
            update_configs,
            interval=config["schedule"]["update_interval"],
            first=0
        )

        logger.info("ربات شروع به کار کرد...")
        app.run_polling()
    except Exception as e:
        logger.error(f"خطا در اجرای اصلی ربات: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()