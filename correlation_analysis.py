import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute Pearson correlation between two assets using OHLC CSV files."
    )
    parser.add_argument(
        "--file1",
        required=True,
        help="Path to the first CSV file produced by fetch_ohlc_mt5.py.",
    )
    parser.add_argument(
        "--file2",
        required=True,
        help="Path to the second CSV file produced by fetch_ohlc_mt5.py.",
    )
    parser.add_argument(
        "--column1",
        default="close",
        help="Price column name to use from the first file.",
    )
    parser.add_argument(
        "--column2",
        default="close",
        help="Price column name to use from the second file.",
    )
    parser.add_argument(
        "--mode",
        choices=["price", "return", "logreturn"],
        default="return",
        help="Series transformation: price, return (default), or logreturn.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory with CSV files when using 'all' for file1 or file2.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to save the merged data used for correlation.",
    )
    return parser.parse_args()


def load_series(path: str, column: str) -> pd.Series:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    df = pd.read_csv(p, parse_dates=["time"])
    if "time" not in df.columns:
        raise ValueError(f"File {path} does not contain a 'time' column.")
    if column not in df.columns:
        raise ValueError(f"File {path} does not contain column '{column}'.")
    df = df.set_index("time")
    return df[column]


def transform_series(series: pd.Series, mode: str) -> pd.Series:
    if mode == "price":
        return series.dropna()
    if mode == "return":
        return series.pct_change().dropna()
    if mode == "logreturn":
        return np.log(series).diff().dropna()
    raise ValueError(f"Unsupported mode: {mode}")


def compute_correlation(
    series1: pd.Series, series2: pd.Series
) -> tuple[float, pd.DataFrame]:
    merged = pd.concat([series1, series2], axis=1, join="inner")
    merged.columns = ["asset1", "asset2"]
    if len(merged) == 0:
        raise ValueError("No overlapping timestamps between the two series.")
    value = merged["asset1"].corr(merged["asset2"])
    return value, merged


def asset_name_from_path(path: Path) -> str:
    return path.stem


def pairwise_mode(args: argparse.Namespace) -> None:
    series1_raw = load_series(args.file1, args.column1)
    series2_raw = load_series(args.file2, args.column2)
    series1 = transform_series(series1_raw, args.mode)
    series2 = transform_series(series2_raw, args.mode)
    value, merged = compute_correlation(series1, series2)
    print(f"Pearson correlation: {value:.6f}")
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=True)
        print(f"Merged data saved to {output_path}")


def one_vs_all_mode(args: argparse.Namespace) -> None:
    file1_all = args.file1.lower() == "all"
    file2_all = args.file2.lower() == "all"
    if file1_all == file2_all:
        raise ValueError("one_vs_all_mode requires exactly one of file1 or file2 to be 'all'.")

    if not file1_all:
        anchor_path = Path(args.file1)
        anchor_column = args.column1
        other_column = args.column2
    else:
        anchor_path = Path(args.file2)
        anchor_column = args.column2
        other_column = args.column1

    if not anchor_path.is_file():
        raise FileNotFoundError(f"Anchor file not found: {anchor_path}")

    anchor_raw = load_series(str(anchor_path), anchor_column)
    anchor = transform_series(anchor_raw, args.mode)
    anchor_name = asset_name_from_path(anchor_path)

    directory = anchor_path.parent
    files = sorted(p for p in directory.glob("*.csv") if p != anchor_path)
    if not files:
        raise ValueError(f"No other CSV files found in {directory} to compare with.")

    results = []
    for path in files:
        other_raw = load_series(str(path), other_column)
        other = transform_series(other_raw, args.mode)
        corr, _ = compute_correlation(anchor, other)
        other_name = asset_name_from_path(path)
        results.append({"anchor": anchor_name, "other": other_name, "correlation": corr})
        print(f"{anchor_name} vs {other_name}: {corr:.6f}")

    df = pd.DataFrame(results)
    df = df.sort_values("correlation", ascending=False)
    default_output = Path("output") / "correlation_one_vs_all.csv"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"One-vs-all correlation table saved to {output_path}")


def all_vs_all_mode(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    files = sorted(data_dir.glob("*.csv"))
    if len(files) < 2:
        raise ValueError(f"Need at least two CSV files in {data_dir} for all-vs-all mode.")

    series_map: dict[str, pd.Series] = {}
    for path in files:
        name = asset_name_from_path(path)
        raw = load_series(str(path), args.column1)
        series_map[name] = transform_series(raw, args.mode)

    merged = pd.concat(series_map, axis=1, join="inner")
    if merged.empty:
        raise ValueError("No overlapping timestamps across all series.")

    corr_matrix = merged.corr()
    default_output = Path("output") / "correlation_matrix.csv"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corr_matrix.to_csv(output_path, index=True)
    print(f"All-vs-all correlation matrix saved to {output_path}")


def main() -> None:
    args = parse_args()
    file1_all = args.file1.lower() == "all"
    file2_all = args.file2.lower() == "all"

    if file1_all and file2_all:
        all_vs_all_mode(args)
    elif file1_all or file2_all:
        one_vs_all_mode(args)
    else:
        pairwise_mode(args)


if __name__ == "__main__":
    main()
