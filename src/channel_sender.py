import asyncio
import logging
import re
from telegram import Bot
from src.db import get_configs_by_protocol, delete_configs
from src.utils import load_config

# تنظیم لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/channel_sender.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def modify_config(config: str) -> str:
    """تغییر کانفیگ: حذف بخش بعد از # و جایگزینی با @Vless_sub_free"""
    try:
        # حذف بخش بعد از # و جایگزینی
        modified = re.sub(r'#.*$', '#@Vless_sub_free', config)
        # قرار دادن کانفیگ در قالب ```
        formatted = f"```\n{modified}\n```\n\n#V2ray #Vless #Vmess #Config #Vpn\n\n@Vless_sub_free"
        return formatted
    except Exception as e:
        logger.error(f"خطا در تغییر کانفیگ {config[:50]}...: {e}")
        return config

async def send_configs_to_channel(bot: Bot, db_path: str, protocols: list = ["vless", "vmess"]):
    """ارسال کانفیگ‌ها به کانال تلگرامی و حذف آنها از دیتابیس"""
    try:
        config = load_config()
        channel_id = config["telegram"].get("channel_id")
        if not channel_id:
            logger.error("شناسه کانال در config.yaml تنظیم نشده است!")
            return

        configs_per_protocol = config["schedule"].get("configs_per_send", 10)
        sent_configs = []

        for protocol in protocols:
            configs = get_configs_by_protocol(db_path, protocol, configs_per_protocol)
            if not configs:
                logger.info(f"هیچ کانفیگی برای پروتکل {protocol} برای ارسال به کانال یافت نشد")
                continue

            for config in configs:
                modified_config = modify_config(config)
                await bot.send_message(
                    chat_id=channel_id,
                    text=modified_config,
                    parse_mode="Markdown"
                )
                sent_configs.append(config)
                logger.info(f"کانفیگ {config[:50]}... به کانال {channel_id} ارسال شد")
                # تاخیر 1 ثانیه برای جلوگیری از محدودیت‌های تلگرام
                await asyncio.sleep(1)

        # حذف کانفیگ‌های ارسالی از دیتابیس
        if sent_configs:
            deleted_count = delete_configs(db_path, sent_configs)
            logger.info(f"{deleted_count} کانفیگ ارسالی از دیتابیس حذف شد")
    except Exception as e:
        logger.error(f"خطا در ارسال کانفیگ‌ها به کانال: {e}")