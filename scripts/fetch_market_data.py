#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live market data helper for the investment research workspace.

Usage:
    python scripts/fetch_market_data.py --news
    python scripts/fetch_market_data.py --news --limit 5 --hours 48
    python scripts/fetch_market_data.py --ticker NVDA ETN RR.L
    python scripts/fetch_market_data.py --ticker NVDA --json

--news uses only the standard library (urllib + xml.etree.ElementTree).
--ticker needs yfinance (pip install -r requirements.txt).

Ticker suffixes follow Yahoo Finance conventions, e.g. RR.L (London),
SAP.DE (Xetra), ASML.AS (Amsterdam), 7203.T (Tokyo). London prices are
quoted in pence (GBp).
"""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Windows consoles default to a legacy code page (cp1252); headlines often
# contain characters outside it. Force UTF-8 and never crash on output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# (source, category, url)
RSS_FEEDS = [
    ("Yahoo Finance", "markets", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "top news", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC", "business", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    ("CNBC", "technology", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ("CNBC", "energy", "https://www.cnbc.com/id/19836768/device/rss/rss.html"),
    ("CNBC", "economy", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("MarketWatch", "top stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch", "market pulse", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("BBC", "business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC", "technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("The Guardian", "business", "https://www.theguardian.com/uk/business/rss"),
    ("Investing.com", "news", "https://www.investing.com/rss/news.rss"),
    ("Investing.com", "commodities", "https://www.investing.com/rss/news_11.rss"),
    ("Investing.com", "economy", "https://www.investing.com/rss/news_14.rss"),
]

ATOM_NS = "{http://www.w3.org/2005/Atom}"


# --------------------------------------------------------------------------
# News
# --------------------------------------------------------------------------
def _clean(text):
    """Strip HTML tags/entities and collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw):
    """Parse RFC 822 or ISO 8601 dates into an aware UTC datetime (or None)."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fetch_feed(url, timeout=15):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_feed(raw):
    """Return a list of dicts from an RSS 2.0 or Atom document."""
    root = ET.fromstring(raw)
    items = []
    for node in root.iter("item"):  # RSS
        items.append(
            {
                "title": _clean(node.findtext("title")),
                "published": _parse_date(node.findtext("pubDate")),
                "summary": _clean(node.findtext("description")),
                "link": (node.findtext("link") or "").strip(),
            }
        )
    if not items:  # Atom
        for node in root.iter(ATOM_NS + "entry"):
            link = node.find(ATOM_NS + "link")
            items.append(
                {
                    "title": _clean(node.findtext(ATOM_NS + "title")),
                    "published": _parse_date(
                        node.findtext(ATOM_NS + "updated")
                        or node.findtext(ATOM_NS + "published")
                    ),
                    "summary": _clean(
                        node.findtext(ATOM_NS + "summary")
                        or node.findtext(ATOM_NS + "content")
                    ),
                    "link": link.get("href", "") if link is not None else "",
                }
            )
    return items


def fetch_news(limit=8, hours=None):
    """Fetch headlines from every feed. Returns (articles, errors)."""
    cutoff = None
    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles, errors, seen = [], [], set()
    for source, category, url in RSS_FEEDS:
        try:
            items = _parse_feed(_fetch_feed(url))
        except (urllib.error.URLError, ET.ParseError, OSError, ValueError) as exc:
            errors.append("%s (%s): %s" % (source, category, exc))
            continue
        kept = 0
        for item in items:
            if kept >= limit:
                break
            key = item["title"].lower()
            if not key or key in seen:
                continue
            if cutoff and item["published"] and item["published"] < cutoff:
                continue
            seen.add(key)
            item["source"] = source
            item["category"] = category
            articles.append(item)
            kept += 1
    return articles, errors


def print_news(articles, errors):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=" * 78)
    print("LIVE FINANCIAL HEADLINES  |  fetched %s  |  %d articles" % (now, len(articles)))
    print("=" * 78)
    current = None
    for a in articles:
        group = "%s - %s" % (a["source"], a["category"])
        if group != current:
            current = group
            print("\n### %s" % group.upper())
        stamp = a["published"].strftime("%Y-%m-%d %H:%M UTC") if a["published"] else "no timestamp"
        print("\n- %s" % a["title"])
        print("  [%s]" % stamp)
        summary = a["summary"]
        if summary and summary.lower() != a["title"].lower():
            if len(summary) > 320:
                summary = summary[:317].rstrip() + "..."
            print("  %s" % summary)
        if a["link"]:
            print("  %s" % a["link"])
    if errors:
        print("\n" + "-" * 78)
        print("Feeds that could not be read (%d):" % len(errors))
        for e in errors:
            print("  ! %s" % e)


# --------------------------------------------------------------------------
# Tickers
# --------------------------------------------------------------------------
def _num(value):
    """Return a float, or None for missing / NaN / non-numeric values."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f or f in (float("inf"), float("-inf")) else f


