# Allotropy
# Fed Signal Systematic Macro Strategy
### Lancaster Capital Management — Quantitative Research

---

## What This Is

A systematic equity index trading strategy built on the premise that Federal Reserve behavior — not just rate levels, but the *character* of Fed guidance — is the single most powerful regime signal available to equity investors.

The strategy doesn't predict where rates go. It reads how the Fed is communicating, cross-references that against what the market has already priced in, gates against global shock environments, and sizes positions accordingly. The core insight: **the gap between what the Fed says and what markets imply is more informative than either signal alone.**

---

## Backtest Results (1971–2026, NASDAQ Composite)

**13,950 trading days · 1971-02-05 to 2026-06-04 · 10bp round-trip transaction cost**

| Metric | Strategy | Buy & Hold | Delta |
|---|---|---|---|
| Annualized Return | **12.18%** | 10.63% | +1.55% |
| Annualized Vol | **16.2%** | 20.2% | −4.0% |
| Sharpe Ratio | **0.752** | 0.526 | +0.226 |
| Sortino Ratio | **0.930** | 0.658 | +0.272 |
| Max Drawdown | **−48.9%** | −77.9% | +29.0% |
| Calmar Ratio | **0.249** | 0.136 | +0.113 |
| Total Return | **680x** | 267x | +413x |

Same return, significantly less volatility, dramatically lower drawdown. The edge is not in chasing returns — it's in surviving the environments where buy-and-hold gets destroyed.

---

## Key Episodes

| Episode | NASDAQ | Strategy | Alpha | Notes |
|---|---|---|---|---|
| 1973–74 OPEC | −29.4% | +44.2% | **+73.6%** | Strategy's natural hunting ground |
| 1987 Black Monday | −15.5% | +9.8% | **+25.3%** | Short gate triggered |
| 1990–91 Gulf War | +10.1% | +21.7% | **+11.6%** | |
| 2000–02 Dot-com | −71.7% | −35.4% | **+36.3%** | Significant drawdown mitigation |
| 2007–09 GFC | −27.9% | −32.1% | −4.2% | Underperformed — easing regime conflicted with shock |
| 2018 Trade War | −9.5% | −11.9% | −2.4% | Short-duration shock, signal lagged |
| 2020 COVID | +3.7% | −14.8% | −18.5% | 1-month data lag at Feb 2020 peak |
| 2022 Ukraine/Inflation | −26.5% | −20.7% | **+5.8%** | Partial mitigation |
| 2023 AI Rally | +43.4% | +12.8% | −30.7% | Rate-agnostic rally; outside signal scope |

**Where the strategy wins:** global transmission shocks where Fed tightening and market stress confirm simultaneously. **Where it costs:** rate-agnostic momentum rallies (2023), and shock events faster than the monthly signal update cycle (COVID Feb–Mar 2020).

---

## Signal Architecture

The strategy runs five signal layers simultaneously:

**1. Guidance Type Classification**
FOMC communications are classified into eight regimes: `HAWKISH_EXPLICIT`, `HAWKISH_PIVOT`, `HAWKISH_GRADUAL`, `DOVISH_LOCK`, `DOVISH_EXPLICIT`, `DOVISH_PIVOT`, `DOVISH_CONDITIONAL`, `NEUTRAL`. These are not the same as the rate decision itself — a 25bp hike with dovish language is a fundamentally different signal than a 25bp hike with hawkish forward guidance.

**2. Rate Surprise vs. Market-Implied**
Fed decisions are compared against what the fed funds futures curve had priced in. A 50bp hike that markets expected is not the same shock as a 50bp hike from a meeting expected to deliver 25bp. Surprise magnitude drives the guidance classification update.

**3. Global Shock Gating**
Short positions are only permitted inside hardcoded global shock windows — events with clear cross-border transmission (OPEC embargo, GFC, COVID, Ukraine/inflation). Domestic US recessions and Fed overtightening alone do not qualify. This is a deliberate design choice: the strategy does not try to short every drawdown, only those where the macro environment structurally justifies inverse exposure.

**4. Market Absorption Signal**
When gradual hikes are met with strong positive momentum (6-month > 8%, 12-month > 5%), the market is telling you something the Fed signal alone cannot: that tightening is not yet biting. The strategy goes full long in this regime rather than defensively hedging against a hiking Fed the market is clearly ignoring.

**5. Momentum Confirmation**
3-month, 6-month, and 12-month price momentum from the actual daily price series provide real-time market state. These gate the final position size alongside the Fed signals — no single signal overrides the others.

---

## Position Sizing Logic

Positions range from −0.75x (maximum short) to +1.0x (full long):

```
+1.00x  Full long    — dovish regime, no shock, no stress; OR emergency cut; OR market absorbing hikes
+0.75x  Cautious     — hiking but market absorbing fine, no severe tightening
+0.50x  Defensive    — price stress emerging, no global shock
+0.25x  Minimal long — shock active, no tightening, moderate stress
−0.25x  Light short  — easing into freefall with earnings collapse (GFC circuit breaker)
−0.50x  Moderate     — global shock + tightening + one stress confirmation
−0.75x  Max short    — global shock + tightening + structural AND severe stress confirmed
```

---

## Key Design Decisions

**Why only short during global shocks?**
Domestic corrections are mean-reverting in ways that global transmission events are not. The strategy's edge is in regime identification, not in calling every drawdown. Attempting to short domestic slowdowns historically generates false signals that cost more in transaction costs and missed recoveries than the hedge provides.

**Why guidance-led regime detection?**
Standard FOMC regime labels are monthly aggregates with 1–2 month lag. The strategy updates on the day of each FOMC decision — when guidance turns explicitly hawkish and at least 25bp of hikes have landed, it treats that as a tightening regime immediately, without waiting for the rolling average to confirm.

**Why the fast recovery rule?**
After covering a short, the strategy jumps immediately to 1.0x long if guidance has turned dovish and the market is no longer falling hard. The historical failure mode for systematic strategies is staying defensive too long after a crisis bottom — missing the sharpest recovery gains that define long-term returns.

**Known limitations (documented honestly)**
- Monthly signal update cycle creates lag on fast-moving events (COVID Feb–Mar 2020 cost −18.5pp alpha)
- Rate-agnostic momentum regimes are outside the signal's scope (2023 AI rally cost −30.7pp alpha)
- The 1990s bull market produced −2.3x cumulative alpha drag from reduced exposure during strong trends

---

## Files

```
fed_strategy_v5.py       # Core strategy logic and backtest engine
nasdaq_daily.csv         # NASDAQ Composite daily close (FRED: NASDAQCOM)
backtest_v5.csv          # Monthly master signals
guidance_monthly.csv     # Monthly Fed guidance classifications
fomc_full_v2.csv         # FOMC decisions with exact dates, bp changes, surprise
backtest_output.csv      # Generated on run
```

---

## Running It

```bash
pip install pandas numpy
python fed_strategy_v5.py
```

Output: performance table printed to console, full daily series saved to `backtest_output.csv`.

---

## Author

Lancaster Capital Management LLC
Vladimir Posner, Founder & Portfolio Manager
NYU Economics, Class of 2028
