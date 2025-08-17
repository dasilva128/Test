import json
import base64
import urllib.parse
import logging
import yaml
from typing import List, Optional
from pydantic import ValidationError
from .models import VmessConfig, VlessConfig, Hysteria2Config

logger = logging.getLogger(__name__)

def load_config(file_path: str = "config.yaml") -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"فایل تنظیمات {file_path} با موفقیت لود شد")
        return config
    except FileNotFoundError as e:
        logger.error(f"فایل تنظیمات {file_path} پیدا نشد: {e}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"خطا در پارس فایل تنظیمات {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"خطای ناشناخته در لود کردن تنظیمات: {e}")
        raise

def load_channels(file_path: str = "channels.yaml") -> List[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            channels = data.get("channels", [])
        logger.info(f"{len(channels)} کانال از {file_path} لود شد")
        return channels
    except FileNotFoundError:
        logger.warning(f"فایل کانال‌ها {file_path} پیدا نشد. لیست خالی برگردانده می‌شود")
        return []
    except Exception as e:
        logger.error(f"خطا در لود کردن کانال‌ها: {e}")
        return []

def is_valid_v2ray_link(link: str) -> bool:
    try:
        logger.debug(f"در حال بررسی لینک: {link[:50]}...")

        if link.startswith("vmess://"):
            encoded = link[8:]
            decoded = base64.b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8')
            config_data = json.loads(decoded)
            VmessConfig(**config_data)
            return True

        elif link.startswith("vless://"):
            VlessConfig.from_uri(link)
            return True

        elif link.startswith("hysteria2://"):
            Hysteria2Config.from_uri(link)
            return True

        logger.warning(f"پروتکل ناشناخته در لینک: {link[:50]}...")
        return False

    except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error(f"خطای فرمت در لینک {link[:50]}...: {e}")
        return False
    except ValidationError as e:
        logger.error(f"خطای اعتبارسنجی برای لینک {link[:50]}...: {e}")
        return False
    except Exception as e:
        logger.error(f"خطای ناشناخته در بررسی لینک {link[:50]}...: {e}")
        return False

def parse_v2ray_protocol(link: str) -> Optional[str]:
    try:
        logger.debug(f"در حال شناسایی پروتکل لینک: {link[:50]}...")
        if link.startswith("vmess://"):
            return "vmess"
        elif link.startswith("vless://"):
            return "vless"
        elif link.startswith("hysteria2://"):
            return "hysteria2"
        logger.warning(f"پروتکل ناشناخته در لینک: {link[:50]}...")
        return None
    except Exception as e:
        logger.error(f"خطای ناشناخته در شناسایی پروتکل لینک {link[:50]}...: {e}")
        return None