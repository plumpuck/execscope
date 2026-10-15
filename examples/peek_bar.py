"""Print a pandas row next to the Bar object BarDataWrangler turns it into.

Adapted from step 4 of NautilusTrader's official example `example_01_load_bars_from_custom_csv`
(LGPL-3.0, https://github.com/nautechsystems/nautilus_trader). Run it inside that example's folder;
the CSV file and `strategy.py` belong to NautilusTrader and are not copied into this repo.
"""
import pandas as pd
from nautilus_trader.model.data import BarType
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

inst = TestInstrumentProvider.eurusd_future(expiry_year=2024, expiry_month=3, venue_name="XCME")

df = pd.read_csv("6EH4.XCME_1min_bars.csv", sep=";", decimal=".", header=0, index_col=False)
df = df.reindex(columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], format="%Y-%m-%d %H:%M:%S")
df = df.rename(columns={"timestamp_utc": "timestamp"}).set_index("timestamp")

print("=== first row of the table ===")
print(df.head(1))

bar_type = BarType.from_str(f"{inst.id}-1-MINUTE-LAST-EXTERNAL")
bars = BarDataWrangler(bar_type, inst).process(df)

print("=== first Bar after conversion ===")
print(bars[0])
print("type:", type(bars[0]))
