"""
Fed Signal Strategy v5
======================
Author: Lancaster Capital Management
Index:  NASDAQ Composite (daily, 1971–present)
Signals: Fed guidance type, surprise vs market-implied, global shock gate,
         market absorption, yield curve, earnings bear regime

Position sizes: 1.0x / 0.75x / 0.5x / 0.25x / 0.0x / -0.25x / -0.50x / -0.75x
Shorts: ONLY during hardcoded global shock windows + confirmed market stress
Transaction cost: 10bp per round-trip

Data files required (same directory or update paths):
  - nasdaq_daily.csv         : date, close  (FRED NASDAQCOM)
  - backtest_v5.csv          : monthly master signals (fomc_regime, yc_sus, etc.)
  - guidance_monthly.csv     : monthly Fed guidance classification
  - fomc_full_v2.csv         : FOMC decisions with exact dates, bp changes, surprise
"""

import pandas as pd
import numpy as np

# ── CONFIG ────────────────────────────────────────────────────────────────────
TC = 0.001          # 10bp one-way transaction cost
RVOL_THRESH = 0.30  # realized vol threshold for stress (NASDAQ-adjusted, higher than SP500)

# ── GLOBAL SHOCK WINDOWS ──────────────────────────────────────────────────────
# Shorts only permitted inside these windows — stressor must have clear cross-border
# ripple effects. Domestic US recessions / Fed overtightening alone are NOT sufficient.
SHOCK_WINDOWS = [
    ('1973-10-01', '1975-04-30', 'OPEC Oil Embargo'),
    ('1979-07-01', '1982-06-30', 'Second Oil Shock + Volcker'),
    ('1987-10-01', '1988-02-28', 'Black Monday'),
    ('1990-08-01', '1991-03-31', 'Gulf War'),
    ('1997-07-01', '1998-12-31', 'Asian Crisis + LTCM'),
    ('2000-03-01', '2002-12-31', 'Dot-com + 9/11 + Enron'),
    ('2007-08-01', '2009-06-30', 'Global Financial Crisis'),
    ('2010-04-01', '2012-12-31', 'EU Sovereign Debt Crisis'),
    ('2015-08-01', '2016-02-29', 'China Deval + EM Rout'),
    ('2018-10-01', '2019-01-31', 'Trade War Shock'),
    ('2020-02-01', '2020-05-31', 'COVID-19'),
    ('2022-02-01', '2023-06-30', 'Ukraine + Global Inflation Shock'),
]

def is_global_shock(date):
    ds = str(date.date()) if hasattr(date, 'date') else str(date)[:10]
    return any(s <= ds <= e for s, e, _ in SHOCK_WINDOWS)

def shock_name(date):
    ds = str(date.date()) if hasattr(date, 'date') else str(date)[:10]
    for s, e, name in SHOCK_WINDOWS:
        if s <= ds <= e:
            return name
    return ''


