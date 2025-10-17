# src/utils.py
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
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_channels(file_path: str = "channels.yaml") -> List[str]:
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)
        return [c for c in data.get("channels", []) if isinstance(c, str) and not c.startswith("t.me/")]

def load_proxy_sources() -> List[str]:
    return load_config()["proxy"]["sources"]

def is_valid_v2ray_link(link: str) -> bool:
    try:
        if link.startswith("vmess://"):
            decoded = base64.b64decode(link[8] + '=' * (-len(link[8]) % 4)).decode('utf-8')
            config_data = json.loads(decoded)
            VmessConfig(**config_data)
            return True
        elif link.startswith("vless://"):
            VlessConfig.from_uri(link)
            return True
        elif link.startswith("hysteria2://"):
            Hysteria2Config.from_uri(link)
            return True
        return False
    except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as e:
        logger.error(f"نامعتبر: {e}")
        return False

def parse_v2ray_protocol(link: str) -> Optional[str]:
    if link.startswith("vmess://"): return "vmess"
    if link.startswith("vless://"): return "vless"
    if link.startswith("hysteria2://"): return "hysteria2"
    return None

def modify_config_name(config: str, new_name: str) -> str:
    if "#" in config:
        return config.split("#")[0] + f"#{new_name}"
    return config + f"#{new_name}"