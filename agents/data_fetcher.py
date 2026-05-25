import time
import requests
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PricePoint:
    timestamp: float
    price: float
    source: str
    unit: str
    yesterday_price: Optional[float] = None
    change_pct: Optional[float] = None
    change_amt: Optional[float] = None
    source_timestamp_ms: Optional[int] = None


class DataFetcher:
    def __init__(self, apis_config: Dict[str, Dict]):
        self.apis = apis_config

    def fetch_price(self, api_name: str) -> Optional[PricePoint]:
        api_info = self.apis.get(api_name)
        if not api_info:
            return None
        try:
            resp = requests.get(api_info["url"], timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return self._parse(api_name, api_info, data)
        except Exception:
            return None

    def _parse(self, api_name: str, api_info: Dict, raw: Dict) -> PricePoint:
        parser_type = api_info.get("parser", "zheshang")
        if parser_type == "zheshang":
            return self._parse_zheshang(api_name, api_info, raw)
        raise ValueError(f"Unknown parser: {parser_type}")

    def _parse_zheshang(self, api_name: str, api_info: Dict, raw: Dict) -> PricePoint:
        datas = raw["resultData"]["datas"]
        price = float(datas["price"])
        yesterday = float(datas.get("yesterdayPrice", 0)) or None
        change_pct_str = datas.get("upAndDownRate", "0%")
        change_pct = float(change_pct_str.replace("%", "").replace("+", ""))
        change_amt_str = datas.get("upAndDownAmt", "0")
        change_amt = float(change_amt_str.replace("+", ""))
        timestamp_ms = int(datas.get("time", 0))
        return PricePoint(
            timestamp=time.time(),
            price=price,
            source=api_name,
            unit=api_info["unit"],
            yesterday_price=yesterday,
            change_pct=change_pct,
            change_amt=change_amt,
            source_timestamp_ms=timestamp_ms,
        )