# ── POSITION LOGIC ────────────────────────────────────────────────────────────
def compute_position(
    guidance_type,   # str: HAWKISH_EXPLICIT / HAWKISH_PIVOT / HAWKISH_GRADUAL /
                     #      DOVISH_LOCK / DOVISH_EXPLICIT / DOVISH_PIVOT /
                     #      DOVISH_CONDITIONAL / NEUTRAL
    fomc_regime,     # str: TIGHTENING / EASING / PLATEAU
    mom_3m,          # float: 3-month price momentum
    mom_6m,          # float: 6-month price momentum
    mom_12m,         # float: 12-month price momentum
    rvol_6m,         # float: 6-month realized vol annualized
    yc_sustained,    # bool: yield curve sustained inversion (< -0.5% for 3+ months)
    earn_stress,     # bool: earnings momentum sharply negative (earn_mom_12m < -5%)
    earn_bear,       # bool: CAPE rich + earnings miss + sentiment falling simultaneously
    cum_hike_9m,     # float: cumulative hikes in basis points over last 9 months
    aggressive_hike, # bool: any single move >= 50bp in last 3 months
    emergency_cut,   # bool: > 100bp of cuts in last 2 months (COVID/GFC-speed response)
    global_shock,    # bool: currently inside a global shock window
    prev_position,   # float: position held last period (for fast-recovery detection)
):
    """
    Returns a position scalar: -0.75 to +1.0
    Negative = short (inverse exposure), positive = long, 1.0 = full long.
    """
    g = guidance_type
    fr = fomc_regime

    # ── Derived market state flags ────────────────────────────────────────────
    market_fine      = mom_6m > 0.00
    market_strong    = mom_6m > 0.04 and mom_12m > 0.04
    price_stress     = mom_3m < -0.05 or mom_6m < -0.08
    extreme_collapse = mom_3m < -0.12 or mom_6m < -0.18
    any_stress       = (yc_sustained or earn_stress or earn_bear
                        or rvol_6m > RVOL_THRESH)
    severe_hike      = cum_hike_9m > 200 or (aggressive_hike and cum_hike_9m > 100)

    # ── Fix 3: guidance-led regime detection ─────────────────────────────────
    # Don't wait for 6-month rolling average to flip. If guidance is explicitly
    # hawkish AND at least one real hike has landed (>25bp cumulative), treat
    # as tightening immediately — closes the 1-2 month regime label lag.
    guidance_hawkish  = g in ('HAWKISH_EXPLICIT', 'HAWKISH_PIVOT')
    hike_started      = cum_hike_9m > 25
    effective_hawkish = (fr == 'TIGHTENING') or (guidance_hawkish and hike_started)

    # ── Fix 2: fast recovery from shorts ─────────────────────────────────────
    # After covering a short, jump to 1.0x immediately if:
    #   - Guidance has turned dovish
    #   - Market is no longer falling hard (3m momentum > -3%)
    #   - Crisis is not still active (not shock + tightening simultaneously)
    coming_off_short = prev_position < 0
    crisis_ongoing   = global_shock and effective_hawkish
    fast_recovery    = (
        coming_off_short
        and g in ('DOVISH_LOCK', 'DOVISH_EXPLICIT', 'DOVISH_PIVOT', 'DOVISH_CONDITIONAL')
        and mom_3m > -0.03
        and not crisis_ongoing
    )

    # ── Fix 1: full exposure in dovish no-shock periods ───────────────────────
    # When guidance is strongly dovish, no global shock, no price stress, not
    # in effective tightening — go 1.0x. Don't hedge against an easing Fed.
    strongly_dovish     = g in ('DOVISH_LOCK', 'DOVISH_EXPLICIT', 'DOVISH_PIVOT')
    go_full_long_dovish = (
        strongly_dovish
        and not global_shock
        and not price_stress
        and not effective_hawkish
    )

    # ── Fix 4: market absorption signal ──────────────────────────────────────
    # HAWKISH_GRADUAL (measured, 25bp/meeting) is only a concern if the market
    # is struggling under the hikes. When momentum is strongly positive
    # (6m > 8%, 12m > 5%) with no stress signals: market is absorbing hikes.
    # Go 1.0x. Threshold is high enough to not fire in 1994, 2022, or declining markets.
    market_absorbing_hikes = (
        g == 'HAWKISH_GRADUAL'
        and mom_6m > 0.08
        and mom_12m > 0.05
        and not global_shock
        and not any_stress
    )

    # ── Fix 5: dovish guidance overrides lagging tightening regime ────────────
    # When guidance has explicitly turned dovish (DOVISH_EXPLICIT) AND market
    # is strongly confirming the pivot (6m momentum > 15%): trust guidance
    # over the lagging fomc_regime label. The price action validates the turn.
    dovish_guidance_overrides_regime = (
        g in ('DOVISH_EXPLICIT', 'DOVISH_LOCK')
        and mom_6m > 0.15
        and not global_shock
        and not severe_hike
        and not any_stress
    )

    # ── DECISION TREE ─────────────────────────────────────────────────────────

    # Emergency Fed response: >100bp cut in 2 months = Fed in crisis mode → trust it
    if emergency_cut:
        return 1.0

    # Fast recovery from short
    if fast_recovery:
        return 1.0

    # Market absorbing gradual hikes: stay full long
    if market_absorbing_hikes:
        return 1.0

    # Dovish guidance confirmed by strong price momentum: override lagging regime
    if dovish_guidance_overrides_regime:
        return 1.0

    # HAWKISH_EXPLICIT / HAWKISH_PIVOT / effective tightening
    if effective_hawkish:
        if market_fine and not severe_hike:
            # Hiking but market absorbing fine → cautious long (not short)
            return 0.75
        if not global_shock:
            # No global shock → cautious at worst, NEVER short
            return 0.5 if price_stress else 0.75
        # Global shock + tightening + confirmed market stress → SHORT
        if price_stress and (any_stress or severe_hike):
            if any_stress and severe_hike:
                return -0.75   # both structural + severe: maximum short
            return -0.50       # one confirmation: moderate short
        return 0.5

    # EASING regime
    elif fr == 'EASING':
        if go_full_long_dovish:
            return 1.0
        if not global_shock:
            return 1.0
        # Easing into freefall with earnings collapse (GFC-style circuit breaker)
        if extreme_collapse and (earn_stress or earn_bear):
            return -0.25
        return 1.0

    # PLATEAU / no clear direction
    else:
        if go_full_long_dovish:
            return 1.0
        if market_absorbing_hikes:
            return 1.0
        if not global_shock:
            return 1.0 if market_strong else 0.75
        # Shock active but no tightening: follow price action
        if extreme_collapse and any_stress:
            return -0.25
        if price_stress and any_stress:
            return 0.25
        return 1.0 if market_strong else 0.75


