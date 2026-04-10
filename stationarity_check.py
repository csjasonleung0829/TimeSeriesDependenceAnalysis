import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


PP_AVAILABLE = True


try:
    from statsmodels.tsa.stattools import phillips_perron as _sm_phillips_perron

    def pp_pvalue(series: pd.Series) -> float:
        stat, pvalue, _, _ = _sm_phillips_perron(series)
        return float(pvalue)

except ImportError:
    try:
        from arch.unitroot import PhillipsPerron as _ArchPhillipsPerron

        def pp_pvalue(series: pd.Series) -> float:
            return float(_ArchPhillipsPerron(series).pvalue)

    except Exception:
        PP_AVAILABLE = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Identify I(1) candidates via ADF and PP tests on price and first difference."
        )
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing CSV files with price data.",
    )
    parser.add_argument(
        "--column",
        default="close",
        help="Column name to use as price (default: close).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level for ADF tests (default: 0.05).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=100,
        help="Minimum number of observations required to run tests (default: 100).",
    )
    return parser.parse_args()


def load_price_series(path: Path, column: str) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["time"])
    if column not in df.columns:
        raise ValueError(f"Column {column} not found in file {path}")
    series = df[column].astype(float).dropna()
    series = np.log(series)
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    return series


def adf_pvalue(series: pd.Series) -> float:
    result = adfuller(series, autolag="AIC")
    return float(result[1])


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        raise NotADirectoryError(f"Data directory not found: {data_dir}")

    results: list[dict[str, object]] = []
    files = sorted(data_dir.glob("*.csv"))
    print(f"Found {len(files)} CSV files in {data_dir}")

    for path in files:
        try:
            series = load_price_series(path, args.column)
        except Exception as exc:
            print(f"Skipping {path.name} due to load error: {exc}")
            continue

        if len(series) < args.min_length:
            print(f"Skipping {path.name}: only {len(series)} observations")
            continue

        symbol = path.stem.split("_")[0]
        try:
            adf_p_level = adf_pvalue(series)
            diff_series = series.diff().dropna()
            adf_p_diff = adf_pvalue(diff_series)
            if PP_AVAILABLE:
                pp_p_level = pp_pvalue(series)
                pp_p_diff = pp_pvalue(diff_series)
            else:
                pp_p_level = np.nan
                pp_p_diff = np.nan
        except Exception as exc:
            print(f"Skipping {path.name} due to unit-root test error: {exc}")
            continue

        adf_i1 = adf_p_level >= args.alpha and adf_p_diff < args.alpha
        pp_i1 = (
            bool(pp_p_level >= args.alpha and pp_p_diff < args.alpha)
            if PP_AVAILABLE and np.isfinite(pp_p_level) and np.isfinite(pp_p_diff)
            else False
        )

        print(
            f"{symbol}: "
            f"adf_p_level={adf_p_level:.4f}, adf_p_diff={adf_p_diff:.4f}, "
            f"pp_p_level={pp_p_level:.4f}, pp_p_diff={pp_p_diff:.4f}, "
            f"ADF_I(1)={'yes' if adf_i1 else 'no'}, PP_I(1)={'yes' if pp_i1 else 'no'}"
        )

        results.append(
            {
                "symbol": symbol,
                "adf_p_level": adf_p_level,
                "adf_p_diff": adf_p_diff,
                "adf_I(1)": adf_i1,
                "pp_p_level": pp_p_level,
                "pp_p_diff": pp_p_diff,
                "pp_I(1)": pp_i1,
            }
        )

    if not results:
        print("No valid results to save.")
        return

    df = pd.DataFrame(results)
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "stationarity_results.csv"
    df.to_csv(summary_path, index=False)
    print(f"\nSaved detailed results to {summary_path}")

    mask_both = df["adf_I(1)"] & df["pp_I(1)"]
    i1_both = df.loc[mask_both, "symbol"].tolist()

    i1_both_path = output_dir / "i1_candidates_adf_pp.csv"
    pd.DataFrame({"symbol": i1_both}).to_csv(i1_both_path, index=False)
    print(f"Saved I(1) candidates (ADF and PP) to {i1_both_path}")

    print()
    print(f"I(1) candidates in both tests: {len(i1_both)} symbols")
    if i1_both:
        print("Symbols:")
        for s in i1_both:
            print(f"  {s}")
        print()
        print("Python list literal:")
        print(i1_both)


if __name__ == "__main__":
    main()
