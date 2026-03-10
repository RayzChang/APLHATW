"""
Strategy tuning runner for AlphaTW backtests.

Usage examples:
  python scripts/tune_backtest.py
  python scripts/tune_backtest.py --days 90 --top 8
  python scripts/tune_backtest.py --full-market --days 60 --top 5
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import BACKTEST_UNIVERSE, SIMULATION_INITIAL_BALANCE
from core.backtest.portfolio_backtest import run_full_market_backtest, run_portfolio_backtest
from core.data.tw_data_fetcher import TWDataFetcher


@dataclass
class CandidateConfig:
    name: str
    buy_score_threshold: int
    max_position_pct: float
    max_positions: int
    max_hold_days: int
    stop_multiplier: float
    target_multiplier: float


def _preset_configs() -> list[CandidateConfig]:
    return [
        CandidateConfig("balanced_v1", 3, 0.15, 5, 15, 2.0, 3.0),
        CandidateConfig("balanced_v2", 3, 0.12, 5, 15, 1.8, 2.8),
        CandidateConfig("strict_quality", 4, 0.12, 4, 15, 2.0, 3.2),
        CandidateConfig("strict_low_dd", 4, 0.10, 4, 12, 1.8, 2.6),
        CandidateConfig("active_v1", 2, 0.15, 5, 12, 1.8, 2.8),
        CandidateConfig("active_v2", 2, 0.12, 6, 10, 1.6, 2.4),
        CandidateConfig("swing_v1", 3, 0.20, 5, 20, 2.2, 3.5),
        CandidateConfig("swing_v2", 3, 0.18, 4, 20, 2.0, 3.4),
        CandidateConfig("defensive_v1", 3, 0.10, 3, 12, 1.6, 2.4),
        CandidateConfig("defensive_v2", 4, 0.08, 3, 10, 1.5, 2.2),
    ]


def _score(summary: dict[str, Any]) -> float:
    total_return = float(summary.get("total_return_pct", 0.0) or 0.0)
    benchmark = float(summary.get("benchmark_return_pct", 0.0) or 0.0)
    alpha = total_return - benchmark
    win_rate = float(summary.get("win_rate", 0.0) or 0.0)
    max_dd = float(summary.get("max_drawdown_pct", 0.0) or 0.0)
    pf = float(summary.get("profit_factor", 0.0) or 0.0)
    capped_pf = min(pf, 3.0)
    return round(alpha * 2.0 + total_return * 1.0 + win_rate * 0.05 - max_dd * 0.30 + capped_pf * 1.5, 4)


def _run_one(
    cfg: CandidateConfig,
    days: int,
    initial_capital: float,
    fetcher: TWDataFetcher,
    full_market: bool,
) -> dict[str, Any]:
    kwargs = dict(
        days=days,
        initial_capital=initial_capital,
        buy_score_threshold=cfg.buy_score_threshold,
        max_position_pct=cfg.max_position_pct,
        max_positions=cfg.max_positions,
        max_hold_days=cfg.max_hold_days,
        stop_multiplier=cfg.stop_multiplier,
        target_multiplier=cfg.target_multiplier,
        fetcher=fetcher,
    )
    if full_market:
        result = run_full_market_backtest(**kwargs)
    else:
        result = run_portfolio_backtest(symbols=list(BACKTEST_UNIVERSE), **kwargs)

    summary = {
        "name": cfg.name,
        "days": days,
        "full_market": full_market,
        "buy_score_threshold": cfg.buy_score_threshold,
        "max_position_pct": cfg.max_position_pct,
        "max_positions": cfg.max_positions,
        "max_hold_days": cfg.max_hold_days,
        "stop_multiplier": cfg.stop_multiplier,
        "target_multiplier": cfg.target_multiplier,
        "total_return_pct": result.total_return_pct,
        "benchmark_return_pct": result.benchmark_return_pct,
        "alpha_pct": round(result.total_return_pct - result.benchmark_return_pct, 2),
        "win_rate": result.win_rate,
        "max_drawdown_pct": result.max_drawdown_pct,
        "profit_factor": result.profit_factor,
        "closed_trades": result.closed_trades,
        "symbols_loaded": result.symbols_loaded,
        "no_signal_reason": result.no_signal_reason,
    }
    summary["objective_score"] = _score(summary)
    return summary


def _write_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(rows: list[dict[str, Any]], out_md: Path, top_n: int) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Backtest Tuning Report")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Candidates tested: {len(rows)}")
    lines.append("")
    lines.append("| Rank | Config | Return% | VS 0050% | WinRate% | MaxDD% | PF | Trades | Score |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for idx, row in enumerate(rows[:top_n], start=1):
        lines.append(
            f"| {idx} | {row['name']} | {row['total_return_pct']:.2f} | "
            f"{row['alpha_pct']:.2f} | {row['win_rate']:.1f} | {row['max_drawdown_pct']:.2f} | "
            f"{row['profit_factor']:.2f} | {row['closed_trades']} | {row['objective_score']:.2f} |"
        )
    lines.append("")
    lines.append("## Parameter Snapshot (Top 3)")
    lines.append("")
    for row in rows[:3]:
        lines.append(
            f"- `{row['name']}`: threshold={row['buy_score_threshold']}, "
            f"max_pos_pct={row['max_position_pct']}, max_positions={row['max_positions']}, "
            f"hold_days={row['max_hold_days']}, stop={row['stop_multiplier']}xATR, target={row['target_multiplier']}xATR"
        )
        if row.get("no_signal_reason"):
            lines.append(f"  - note: {row['no_signal_reason']}")

    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AlphaTW strategy tuning on backtests.")
    parser.add_argument("--days", type=int, default=90, help="Backtest days window.")
    parser.add_argument("--capital", type=float, default=SIMULATION_INITIAL_BALANCE, help="Initial capital.")
    parser.add_argument("--top", type=int, default=10, help="Top rows to render in markdown.")
    parser.add_argument("--full-market", action="store_true", help="Use full market backtest mode.")
    args = parser.parse_args()

    fetcher = TWDataFetcher()
    rows: list[dict[str, Any]] = []
    configs = _preset_configs()

    print(f"[tune] mode={'full_market' if args.full_market else 'universe'} days={args.days} candidates={len(configs)}")
    for i, cfg in enumerate(configs, start=1):
        print(f"[tune] ({i}/{len(configs)}) {cfg.name} ...")
        row = _run_one(cfg, days=args.days, initial_capital=args.capital, fetcher=fetcher, full_market=args.full_market)
        rows.append(row)
        print(
            f"  -> return={row['total_return_pct']:.2f}% alpha={row['alpha_pct']:.2f}% "
            f"win={row['win_rate']:.1f}% dd={row['max_drawdown_pct']:.2f}% trades={row['closed_trades']}"
        )

    rows.sort(key=lambda x: x["objective_score"], reverse=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "full_market" if args.full_market else "universe"
    out_dir = Path("reports") / "tuning"
    out_csv = out_dir / f"tuning_{mode}_{args.days}d_{ts}.csv"
    out_md = out_dir / f"tuning_{mode}_{args.days}d_{ts}.md"
    latest_csv = out_dir / f"tuning_{mode}_{args.days}d_latest.csv"
    latest_md = out_dir / f"tuning_{mode}_{args.days}d_latest.md"

    _write_csv(rows, out_csv)
    _write_csv(rows, latest_csv)
    _write_markdown(rows, out_md, args.top)
    _write_markdown(rows, latest_md, args.top)

    best = rows[0] if rows else None
    if best:
        print(
            f"[tune] best={best['name']} return={best['total_return_pct']:.2f}% "
            f"alpha={best['alpha_pct']:.2f}% score={best['objective_score']:.2f}"
        )
    print(f"[tune] report: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