# ── BACKTEST ENGINE ───────────────────────────────────────────────────────────
def run_backtest(nasdaq_df, master_df, guide_df, fomc_df):
    """
    nasdaq_df : DataFrame with columns [date, close]  (daily, sorted ascending)
    master_df : DataFrame with monthly signal columns
    guide_df  : DataFrame with monthly guidance_type column
    fomc_df   : DataFrame with FOMC decisions (date, change_bp, stance, etc.)

    Returns nasdaq_df with added columns:
        pos        : position held entering each day
        ret_bh     : daily buy-and-hold return
        ret_strat  : daily strategy return (after transaction costs)
    """
    nasdaq_df = nasdaq_df.sort_values('date').reset_index(drop=True)
    nasdaq_df['ret_bh'] = nasdaq_df['close'].pct_change()

    master_idx = master_df.set_index('date').sort_index()
    guide_idx  = guide_df.set_index('date').sort_index()
    fomc_lookup = {str(r['date'].date()): r for _, r in fomc_df.iterrows()}

    positions  = []
    rets_strat = []

    # Current signal state (updated at month boundaries and FOMC days)
    prev_pos   = 0.75
    prev_month = None
    cur_g   = 'NEUTRAL';   cur_fr   = 'PLATEAU'
    cur_chk = 0.0;         cur_aggr = False
    cur_emg = False;       cur_yc   = False
    cur_earn = False;      cur_eb   = False

    for i, row in nasdaq_df.iterrows():
        d   = row['date']
        ret = row['ret_bh'] if not pd.isna(row['ret_bh']) else 0.0

        # ── Update monthly signals at each new month ──────────────────────────
        month_start = d.replace(day=1)
        if prev_month != month_start:
            prev_month = month_start
            m_cands = master_idx[master_idx.index <= month_start]
            g_cands = guide_idx[guide_idx.index <= month_start]
            if len(m_cands):
                m = m_cands.iloc[-1]
                cur_fr   = str(m.get('fomc_regime', 'PLATEAU') or 'PLATEAU')
                cur_chk  = float(m.get('cum_hike_9m', 0) or 0)
                cur_aggr = bool(m.get('aggressive', False))
                cur_emg  = bool(m.get('emergency_cut', False))
                cur_yc   = bool(m.get('yc_sus', False))
                cur_earn = bool(m.get('earn_stress', False))
                cur_eb   = bool(m.get('earn_bear', False))
            if len(g_cands):
                cur_g = str(g_cands.iloc[-1].get('guidance_type', 'NEUTRAL') or 'NEUTRAL')

        # ── Update on FOMC decision day (same-day signal, eliminates monthly lag) ──
        ds = str(d.date())
        if ds in fomc_lookup:
            fr = fomc_lookup[ds]
            cb = float(fr['change_bp'])
            # Update cumulative hike tracker
            cur_chk = max(0, cur_chk + max(0, cb))
            # Update guidance immediately from decision magnitude
            if cb >= 50:
                cur_g = 'HAWKISH_EXPLICIT'
            elif cb <= -50:
                cur_g = 'DOVISH_EXPLICIT'
            # Update regime
            if cb > 0 and cur_chk > 50:
                cur_fr = 'TIGHTENING'
            elif cb < 0:
                cur_fr = 'EASING'

        # ── Compute daily momentum from actual price series ───────────────────
        p_now = nasdaq_df.loc[i, 'close']
        p_3m  = nasdaq_df.loc[max(0, i-63),  'close']
        p_6m  = nasdaq_df.loc[max(0, i-126), 'close']
        p_12m = nasdaq_df.loc[max(0, i-252), 'close']
        rvol  = nasdaq_df.loc[max(0, i-20):i, 'ret_bh'].std() * np.sqrt(252)
        if np.isnan(rvol): rvol = 0.20

        mom3  = p_now / p_3m  - 1 if p_3m  > 0 else 0
        mom6  = p_now / p_6m  - 1 if p_6m  > 0 else 0
        mom12 = p_now / p_12m - 1 if p_12m > 0 else 0

        shock = is_global_shock(d)

        # ── Compute position ──────────────────────────────────────────────────
        pos = compute_position(
            guidance_type   = cur_g,
            fomc_regime     = cur_fr,
            mom_3m          = mom3,
            mom_6m          = mom6,
            mom_12m         = mom12,
            rvol_6m         = rvol,
            yc_sustained    = cur_yc,
            earn_stress     = cur_earn,
            earn_bear       = cur_eb,
            cum_hike_9m     = cur_chk,
            aggressive_hike = cur_aggr,
            emergency_cut   = cur_emg,
            global_shock    = shock,
            prev_position   = prev_pos,
        )

        positions.append(pos)

        # Strategy return: position set YESTERDAY applies to TODAY's return
        # (no look-ahead: we don't know today's return when setting the position)
        if i == 0:
            rets_strat.append(0.0)
        else:
            tc = abs(positions[-2] - prev_pos) * TC
            rets_strat.append(positions[-2] * ret - tc)

        prev_pos = pos

    nasdaq_df['pos']       = positions
    nasdaq_df['ret_strat'] = rets_strat
    return nasdaq_df


