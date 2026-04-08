import re
import csv
from datetime import datetime

# Input and output file names
input_file = "binanceexecutor.log"
output_file = "order_events.csv"

# Regex pattern to extract OrderEvent data
pattern = re.compile(
    r"^(?P<log_time>[\d\-\s:]+)\s+-\s+BinanceExecutor\s+-\s+INFO\s+-\s+OrderEvent"
    r"\(timestamp=datetime\.datetime\((?P<event_time>[\d,\s]+)\),\s+source='(?P<source>[^']+)',\s+"
    r"order_id=(?P<order_id>\d+),\s+instrument='(?P<instrument>[^']+)',\s+side='(?P<side>[^']+)',\s+"
    r"price=(?P<price>[\d.]+),\s+strategy='(?P<strategy>[^']+)',\s+type='(?P<type>[^']+)',\s+"
    r"candle=CandleGenerated\(timestamp=datetime\.datetime\((?P<candle_time>[\d,\s]+)\),\s+source='CandleMaker',\s+symbol='(?P<symbol>[^']+)',\s+timeframe='(?P<timeframe>[^']+)',\s+"
    r"open=(?P<open>[\d.]+),\s+high=(?P<high>[\d.]+),\s+low=(?P<low>[\d.]+),\s+close=(?P<close>[\d.]+),\s+volume=(?P<volume>[\d.Ee+-]+),\s+vwap=(?P<vwap>[\d.Ee+-]+),\s+is_complete=(?P<complete>\w+)\),\s+meta_info=(?P<meta>.*)$"
)

def parse_datetime(dt_str):
    """Convert datetime.datetime(YYYY, M, D, H, M, S, µS) to readable string"""
    nums = [int(x.strip()) for x in dt_str.split(',')]
    while len(nums) < 7:
        nums.append(0)
    return datetime(*nums).strftime("%Y-%m-%d %H:%M:%S")

rows = []

with open(input_file, "r") as f:
    for line in f:
        line = line.strip()
        m = pattern.match(line)
        if not m:
            continue

        d = m.groupdict()
        row = {
            "log_time": d["log_time"],
            "order_id": d["order_id"],
            "source": d["source"],
            "instrument": d["instrument"],
            "side": d["side"],
            "price": d["price"],
            "strategy": d["strategy"],
            "type": d["type"],
            "event_time": parse_datetime(d["event_time"]),
            "candle_time": parse_datetime(d["candle_time"]),
            "candle_open": d["open"],
            "candle_high": d["high"],
            "candle_low": d["low"],
            "candle_close": d["close"],
            "candle_volume": d["volume"],
            "candle_vwap": d["vwap"],
            "candle_complete": d["complete"],
            "meta_info": d["meta"].strip()
        }
        rows.append(row)

# Write to CSV
if rows:
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

print(f"✅ Parsed {len(rows)} OrderEvent records to {output_file}")
