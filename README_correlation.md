Correlation Analysis with MT5 Data
==================================

This project provides two main Python scripts:

- fetch_ohlc_mt5.py: download OHLC data from a connected MetaTrader 5 terminal and store it as CSV files.
- correlation_analysis.py: compute Pearson correlations between assets using the stored CSV data.

Requirements
------------

- Python 3.10+
- Installed and configured MetaTrader 5 terminal
- Python packages:
  - MetaTrader5
  - pandas
  - numpy

Install dependencies:

```bash
pip install MetaTrader5 pandas numpy
```

Fetching OHLC Data (fetch_ohlc_mt5.py)
--------------------------------------

Basic usage for a single symbol:

```bash
python fetch_ohlc_mt5.py \
  --symbol XAUUSD \
  --timeframe D1 \
  --start 2024-01-01 \
  --end 2026-01-01
```

Arguments:

- --symbol: trading symbol, for example: EURUSD, XAUUSD, or all for all symbols.
- --timeframe: one of M1, M5, M15, M30, H1, H4, D1, W1, MN1.
- --start: start date (YYYY-MM-DD).
- --end: end date (YYYY-MM-DD, inclusive).
- --output-dir: directory to store CSV files (default: data).
- --filename: optional custom filename for the single-symbol case.

The default filename pattern (when filename is not provided) is:

```text
<SYMBOL>_<TIMEFRAME>_<START>_<END>.csv
```

Example with a custom filename:

```bash
python fetch_ohlc_mt5.py \
  --symbol EURUSD \
  --timeframe H1 \
  --start 2024-01-01 \
  --end 2024-03-01 \
  --filename eurusd_h1_q1.csv
```

Downloading all broker symbols:

```bash
python fetch_ohlc_mt5.py \
  --symbol all \
  --timeframe D1 \
  --start 2024-01-01 \
  --end 2026-01-01
```

This will:

- Call mt5.symbols_get() to list all broker symbols.
- Download the requested timeframe and date range for each symbol.
- Save each symbol to its own CSV in the output directory.

Resume Support
--------------

The fetch script is resume-aware. If you interrupt a long download, you can run the same command again to continue:

- If a CSV already exists for a symbol:
  - The script reads the last timestamp from the time column.
  - It only requests data from the later of:
    - the user-provided --start
    - the last existing time
  - Existing and new data are concatenated, duplicates by time are removed, and rows are sorted by time.
- If the existing data already covers up to --end, the symbol is skipped.

This logic applies both to:

- Single-symbol mode (e.g. --symbol EURUSD)
- All-symbol mode (--symbol all)

Correlation Analysis (correlation_analysis.py)
----------------------------------------------

Basic pairwise correlation between two assets:

```bash
python correlation_analysis.py \
  --file1 data/EURUSD_D1_20240101_20260101.csv \
  --file2 data/GBPUSD_D1_20240101_20260101.csv
```

Key arguments:

- --file1: path to the first CSV file (or all).
- --file2: path to the second CSV file (or all).
- --column1: price column from file1 (default: close).
- --column2: price column from file2 (default: close).
- --mode: transformation to apply before correlation:
  - price: use raw prices.
  - return: simple percentage returns (default).
  - logreturn: log returns.
- --data-dir: directory with CSV files when using all (default: data).
- --output: optional CSV output path.

Modes of Operation
------------------

1. Pairwise mode (both file1 and file2 are paths)

Example:

```bash
python correlation_analysis.py \
  --file1 data/EURUSD_D1_20240101_20260101.csv \
  --file2 data/GBPUSD_D1_20240101_20260101.csv \
  --mode return \
  --output output/eurusd_gbpusd_returns.csv
```

Behavior:

- Loads the specified columns from each CSV (default: close).

- Transforms series according to mode.

- Aligns timestamps (inner join).

- Prints the Pearson correlation.

- If output is provided, saves the merged two-asset series used for correlation.
2. One-vs-all mode (exactly one of file1 or file2 is all)

Example: XAUUSD vs all other assets:

```bash
python correlation_analysis.py \
  --file1 data/XAUUSD_D1_20240101_20260101.csv \
  --file2 all \
  --mode return \
  --output output/xauusd_vs_all.csv
```

or equivalently:

```bash
python correlation_analysis.py \
  --file1 all \
  --file2 data/XAUUSD_D1_20240101_20260101.csv \
  --mode return \
  --output output/all_vs_xauusd.csv
```

Behavior:

- Treats the non-all argument as the anchor asset.
- Scans the anchor file's directory for other *.csv files.
- For each other asset:
  - Loads its data (using column2 if file2 is all, or column1 if file1 is all).
  - Applies the chosen mode.
  - Aligns timestamps with the anchor and computes the correlation.
- Prints anchor vs other: value for each asset.
- Saves a table of correlations, sorted in descending order by correlation.

Default output for one-vs-all (when --output is omitted):

- output/correlation_one_vs_all.csv

Columns:

- anchor: name derived from the anchor filename.

- other: name derived from the other filename.

- correlation: Pearson correlation value.
3. All-vs-all mode (file1 all and file2 all)

Example:

```bash
python correlation_analysis.py \
  --file1 all \
  --file2 all \
  --mode return \
  --data-dir data \
  --output output/correlation_matrix.csv
```

Behavior:

- Scans data-dir for all *.csv files.
- For each file:
  - Loads column1 (default: close).
  - Applies the chosen mode.
- Aligns all series on overlapping timestamps (inner join).
- Computes the full correlation matrix between all assets.
- Saves the correlation matrix as a CSV file.

Default output for all-vs-all (when --output is omitted):

- output/correlation_matrix.csv

The CSV has:

- Rows and columns labeled by asset names derived from filenames.
- Entries equal to the Pearson correlation between the assets.