# ── PERFORMANCE METRICS ───────────────────────────────────────────────────────
def performance_metrics(returns, freq=252):
    r = pd.Series(returns).fillna(0)
    cum     = (1 + r).cumprod()
    total   = float(cum.iloc[-1] - 1)
    n       = len(r) / freq
    ann_ret = float((1 + total) ** (1 / n) - 1)
    ann_vol = float(r.std() * np.sqrt(freq))
    sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0
    downvol = r[r < 0].std() * np.sqrt(freq)
    sortino = ann_ret / downvol if downvol > 0 else 0
    drawdown = ((cum - cum.cummax()) / cum.cummax()).min()
    calmar  = ann_ret / abs(drawdown) if drawdown != 0 else 0
    win_rate = (r > 0).sum() / max(len(r[r != 0]), 1)
    return {
        'ann_ret':   round(ann_ret, 4),
        'ann_vol':   round(ann_vol, 4),
        'sharpe':    round(sharpe, 4),
        'sortino':   round(sortino, 4),
        'max_dd':    round(float(drawdown), 4),
        'calmar':    round(calmar, 4),
        'total_ret': round(total, 4),
        'win_rate':  round(float(win_rate), 4),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import os

    BASE = os.path.dirname(os.path.abspath(__file__))

    nasdaq  = pd.read_csv(os.path.join(BASE, 'nasdaq_daily.csv'),     parse_dates=['date'])
    master  = pd.read_csv(os.path.join(BASE, 'backtest_v5.csv'),      parse_dates=['date'])
    guide   = pd.read_csv(os.path.join(BASE, 'guidance_monthly.csv'), parse_dates=['date'])
    fomc    = pd.read_csv(os.path.join(BASE, 'fomc_full_v2.csv'),      parse_dates=['date'])

    master = master[master['date'] <= '2025-12-01'].reset_index(drop=True)

    print("Running backtest...")
    result = run_backtest(nasdaq, master, guide, fomc)

    bh_metrics   = performance_metrics(result['ret_bh'])
    strat_metrics= performance_metrics(result['ret_strat'])

    print(f"\n{'Metric':15} {'Buy & Hold':>12} {'Strategy':>12} {'Delta':>10}")
    print("-" * 52)
    for k in ['ann_ret', 'ann_vol', 'sharpe', 'sortino', 'max_dd', 'calmar']:
        bv = bh_metrics[k]; sv = strat_metrics[k]
        d  = sv - bv
        print(f"{k:15} {bv:>12.3f} {sv:>12.3f} {d:>+10.3f}")

    result.to_csv(os.path.join(BASE, 'backtest_output.csv'), index=False)
    print(f"\nOutput saved to backtest_output.csv")
    print(f"Total rows: {len(result)}")
    print(f"Date range: {result['date'].iloc[0].date()} to {result['date'].iloc[-1].date()}")
