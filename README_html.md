# HTML Data Visualization Guide

This project includes a browser-based visualization app in `index.html` for exploring:

- Pearson correlation values from `output/correlation_matrix.csv`
- Cointegration statistics from `output/cointegrated_pairs.csv`

## 1) Start a local web server

From the project root directory:

```bash
python -m http.server 8000
```

## 2) Open in your browser

Use either URL:

- `http://127.0.0.1:8000/`
- `http://localhost:8000/`

The app is served directly from `index.html`.

## 3) Use the app

- Select an asset from the **Asset symbol** dropdown.
- Click column headers to sort ascending/descending.
- Use **Hide non-cointegrated / Show all pairs** to filter rows.

The table displays:

- Paired Asset
- ρ (Pearson)
- β
- α
- p_ADF
- N
- t_1/2

For non-cointegrated pairs, the app shows a label and keeps the correlation value visible.

## 4) Symbol definitions

- `ρ (Pearson)`  
  Pearson correlation coefficient between the selected asset and the paired asset.  
  Range is `[-1, 1]`: `+1` means strong positive linear co-movement, `-1` means strong negative linear co-movement, and `0` means weak/no linear relationship.

- `β`  
  Cointegration hedge ratio (slope) from the spread model between the pair.  
  It indicates how many units of one asset are used to hedge the other when building the spread.

- `α`  
  Intercept term in the cointegration regression.  
  This is the constant offset in the fitted long-run relationship.

- `p_ADF`  
  P-value from the Augmented Dickey-Fuller (ADF) test applied to the spread.  
  Smaller values indicate stronger evidence that the spread is stationary (mean-reverting).

- `N`  
  Number of observations used for that pair’s estimation/testing.

- `t_1/2`  
  Estimated half-life of mean reversion of the spread (in bars of the source timeframe).  
  Smaller values generally indicate faster reversion to the mean.