def _money(value, currency=""):
    v = _num(value)
    if v is None:
        return "n/a"
    sign = "-" if v < 0 else ""
    v = abs(v)
    for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= size:
            return ("%s%.2f%s %s" % (sign, v / size, suffix, currency)).strip()
    return ("%s%.2f %s" % (sign, v, currency)).strip()


def _fmt(value, pattern="%.2f"):
    v = _num(value)
    return "n/a" if v is None else pattern % v


def _pct(value):
    v = _num(value)
    return "n/a" if v is None else "%.1f%%" % (v * 100)


def fetch_ticker(symbol):
    """Return a dict of fundamentals for one symbol (never raises)."""
    import yfinance as yf

    data = {"symbol": symbol.upper(), "error": None}
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}
    except Exception as exc:  # yfinance raises many unrelated types
        data["error"] = "%s: %s" % (type(exc).__name__, exc)
        return data

    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if price is None:
        try:
            price = _num(tk.fast_info["last_price"])
        except Exception:
            price = None
    if price is None:
        data["error"] = "No data returned - check the symbol and exchange suffix (e.g. RR.L)."
        return data

    currency = info.get("currency") or ""
    low = _num(info.get("fiftyTwoWeekLow"))
    high = _num(info.get("fiftyTwoWeekHigh"))
    target = _num(info.get("targetMeanPrice"))
    data.update(
        {
            "name": info.get("longName") or info.get("shortName") or symbol.upper(),
            "exchange": info.get("fullExchangeName") or info.get("exchange") or "n/a",
            "sector": info.get("sector") or "n/a",
            "industry": info.get("industry") or "n/a",
            "currency": currency,
            "financial_currency": info.get("financialCurrency") or currency,
            "price": price,
            "day_change_pct": _num(info.get("regularMarketChangePercent")),
            "week52_low": low,
            "week52_high": high,
            "pct_below_52w_high": (high - price) / high if high else None,
            "pct_above_52w_low": (price - low) / low if low else None,
            "market_cap": _num(info.get("marketCap")),
            "trailing_pe": _num(info.get("trailingPE")),
            "forward_pe": _num(info.get("forwardPE")),
            "profit_margin": _num(info.get("profitMargins")),
            "revenue_growth_yoy": _num(info.get("revenueGrowth")),
            # Yahoo reports debt/equity as a percentage (150 = 1.5x)
            "debt_to_equity_pct": _num(info.get("debtToEquity")),
            "free_cash_flow": _num(info.get("freeCashflow")),
            "target_mean": target,
            "target_low": _num(info.get("targetLowPrice")),
            "target_high": _num(info.get("targetHighPrice")),
            "upside_to_mean_target": (target - price) / price if target else None,
            "analyst_count": _num(info.get("numberOfAnalystOpinions")),
            "recommendation": info.get("recommendationKey") or "n/a",
        }
    )
    return data


