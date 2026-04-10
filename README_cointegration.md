Cointegration Analysis with MT5 Data
====================================

This repository provides an end-to-end toolkit to:

- collect OHLC data from MetaTrader~5 into local CSV files,
- screen assets for $I(1)$ behaviour using ADF and PP tests, and
- discover cointegrated pairs suitable for pairs trading using Engle--Granger methodology.

The focus of this README is on the cointegration pipeline. A separate document, `README_correlation.md`, summarises the correlation-analysis tools.

Requirements
------------

- Python 3.10+
- Installed and configured MetaTrader 5 terminal (for data collection)
- Python packages:
  - MetaTrader5
  - pandas
  - numpy
  - statsmodels
  - (optional) arch
  - (optional) tqdm

Install core dependencies:

```bash
pip install MetaTrader5 pandas numpy statsmodels
```

For PP tests via `arch` and progress bars via `tqdm`:

```bash
pip install arch tqdm
```

Data layout
-----------

The repository uses the following directory structure:

- `data/`: raw OHLC data downloaded from MetaTrader~5.
- `output/`: analysis outputs (stationarity results, candidate lists, cointegrated pairs, etc.).

Price CSV files in `data/` follow the pattern:

```text
<SYMBOL>_<TIMEFRAME>_<START>_<END>.csv
```

where:

- `<SYMBOL>` is the broker symbol (for example, `XAUUSD`, `EURUSD`),

- `<TIMEFRAME>` is an MT5 timeframe (for example, `D1`), and

- `<START>`, `<END>` are dates in `YYYYMMDD` format.
1. Fetching OHLC data (fetch_ohlc_mt5.py)

-----------------------------------------

The script `fetch_ohlc_mt5.py` connects to a running MetaTrader~5 terminal and downloads OHLC data for user-specified symbols, timeframes and date ranges, saving the results to `data/`.

Basic usage for a single symbol:

```bash
python fetch_ohlc_mt5.py \
  --symbol XAUUSD \
  --timeframe D1 \
  --start 2024-01-01 \
  --end 2026-01-01
```

Key arguments:

- `--symbol`: trading symbol, for example `EURUSD`, `XAUUSD`, or `all` for all available symbols.
- `--timeframe`: one of `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, `W1`, `MN1`.
- `--start`: start date (`YYYY-MM-DD`).
- `--end`: end date (`YYYY-MM-DD`, inclusive).
- `--output-dir`: directory to store CSV files (default: `data`).
- `--filename`: optional custom filename for the single-symbol case.

Downloading all broker symbols:

```bash
python fetch_ohlc_mt5.py \
  --symbol all \
  --timeframe D1 \
  --start 2024-01-01 \
  --end 2026-01-01
