#!/usr/bin/env python3
"""Regenerate research-note figures from sanitized results/ CSVs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = ROOT / "figures"


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
        }
    )


def sample_size_warning() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.2))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    boxes = [
        (0.4, 1.2, 2.8, 2.0, "#c0392b", "20 windows\ntested"),
        (3.6, 1.2, 2.8, 2.0, "#f9a825", "2 trades\npass filter"),
        (6.8, 1.2, 2.8, 2.0, "#2e7d32", "2 / 2 wins\n(tiny N)"),
    ]
    for x, y, w, h, c, text in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=c, alpha=0.9, ec="none"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="white", fontsize=11, fontweight="bold")
    ax.annotate("", xy=(3.5, 2.2), xytext=(3.2, 2.2), arrowprops=dict(arrowstyle="->", color="#333", lw=1.5))
    ax.annotate("", xy=(6.7, 2.2), xytext=(6.4, 2.2), arrowprops=dict(arrowstyle="->", color="#333", lw=1.5))
    ax.text(
        5,
        0.45,
        "Validated Trump family (no_upper_only, 24h, edge≥10%, 1/window) — interesting, not statistically proven",
        ha="center",
        fontsize=9,
        color="#333",
    )
    ax.set_title("The main result is sparsity, not a fat live edge", loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "sample_size_warning.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def mode_comparison() -> None:
    df = pd.read_csv(RES / "trump_mode_comparison.csv")
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.6))
    x = np.arange(len(df))
    labels = df["mode"].str.replace("_", "\n", regex=False)

    axes[0].bar(x, df["trades"], color="#4c78a8")
    axes[0].set_title("Trades")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=7)

    axes[1].bar(x, df["win_rate"], color="#f58518")
    axes[1].set_title("Win rate %")
    axes[1].set_ylim(0, 110)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=7)

    axes[2].bar(x, df["total_pnl"], color="#54a24b")
    axes[2].set_title("Total PnL / share")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, fontsize=7)

    fig.suptitle("Filter ablation (20 windows, entry=24h, min_edge=0.10, 1 trade/window)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "mode_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def sensitivity_heatmap() -> None:
    df = pd.read_csv(RES / "trump_sensitivity_no_upper.csv")
    piv_trades = df.pivot(index="min_edge", columns="entry_hours", values="trades")
    piv_pnl = df.pivot(index="min_edge", columns="entry_hours", values="total_pnl")

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6))
    for ax, piv, title, fmt in (
        (axes[0], piv_trades, "Trade count", ".0f"),
        (axes[1], piv_pnl, "Total PnL / share", ".2f"),
    ):
        im = ax.imshow(piv.values, cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(piv.columns)))
        ax.set_xticklabels(piv.columns)
        ax.set_yticks(range(len(piv.index)))
        ax.set_yticklabels(piv.index)
        ax.set_xlabel("entry_hours")
        ax.set_ylabel("min_edge")
        ax.set_title(title)
        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                ax.text(j, i, format(piv.values[i, j], fmt), ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("no_upper_only sensitivity — all cells still tiny N (1–5 trades)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "sensitivity_heatmap.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def yes_lottery() -> None:
    df = pd.read_csv(RES / "trump_mode_all_trades.csv").sort_values("pnl")
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    colors = ["#2e7d32" if p > 0 else "#c0392b" for p in df["pnl"]]
    ax.bar(range(len(df)), df["pnl"], color=colors)
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xlabel("Trade index (sorted by PnL)")
    ax.set_ylabel("PnL / share")
    ax.set_title("mode=all: 18 YES trades — 11% WR, but one 0.5¢ YES lottery inflates total PnL")
    ax.text(
        0.02,
        0.95,
        f"total={df['pnl'].sum():+.3f}  mean={df['pnl'].mean():+.3f}  median={df['pnl'].median():+.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, ec="#ccc"),
    )
    fig.tight_layout()
    fig.savefig(FIG / "yes_lottery_skew.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def research_path() -> None:
    steps = [
        ("Overlap +\nregime math", "framework", "#1f4e79"),
        ("mode=all\nYES hunting", "11% WR", "#c0392b"),
        ("NO upper\nfilter", "sparse", "#f9a825"),
        ("Live toolkit", "ops ready", "#4c78a8"),
        ("Elon weekly", "exploratory", "#9e9e9e"),
    ]
    fig, ax = plt.subplots(figsize=(8.4, 2.6))
    ax.set_xlim(0, len(steps) + 0.2)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Research path — toolkit + thesis first; sample size still the bottleneck", loc="left")
    for i, (title, note, color) in enumerate(steps):
        x = i + 0.5
        ax.add_patch(plt.Rectangle((x - 0.38, 0.3), 0.76, 0.42, facecolor=color, ec="none", alpha=0.9))
        ax.text(x, 0.51, title, ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        ax.text(x, 0.16, note, ha="center", fontsize=8, color="#333")
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 0.55, 0.51), xytext=(x + 0.42, 0.51), arrowprops=dict(arrowstyle="->", color="#666"))
    fig.tight_layout()
    fig.savefig(FIG / "research_path.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def series_status() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    series = ["Trump Truth Social\n(validated family)", "Elon weekly tweets\n(exploratory)"]
    trades = [2, 2]
    colors = ["#f9a825", "#9e9e9e"]
    ax.barh(series, trades, color=colors)
    ax.set_xlabel("Trades under selected NO-upper filter")
    ax.set_title("Both series are still tiny-N — Elon is not promoted to validated")
    for i, (t, label) in enumerate(zip(trades, ["Trump: +0.385 / share", "Elon: +0.264 / share"])):
        ax.text(t + 0.05, i, label, va="center", fontsize=9)
    ax.set_xlim(0, 4)
    fig.tight_layout()
    fig.savefig(FIG / "series_status.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    style()
    sample_size_warning()
    mode_comparison()
    sensitivity_heatmap()
    yes_lottery()
    research_path()
    series_status()
    print(f"Wrote figures to {FIG}")


if __name__ == "__main__":
    main()
