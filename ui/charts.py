"""終端機圖表與表格呈現:plotext 畫圖、rich 畫表格與彩色矩陣。不存任何圖檔。"""
from __future__ import annotations

import plotext as plt
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def bar(labels, values, title: str, color: str = "cyan") -> None:
    """終端長條圖。labels 為字串清單,values 為數值清單。"""
    plt.clear_figure()
    plt.bar([str(x) for x in labels], list(values), color=color)
    plt.title(title)
    plt.plotsize(100, 20)
    plt.theme("clear")
    plt.show()


def hist(values, bins: int = 20, title: str = "") -> None:
    """終端直方圖(用於和值分布)。"""
    plt.clear_figure()
    plt.hist(list(values), bins=bins, color="orange")
    plt.title(title)
    plt.plotsize(100, 20)
    plt.theme("clear")
    plt.show()


def rich_table(title: str, columns: list[str], rows: list[list]) -> None:
    """rich 表格。"""
    table = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold magenta")
    for c in columns:
        table.add_column(str(c))
    for r in rows:
        table.add_row(*[str(x) for x in r])
    console.print(table)


def number_grid(values: dict[int, float], title: str, highlight_top: int = 5) -> None:
    """把 1~39 的數值以 5 欄網格呈現,數值越高顏色越亮。"""
    if not values:
        return
    vmax = max(values.values()) or 1
    ranked = sorted(values, key=lambda n: -values[n])[:highlight_top]
    table = Table(title=title, box=box.ROUNDED, show_header=False)
    for _ in range(5):
        table.add_column(justify="center")
    cells = []
    for n in sorted(values):
        v = values[n]
        ratio = v / vmax
        if n in ranked:
            style = "bold white on red"
        elif ratio > 0.66:
            style = "bold red"
        elif ratio > 0.33:
            style = "yellow"
        else:
            style = "blue"
        cells.append(f"[{style}]{n:02d}:{v:g}[/{style}]")
    for i in range(0, len(cells), 5):
        row = cells[i:i + 5]
        row += [""] * (5 - len(row))
        table.add_row(*row)
    console.print(table)


def info(msg: str) -> None:
    console.print(msg, style="cyan")


def warn(msg: str) -> None:
    console.print(msg, style="bold yellow")


def banner(text: str) -> None:
    from rich.panel import Panel
    console.print(Panel(text, border_style="red", title="⚠ 免責聲明"))


def pause() -> None:
    console.input("\n[dim]按 Enter 返回選單...[/dim]")