```

This will:

- call `mt5.symbols_get()` to list all broker symbols;
- download the requested timeframe and date range for each symbol; and
- save each symbol to its own CSV file in `data/`.

Resume support:

- if a CSV already exists for a symbol:
  - the script reads the last timestamp from the `time` column;
  - it only requests data from the later of:
    - the user-provided `--start`, and
    - the last existing time;
  - existing and new data are concatenated, duplicates by `time` are removed, and rows are sorted by `time`;
- if the existing data already covers up to `--end`, the symbol is skipped.

This logic applies in both single-symbol mode and `--symbol all` mode.

2. Stationarity screening (stationarity_check.py)

-------------------------------------------------

The script `stationarity_check.py` scans all CSV files in `data/` and identifies symbols whose log-price series are plausibly $I(1)$ using ADF and (optionally) PP tests.

For each file:

1. Read the CSV and extract the chosen price column (default: `close`).
2. Convert to log prices $p_t = \log P_t$ and drop missing or infinite values.
3. Apply the ADF test to the level series $\{p_t\}$, obtaining `adf_p_level`.
4. Apply the ADF test to the first differences $\{\Delta p_t\}$, obtaining `adf_p_diff`.
5. If a PP implementation is available, apply the PP test to both $\{p_t\}$ and $\{\Delta p_t\}$ to obtain `pp_p_level` and `pp_p_diff`; otherwise, these fields are set to NaN.
6. Classify the series as $I(1)$ under each test if:
   - the unit-root null is not rejected at levels, and
   - the null is rejected at first differences.

Run the script:

```bash
python stationarity_check.py
```

By default this writes two CSVs to `output/`:

1. `output/stationarity_results.csv`
   
   Columns:
   
   - `symbol`
   - `adf_p_level`, `adf_p_diff`, `adf_I(1)`
   - `pp_p_level`, `pp_p_diff`, `pp_I(1)`

2. `output/i1_candidates_adf_pp.csv`
   
   - Single column `symbol`, listing those assets that are $I(1)$ according to both ADF and PP at the chosen significance level.

You can adjust behaviour with:

- `--data-dir`: directory to scan (default: `data`).

- `--column`: price column to use (default: `close`).

- `--alpha`: significance level (default: 0.05).

- `--min-length`: minimum series length (default: 100 observations).
3. Pairwise cointegration search (cointegration_pairs_scan.py)

--------------------------------------------------------------

The script `cointegration_pairs_scan.py` takes the $I(1)$ universe from `output/i1_candidates_adf_pp.csv` and searches for cointegrated pairs using the Engle--Granger two-step method.

Inputs:

- `--data-dir`: directory with price CSVs (default: `data`).
- `--candidates-file`: list of $I(1)$ symbols (default: `output/i1_candidates_adf_pp.csv`).
- `--column`: price column to use (default: `close`).
- `--alpha`: significance level for ADF on the spread (default: 0.05).
- `--min-length`: minimum overlapping observations per pair (default: 100).
- `--output`: output CSV path (default: `output/cointegrated_pairs.csv`).

For each pair of symbols $(i,j)$ in the candidate list:

1. Load and align log prices $p_{i,t}$ and $p_{j,t}$ on their common time grid.
2. Estimate the regression
   $p_{i,t} = \alpha_{ij} + \beta_{ij} p_{j,t} + \varepsilon_{ij,t}$
   via ordinary least squares, obtaining $\hat{\alpha}_{ij}$ and $\hat{\beta}_{ij}$.
3. Construct the spread
   $Z_{ij,t} = p_{i,t} - \left(\hat{\alpha}*{ij} + \hat{\beta}*{ij} p_{j,t}\right).$
4. Apply the ADF test to $\{Z_{ij,t}\}$ with the null hypothesis of a unit root. If the $p$-value is below `--alpha`, treat the pair as cointegrated.
5. For cointegrated pairs, estimate an approximate half-life of mean reversion by fitting an AR(1) model to the demeaned spread and mapping the estimated coefficient to a half-life.

The script iterates over all unordered pairs and uses a progress bar (via `tqdm`, if installed) to report progress. At the end it writes a summary to:

- `output/cointegrated_pairs.csv`

with columns:

- `asset1`, `asset2`: symbol names;
- `beta`, `alpha`: regression hedge ratio and intercept;
- `adf_p_spread`: ADF $p$-value for the spread;
- `n_obs`: number of overlapping observations;
- `half_life`: estimated half-life of mean reversion.

Example invocation:

```bash
python cointegration_pairs_scan.py
```

This uses the defaults:

- candidates from `output/i1_candidates_adf_pp.csv`;

- results saved to `output/cointegrated_pairs.csv`.
4. Typical workflow

-------------------

Putting everything together, a typical research workflow is:

1. Use `fetch_ohlc_mt5.py` to download daily OHLC data for the desired universe into `data/`.
2. Run `stationarity_check.py` to identify assets that are plausibly $I(1)$ and produce:
   - `output/stationarity_results.csv`
   - `output/i1_candidates_adf_pp.csv`
3. Run `cointegration_pairs_scan.py` to scan the $I(1)$ universe for cointegrated pairs and generate:
   - `output/cointegrated_pairs.csv`
4. Inspect the resulting pairs, paying attention to:
   - the strength of stationarity evidence for the spread (`adf_p_spread`);
   - the estimated half-life (mean-reversion speed);
   - economic plausibility (sector relationships, fundamental links).
5. For selected pairs, proceed to design and backtest concrete pairs-trading strategies using the estimated spreads as inputs.
