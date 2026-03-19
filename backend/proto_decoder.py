"""
proto_decoder.py – Upstox Market Data Feed V3 Protobuf Decoder

SETUP (one-time):
  1. Download the proto file from Upstox developer portal:
     https://assets.upstox.com/feed/market-data-feed/v3/MarketDataFeed.proto

  2. Install protoc + Python plugin:
     pip install grpcio-tools

  3. Generate Python code:
     python -m grpc_tools.protoc -I. --python_out=. MarketDataFeed.proto

  4. The generated file will be: MarketDataFeed_pb2.py
     This decoder will automatically use it.

Until the proto file is compiled, we provide a JSON fallback decoder.
"""

import json
import struct
from typing import Optional, Dict, Any

# Try to import generated protobuf classes
try:
    import MarketDataFeed_pb2 as pb
    PROTO_AVAILABLE = True
    print("[Proto] Protobuf classes loaded ✓")
except ImportError:
    PROTO_AVAILABLE = False
    print("[Proto] Proto classes not found – using JSON fallback decoder")


def decode_market_feed(raw: bytes) -> Optional[Dict[str, Any]]:
    """
    Decode raw bytes from Upstox V3 WebSocket.
    Returns a normalized dict or None on failure.
    """
    if PROTO_AVAILABLE:
        return _decode_proto(raw)
    else:
        return _decode_json_fallback(raw)


def _decode_proto(raw: bytes) -> Optional[Dict[str, Any]]:
    """Full protobuf decode using generated classes."""
    try:
        feed = pb.FeedResponse()
        feed.ParseFromString(raw)

        result = {"type": "live_feed", "feeds": {}}

        if feed.HasField("marketInfo"):
            result["type"] = "market_info"
            result["marketInfo"] = {
                "segmentStatus": dict(feed.marketInfo.segmentStatus)
            }
            return result

        for key, val in feed.feeds.items():
            entry = {}

            if val.HasField("ltpc"):
                entry["ltpc"] = {
                    "ltp": val.ltpc.ltp,
                    "ltt": str(val.ltpc.ltt),
                    "ltq": str(val.ltpc.ltq),
                    "cp":  val.ltpc.cp,
                }

            if val.HasField("marketFF"):
                mff = val.marketFF
                entry["marketOHLC"] = {
                    "open":  mff.marketOHLC.open,
                    "high":  mff.marketOHLC.high,
                    "low":   mff.marketOHLC.low,
                    "close": mff.marketOHLC.close,
                }
                entry["eFeedDetails"] = {
                    "atp":        mff.eFeedDetails.atp,
                    "cp":         mff.eFeedDetails.cp,
                    "vtt":        mff.eFeedDetails.vtt,
                    "tbq":        mff.eFeedDetails.tbq,
                    "tsq":        mff.eFeedDetails.tsq,
                    "uc":         mff.eFeedDetails.uc,
                    "lc":         mff.eFeedDetails.lc,
                    "52WeekHigh": mff.eFeedDetails.high52Week,
                    "52WeekLow":  mff.eFeedDetails.low52Week,
                }

            if val.HasField("optionGreeks"):
                og = val.optionGreeks
                entry["optionGreeks"] = {
                    "delta": og.delta,
                    "theta": og.theta,
                    "gamma": og.gamma,
                    "vega":  og.vega,
                    "iv":    og.iv,
                }

            result["feeds"][key] = entry

        result["currentTs"] = str(feed.currentTs)
        return result

    except Exception as e:
        print(f"[Proto] Decode error: {e}")
        return None


def _decode_json_fallback(raw: bytes) -> Optional[Dict[str, Any]]:
    """JSON fallback – works for text frames & development."""
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def normalize_ltp(feed_entry: dict) -> float:
    """Extract LTP from a feed entry regardless of mode."""
    if "ltpc" in feed_entry:
        return feed_entry["ltpc"].get("ltp", 0.0)
    return 0.0


def normalize_change_pct(feed_entry: dict) -> float:
    """Calculate % change from LTP and close price."""
    ltpc = feed_entry.get("ltpc", {})
    ltp = ltpc.get("ltp", 0.0)
    cp  = ltpc.get("cp", 0.0)
    if cp and cp != 0:
        return round(((ltp - cp) / cp) * 100, 2)
    return 0.0
