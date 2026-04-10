import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort cointegrated pairs by increasing adf_p_spread."
    )
    parser.add_argument(
        "--input",
        default="output/cointegrated_pairs.csv",
        help="Input CSV file with cointegrated pairs.",
    )
    parser.add_argument(
        "--output",
        default="output/cointegrated_pairs_sorted.csv",
        help="Output CSV file for sorted pairs.",
    )
    parser.add_argument(
        "--na-last",
        action="store_true",
        help="Place rows with missing adf_p_spread at the end.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    if "adf_p_spread" not in df.columns:
        raise ValueError("Input file must contain an 'adf_p_spread' column.")

    df_sorted = df.sort_values(
        "adf_p_spread",
        ascending=True,
        na_position="last" if args.na_last else "first",
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_sorted.to_csv(output_path, index=False)
    print(f"Saved sorted pairs to {output_path}")


if __name__ == "__main__":
    main()