def print_ticker(d):
    print("=" * 78)
    if d.get("error"):
        print("%s  |  ERROR: %s" % (d["symbol"], d["error"]))
        return
    cur = d["currency"]
    fcur = d["financial_currency"]
    print("%s  |  %s" % (d["symbol"], d["name"]))
    print("%s  |  %s / %s" % (d["exchange"], d["sector"], d["industry"]))
    print("-" * 78)
    rows = [
        ("Price", "%s %s  (day %s)" % (_fmt(d["price"]), cur, _fmt(d["day_change_pct"], "%+.2f%%"))),
        (
            "52-week range",
            "%s - %s %s  (%s below high, %s above low)"
            % (
                _fmt(d["week52_low"]),
                _fmt(d["week52_high"]),
                cur,
                _pct(d["pct_below_52w_high"]),
                _pct(d["pct_above_52w_low"]),
            ),
        ),
        ("Market cap", _money(d["market_cap"], cur if cur != "GBp" else "GBP")),
        ("Trailing P/E", _fmt(d["trailing_pe"])),
        ("Forward P/E", _fmt(d["forward_pe"])),
        ("Profit margin", _pct(d["profit_margin"])),
        ("Revenue growth (YoY)", _pct(d["revenue_growth_yoy"])),
        (
            "Debt-to-equity",
            "n/a"
            if d["debt_to_equity_pct"] is None
            else "%.1f%%  (%.2fx)" % (d["debt_to_equity_pct"], d["debt_to_equity_pct"] / 100),
        ),
        ("Free cash flow (TTM)", _money(d["free_cash_flow"], fcur)),
        (
            "Analyst target",
            "mean %s / low %s / high %s %s  (%s analysts, %s)"
            % (
                _fmt(d["target_mean"]),
                _fmt(d["target_low"]),
                _fmt(d["target_high"]),
                cur,
                _fmt(d["analyst_count"], "%.0f"),
                d["recommendation"],
            ),
        ),
        ("Upside to mean target", _fmt(None if d["upside_to_mean_target"] is None else d["upside_to_mean_target"] * 100, "%+.1f%%")),
    ]
    for label, value in rows:
        print("  %-24s %s" % (label, value))
    if cur == "GBp":
        print("  Note: London prices and targets are in pence (GBp).")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch live financial headlines and stock fundamentals."
    )
    parser.add_argument("--news", action="store_true", help="fetch latest headlines from financial RSS feeds")
    parser.add_argument("--ticker", nargs="+", metavar="SYMBOL", help="one or more Yahoo Finance symbols, e.g. NVDA RR.L")
    parser.add_argument("--limit", type=int, default=8, help="max headlines per feed (default: 8)")
    parser.add_argument("--hours", type=float, default=None, help="only show headlines newer than this many hours")
    parser.add_argument("--json", action="store_true", help="output JSON instead of text")
    args = parser.parse_args(argv)

    if not args.news and not args.ticker:
        parser.print_help()
        return 2

    exit_code = 0
    output = {}

    if args.news:
        articles, errors = fetch_news(limit=args.limit, hours=args.hours)
        if args.json:
            output["news"] = [
                dict(a, published=a["published"].isoformat() if a["published"] else None)
                for a in articles
            ]
            output["news_errors"] = errors
        else:
            print_news(articles, errors)
        if not articles:
            exit_code = 1

    if args.ticker:
        try:
            import yfinance  # noqa: F401
        except ImportError:
            print(
                "ERROR: yfinance is not installed. Run: pip install -r requirements.txt",
                file=sys.stderr,
            )
            return 1
        results = [fetch_ticker(s) for s in args.ticker]
        if args.json:
            output["tickers"] = results
        else:
            if args.news:
                print()
            for r in results:
                print_ticker(r)
            print("=" * 78)
            print("Source: Yahoo Finance via yfinance. Data may be delayed 15+ minutes.")
        if all(r.get("error") for r in results):
            exit_code = 1

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
