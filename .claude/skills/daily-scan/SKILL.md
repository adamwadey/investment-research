---
name: daily-scan
description: Run the daily live-market investment scan - gather global news, extract second-order trends, verify share ideas with live fundamentals, save a dated briefing to reports/ and update the watchlist. Use when the user types /daily-scan or asks for today's investment briefing.
---

# Daily Scan

Produce today's investment briefing. Follow the rules in `CLAUDE.md` throughout (second-order thinking, anti-hype verification, honest risk/reward, Freetrade suitability, disclaimer).

Get today's date first (`date +%F`, or `Get-Date -Format yyyy-MM-dd` on Windows PowerShell) and use it for the filename and report header. If `reports/<date>-briefing.md` already exists, ask whether to overwrite it or save as `<date>-briefing-2.md`.

## Step 1 - Gather news and trends

Launch the **`news-trawler`** subagent. Ask it to run `python scripts/fetch_market_data.py --news --hours 48`, run its targeted live web searches, and return its structured summary of the top 3 to 5 developments and the second-order trends each will trigger.

If it returns fewer than 3 sourced developments, send it back once with the gaps named before continuing.

## Step 2 - Find and verify share ideas

Launch the **`equity-analyst`** subagent and pass it the **full text** of the news-trawler output (it has no other context). Also tell it which tickers are already in `watchlists/active-watchlist.csv` so it can re-check them rather than re-pitch them. It must return 2 to 3 candidates per trend, verified with `python scripts/fetch_market_data.py --ticker <SYMBOLS>`, filtered, and scored on Moat, Valuation and Catalyst Strength.

Spot-check before writing: re-run the ticker script yourself on the high-conviction names and confirm the figures match. Drop any idea whose data cannot be reproduced.

## Step 3 - Write the report

Save to `reports/YYYY-MM-DD-briefing.md` using this structure:

```markdown
# Daily Investment Briefing - YYYY-MM-DD

> **Disclaimer:** <the full research-only disclaimer from CLAUDE.md, verbatim>

_Data pulled: <time UTC>. Prices may be delayed 15+ minutes._

## Executive Summary
<4-6 bullets: what changed, the trends that matter, the top ideas, the single biggest risk. Readable in under a minute.>

## High-Conviction Trends
### 1. <Trend name>
- **Trigger:** <the news, with source link and date>
- **Second-order chain:** <headline effect -> upstream/downstream effect -> who benefits>
- **Horizon:** <days/weeks | months | years>
- **What would invalidate it:** <one line>

## Actionable Share Ideas

### Structural Ideas (months to years)
| Ticker | Company | Price | Mkt Cap | Trailing P/E | Fwd P/E | Rev Growth | D/E | FCF | Analyst Target | Moat | Val | Catalyst | Total /15 | Freetrade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

#### <TICKER> - <Company>
- **Thesis:**
- **Potential reward:**
- **Risks:**
- **Risk/reward verdict:**
- **How to buy:** <Freetrade availability and exact ticker; alternative platform if better suited, and why>

### Short-Term Trades (days to weeks)
<Same table, then per idea: thesis, entry logic, invalidation level, horizon, reward, risks, FX-cost note for non-GBP names. Write "None today that pass verification." if so.>

### Considered and Rejected
| Ticker | Reason |
|---|---|

## Key Risks
<Portfolio-level risks: macro, rates, FX (GBP investor), concentration across today's ideas, event calendar for the coming week, and the main way today's theses could be wrong.>

## Platform Notes
<Only if relevant today: ideas not available on Freetrade and the alternative route or platform.>

## Sources
<Linked list of articles used, with dates.>
```

Writing standards: executive-ready, plain English, no hype words, every number traceable to the script output, `n/a` for anything missing, fact kept separate from inference.

## Step 4 - Update the watchlist

Append every **high-conviction** ticker (total 12+/15 with no score below 3) to `watchlists/active-watchlist.csv`:

- Append only. Never rewrite, reorder, or delete existing rows.
- Skip tickers already in the file; mention them in the report as "already on watchlist" instead.
- Match the existing header columns exactly, and wrap any field containing a comma in double quotes.
- Write the file as UTF-8.

## Step 5 - Report back

Tell the user: the report path, the 2-3 headline trends, the high-conviction tickers added to the watchlist, anything not buyable on Freetrade, and any feeds or data that failed.
