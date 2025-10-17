# src/models.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from urllib.parse import unquote, urlparse, parse_qs
import json
import base64

class BaseConfig(BaseModel):
    model_config = {'str_strip_whitespace': True}
    protocol: str
    host: str
    port: int
    uuid: str
    remarks: str = "N/A"
    network: str = 'tcp'
    security: str = 'none'
    path: Optional[str] = None
    sni: Optional[str] = None
    fingerprint: Optional[str] = None
    country: Optional[str] = Field("XX", exclude=True)
    source_type: str = Field("unknown", exclude=True)
    ping: Optional[int] = Field(None, exclude=True)
    asn_org: Optional[str] = Field(None, exclude=True)

    def get_deduplication_key(self) -> str:
        return f"{self.protocol}:{self.host}:{self.port}:{self.uuid}"

    def to_uri(self) -> str:
        raise NotImplementedError

class VmessConfig(BaseConfig):
    protocol: str = 'vmess'
    source_type: str = 'vmess'
    ps: str
    add: str
    v: Any = "2"
    aid: int = 0
    scy: str = 'auto'
    net: str
    type: str = 'none'
    tls: str = ''

    @model_validator(mode='before')
    def map_fields(cls, values):
        values['remarks'] = values.get('ps', 'N/A')
        values['host'] = values.get('add', '')
        values['uuid'] = values.get('id', '')
        values['network'] = values.get('net', 'tcp')
        values['security'] = values.get('tls') or 'none'
        values['v'] = str(values.get('v', '2'))
        return values

    def to_uri(self) -> str:
        config = {
            "v": self.v,
            "ps": self.remarks,
            "add": self.host,
            "port": self.port,
            "id": self.uuid,
            "aid": self.aid,
            "scy": self.scy,
            "net": self.network,
            "type": self.type,
            "tls": self.security
        }
        encoded = base64.b64encode(json.dumps(config).encode('utf-8')).decode('utf-8')
        return f"vmess://{encoded}"

class VlessConfig(BaseConfig):
    protocol: str = 'vless'
    flow: Optional[str] = None
    pbk: Optional[str] = None
    sid: Optional[str] = None

    @classmethod
    def from_uri(cls, uri: str):
        parsed = urlparse(uri)
        if parsed.scheme != 'vless':
            raise ValueError("Invalid VLESS URI")

        uuid_host = parsed.netloc.split('@')
        if len(uuid_host) != 2:
            raise ValueError("Invalid VLESS URI format")

        uuid, host_port = uuid_host
        host, port = host_port.split(':') if ':' in host_port else (host_port, 443)

        query = parse_qs(parsed.query)
        config = {
            'uuid': uuid,
            'host': host,
            'port': int(port),
            'remarks': unquote(parsed.fragment) if parsed.fragment else 'N/A',
            'network': query.get('type', ['tcp'])[0],
            'security': query.get('security', ['none'])[0],
            'path': query.get('path', [None])[0],
            'sni': query.get('sni', [None])[0],
            'fingerprint': query.get('fp', [None])[0],
            'flow': query.get('flow', [None])[0],
            'pbk': query.get('pbk', [None])[0],
            'sid': query.get('sid', [None])[0],
        }
        return cls(**config)

    def to_uri(self) -> str:
        params = {
            'type': self.network,
            'security': self.security,
            'path': self.path,
            'sni': self.sni,
            'fp': self.fingerprint,
            'flow': self.flow,
            'pbk': self.pbk,
            'sid': self.sid
        }
        query_string = '&'.join([f"{k}={v}" for k, v in params.items() if v is not None and v != ""])
        remarks_encoded = f"#{unquote(self.remarks)}"
        return f"vless://{self.uuid}@{self.host}:{self.port}?{query_string}{remarks_encoded}"

class Hysteria2Config(BaseConfig):
    protocol: str = 'hysteria2'
    insecure: Optional[int] = None
    obfs: Optional[str] = None
    obfs_password: Optional[str] = Field(None, alias='obfs-password')

    @classmethod
    def from_uri(cls, uri: str):
        parsed = urlparse(uri)
        if parsed.scheme != 'hysteria2':
            raise ValueError("Invalid Hysteria2 URI")

        uuid_host = parsed.netloc.split('@')
        if len(uuid_host) != 2:
            raise ValueError("Invalid Hysteria2 URI format")

        uuid, host_port = uuid_host
        host, port = host_port.split(':') if ':' in host_port else (host_port, 443)

        query = parse_qs(parsed.query)
        config = {
            'uuid': uuid,
            'host': host,
            'port': int(port),
            'remarks': unquote(parsed.fragment) if parsed.fragment else 'N/A',
            'network': query.get('type', ['tcp'])[0],
            'security': query.get('security', ['none'])[0],
            'sni': query.get('sni', [None])[0],
            'insecure': int(query.get('insecure', [0])[0]) if query.get('insecure') else None,
            'obfs': query.get('obfs', [None])[0],
            'obfs-password': query.get('obfs-password', [None])[0],
        }
        return cls(**config)

    def to_uri(self) -> str:
        params = {
            'sni': self.sni,
            'insecure': self.insecure,
            'obfs': self.obfs,
            'obfs-password': self.obfs_password
        }
        query_string = '&'.join([f"{k}={v}" for k, v in params.items() if v is not None])
        remarks_encoded = f"#{unquote(self.remarks)}"
        return f"hysteria2://{self.uuid}@{self.host}:{self.port}?{query_string}{remarks_encoded}"