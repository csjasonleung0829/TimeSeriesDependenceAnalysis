import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan pairs of I(1) assets and identify cointegrated spreads."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing CSV files with price data.",
    )
    parser.add_argument(
        "--candidates-file",
        default="output/i1_candidates_adf_pp.csv",
        help="CSV file with a 'symbol' column listing I(1) candidates.",
    )
    parser.add_argument(
        "--column",
        default="close",
        help="Price column to use (default: close).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level for ADF test on the spread (default: 0.05).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=100,
        help="Minimum number of overlapping observations required per pair.",
    )
    parser.add_argument(
        "--output",
        default="output/cointegrated_pairs.csv",
        help="Output CSV file for cointegrated pairs.",
    )
    return parser.parse_args()


def build_symbol_file_map(data_dir: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for path in data_dir.glob("*.csv"):
        stem = path.stem
        parts = stem.split("_")
        if len(parts) < 2:
            continue
        symbol = parts[0]
        timeframe = parts[1]
        if timeframe != "D1":
            continue
        if symbol not in mapping:
            mapping[symbol] = path
        else:
            existing = mapping[symbol]
            if path.stat().st_mtime > existing.stat().st_mtime:
                mapping[symbol] = path
    return mapping


def load_price_series(path: Path, column: str) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["time"])
    if column not in df.columns:
        raise ValueError(f"Column {column} not found in file {path}")
    series = df.set_index("time")[column].astype(float).dropna()
    series = np.log(series)
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    return series


def adf_pvalue(series: pd.Series) -> float:
    result = adfuller(series, autolag="AIC")
    return float(result[1])


def estimate_beta_alpha(y: pd.Series, x: pd.Series) -> tuple[float, float]:
    yv = y.values
    xv = x.values
    X = np.column_stack([np.ones(len(xv)), xv])
    params, _, _, _ = np.linalg.lstsq(X, yv, rcond=None)
    alpha = float(params[0])
    beta = float(params[1])
    return beta, alpha


def estimate_half_life(spread: pd.Series) -> float:
    z = spread - spread.mean()
    z_lag = z.shift(1).dropna()
    z_now = z.iloc[1:]
    if len(z_lag) != len(z_now):
        z_now = z_now.loc[z_lag.index]
    xv = z_lag.values
    yv = z_now.values
    if len(xv) < 2 or np.allclose(xv, 0.0):
        return np.nan
    phi = float((xv @ yv) / (xv @ xv))
    if phi <= 0 or phi >= 1:
        return np.nan
    return float(-np.log(2) / np.log(phi))


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        raise NotADirectoryError(f"Data directory not found: {data_dir}")

    candidates_path = Path(args.candidates_file)
    if not candidates_path.is_file():
        raise FileNotFoundError(f"Candidates file not found: {candidates_path}")

    df_candidates = pd.read_csv(candidates_path)
    if "symbol" not in df_candidates.columns:
        raise ValueError("Candidates file must contain a 'symbol' column.")
    symbols = df_candidates["symbol"].astype(str).tolist()

    symbol_file = build_symbol_file_map(data_dir)
    available_symbols = [s for s in symbols if s in symbol_file]
    if not available_symbols:
        raise ValueError("No candidate symbols have matching D1 CSV files.")

    series_map: dict[str, pd.Series] = {}
    for s in available_symbols:
        path = symbol_file[s]
        try:
            series_map[s] = load_price_series(path, args.column)
        except Exception:
            continue

    valid_symbols = [s for s in available_symbols if s in series_map]
    if len(valid_symbols) < 2:
        raise ValueError("Fewer than two valid symbols after loading series.")

    results: list[dict[str, object]] = []

    total_pairs = len(valid_symbols) * (len(valid_symbols) - 1) // 2
    pairs_iter = itertools.combinations(valid_symbols, 2)
    if tqdm is not None:
        pairs_iter = tqdm(pairs_iter, total=total_pairs, desc="Scanning pairs")

    for asset1, asset2 in pairs_iter:
        s1 = series_map[asset1]
        s2 = series_map[asset2]
        joined = pd.concat([s1, s2], axis=1, join="inner").dropna()
        if joined.shape[0] < args.min_length:
            continue
        y = joined.iloc[:, 0]
        x = joined.iloc[:, 1]
        try:
            beta, alpha = estimate_beta_alpha(y, x)
            spread = y - (alpha + beta * x)
            p_spread = adf_pvalue(spread)
        except Exception:
            continue
        if p_spread < args.alpha:
            half_life = estimate_half_life(spread)
            results.append(
                {
                    "asset1": asset1,
                    "asset2": asset2,
                    "beta": beta,
                    "alpha": alpha,
                    "adf_p_spread": p_spread,
                    "n_obs": joined.shape[0],
                    "half_life": half_life,
                }
            )

    if not results:
        print("No cointegrated pairs found at the specified significance level.")
        return

    df_out = pd.DataFrame(results)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(output_path, index=False)
    print(f"Saved {len(df_out)} cointegrated pairs to {output_path}")


if __name__ == "__main__":
    main()
