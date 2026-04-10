import argparse
import os
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch OHLC data from MT5 and store it in a local CSV file."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="Trading symbol, for example: EURUSD, XAUUSD, or 'all' for all symbols.",
    )
    parser.add_argument(
        "--timeframe",
        required=True,
        choices=list(TIMEFRAME_MAP.keys()),
        help="MT5 timeframe, for example: M1, M5, H1, D1.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date in the format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End date in the format YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory where the CSV file will be stored.",
    )
    parser.add_argument(
        "--filename",
        default="",
        help="Optional custom filename for the CSV file.",
    )
    return parser.parse_args()


def ensure_mt5_initialized() -> None:
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize() failed, error code: {mt5.last_error()}")


def ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Symbol {symbol} not found in MT5.")
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to select symbol {symbol}.")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def fetch_ohlc(symbol: str, timeframe_key: str, start: datetime, end: datetime) -> pd.DataFrame:
    timeframe = TIMEFRAME_MAP[timeframe_key]
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is None or len(rates) == 0:
        raise RuntimeError("No rates returned from MT5 for the specified parameters.")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df[
        [
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread",
            "real_volume",
        ]
    ]
    return df


def load_existing_data(path: str) -> Optional[pd.DataFrame]:
    if not os.path.isfile(path):
        return None
    df = pd.read_csv(path, parse_dates=["time"])
    if "time" not in df.columns:
        return None
    return df


def build_output_path(
    output_dir: str,
    symbol: str,
    timeframe_key: str,
    start: datetime,
    end: datetime,
    filename: str,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    if filename:
        return os.path.join(output_dir, filename)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    safe_symbol = symbol.replace("/", "").replace("\\", "").replace(" ", "")
    return os.path.join(
        output_dir, f"{safe_symbol}_{timeframe_key}_{start_str}_{end_str}.csv"
    )


def main() -> None:
    args = parse_args()
    ensure_mt5_initialized()
    try:
        start = parse_date(args.start)
        end = parse_date(args.end)
        if args.symbol.lower() == "all":
            symbols = mt5.symbols_get()
            for info in symbols:
                name = info.name
                try:
                    ensure_symbol(name)
                    output_path = build_output_path(
                        args.output_dir, name, args.timeframe, start, end, ""
                    )
                    existing = load_existing_data(output_path)
                    if existing is not None and not existing.empty:
                        last_time = existing["time"].max().to_pydatetime()
                        effective_start = max(start, last_time)
                        if effective_start >= end:
                            print(f"{name}: existing data already covers up to {end}")
                            continue
                    else:
                        effective_start = start
                    data = fetch_ohlc(name, args.timeframe, effective_start, end)
                    if existing is not None and not existing.empty:
                        combined = pd.concat([existing, data], ignore_index=True)
                        combined = combined.drop_duplicates(subset="time")
                        combined = combined.sort_values("time")
                    else:
                        combined = data
                    combined.to_csv(output_path, index=False)
                    print(f"Saved {len(combined)} rows for {name} to {output_path}")
                except Exception as exc:
                    print(f"Skipping {name} due to error: {exc}")
        else:
            ensure_symbol(args.symbol)
            output_path = build_output_path(
                args.output_dir, args.symbol, args.timeframe, start, end, args.filename
            )
            existing = load_existing_data(output_path)
            if existing is not None and not existing.empty:
                last_time = existing["time"].max().to_pydatetime()
                effective_start = max(start, last_time)
                if effective_start >= end:
                    print(f"{args.symbol}: existing data already covers up to {end}")
                    return
            else:
                effective_start = start
            data = fetch_ohlc(args.symbol, args.timeframe, effective_start, end)
            if existing is not None and not existing.empty:
                combined = pd.concat([existing, data], ignore_index=True)
                combined = combined.drop_duplicates(subset="time")
                combined = combined.sort_values("time")
            else:
                combined = data
            combined.to_csv(output_path, index=False)
            print(f"Saved {len(combined)} rows to {output_path}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()

