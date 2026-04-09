"""CLI for booklog.jp local viewer."""

import csv
import json
import sys
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from . import api, db

console = Console()

DEFAULT_USER_ID = "jinim8"


@click.group()
@click.option("--data-dir", type=click.Path(), default=None, help="Path to data directory")
@click.pass_context
def cli(ctx, data_dir):
    """booklog.jp local viewer - ブクログデータをローカルで閲覧・ソート・検索"""
    ctx.ensure_object(dict)
    from pathlib import Path
    ctx.obj["data_dir"] = Path(data_dir) if data_dir else None


@cli.command()
@click.option("--user", "-u", default=DEFAULT_USER_ID, help="booklog.jp user ID")
@click.option("--force", "-f", is_flag=True, help="キャッシュを無視して強制取得")
@click.option("--cache-hours", type=float, default=24, help="キャッシュ有効時間 (時間, default: 24)")
@click.pass_context
def fetch(ctx, user, force, cache_hours):
    """Fetch books from booklog.jp API (4ステータス並列)."""
    data_dir = ctx.obj["data_dir"]

    if not force:
        meta = db.get_meta(data_dir)
        last_fetch = meta.get("last_fetch")
        if last_fetch:
            elapsed = datetime.now() - datetime.fromisoformat(last_fetch)
            hours = elapsed.total_seconds() / 3600
            if hours < cache_hours:
                remaining = cache_hours - hours
                all_books = db.load_books(data_dir)
                console.print(f"[yellow]キャッシュ有効: {hours:.1f}時間前に取得済み (残り{remaining:.1f}時間, {len(all_books)}冊)[/yellow]")
                console.print(f"[dim]強制取得するには --force を指定[/dim]")
                return

    def on_progress(status_name, page, status_total):
        console.print(f"  [dim]{status_name}[/dim] p.{page} ({status_total}冊)", end="\r")

    def on_batch(books, status_name):
        total, new = db.merge_books(books, data_dir)
        console.print(f"  [green]{status_name}: {len(books)}冊取得 (新規{new}) → 保存 (計{total}冊)[/green]")

    old_books = db.load_books(data_dir)

    console.print(f"[bold]Fetching books for [cyan]{user}[/cyan] (4ステータス並列)...[/bold]")
    books = api.fetch_all_books(user, on_progress=on_progress, on_batch=on_batch)

    db.set_meta("last_fetch", datetime.now().isoformat(), data_dir)
    db.set_meta("user_id", user, data_dir)

    all_books = db.load_books(data_dir)
    console.print(f"[bold green]完了: {len(books)}冊取得, DB: {len(all_books)}冊[/bold green]")

    diff = db.diff_books(old_books, all_books)
    if diff.has_changes:
        db.save_changelog_entry(diff, data_dir)
        _print_diff(diff)
    else:
        console.print("[dim]変更なし[/dim]")


def _format_field_change(field: str, old_val, new_val) -> str:
    label = db.FIELD_LABELS.get(field, field)
    if field == "rating":
        old_s = "★" * (old_val or 0) if old_val else "なし"
        new_s = "★" * (new_val or 0) if new_val else "なし"
        return f"{label} {old_s}→{new_s}"
    if field == "review":
        if not old_val and new_val:
            return f"{label} (追加)"
        if old_val and not new_val:
            return f"{label} (削除)"
        return f"{label} (変更)"
    return f"{label} {old_val}→{new_val}"


def _print_diff(diff: db.DiffResult):
    console.print(f"\n[bold]── 変更サマリ: {diff.summary} ──[/bold]")
    if diff.added:
        console.print(f"  [bold green]追加 {len(diff.added)}冊:[/bold green]")
        for c in diff.added:
            console.print(f"    [green]+[/green] 「{c.title}」")
    if diff.updated:
        console.print(f"  [bold yellow]更新 {len(diff.updated)}冊:[/bold yellow]")
        for c in diff.updated:
            details = ", ".join(_format_field_change(f, o, n) for f, (o, n) in c.fields.items())
            console.print(f"    [yellow]~[/yellow] 「{c.title}」: {details}")
    if diff.removed:
        console.print(f"  [bold red]削除 {len(diff.removed)}冊:[/bold red]")
        for c in diff.removed:
            console.print(f"    [red]-[/red] 「{c.title}」")


@cli.command()
@click.option("--limit", "-n", type=int, default=10, help="表示する履歴件数")
@click.pass_context
def changes(ctx, limit):
    """Show recent change history (変更履歴を表示)."""
    data_dir = ctx.obj["data_dir"]
    entries = db.load_changelog(data_dir, limit=limit)
    if not entries:
        console.print("[yellow]変更履歴がありません。mybooklog fetch を実行してください。[/yellow]")
        return

    console.print(f"[bold cyan]── 変更履歴 ──[/bold cyan]\n")
    for entry in entries:
        ts = entry["timestamp"][:16].replace("T", " ")
        console.print(f"[bold]{ts}[/bold]  {entry['summary']}")
        for b in entry.get("added", []):
            console.print(f"  [green]+[/green] 「{b['title']}」")
        for b in entry.get("updated", []):
            fields = b.get("fields", {})
            details = ", ".join(
                _format_field_change(f, v[0], v[1]) for f, v in fields.items()
            )
            console.print(f"  [yellow]~[/yellow] 「{b['title']}」: {details}")
        for b in entry.get("removed", []):
            console.print(f"  [red]-[/red] 「{b['title']}」")
        console.print()


@cli.command("list")
@click.option("--sort", "-s", type=click.Choice(list(db.SORT_KEYS.keys())), default="date", help="Sort by")
@click.option("--status", type=click.IntRange(1, 4), default=None, help="1=読みたい 2=読んでる 3=読んだ 4=積読")
@click.option("--author", "-a", default=None, help="Filter by author")
@click.option("--search", "-q", default=None, help="Search keyword")
@click.option("--rating", "-r", type=click.IntRange(1, 5), default=None, help="Filter by rating")
@click.option("--category", "-c", default=None, help="Filter by category/shelf")
@click.option("--limit", "-n", type=int, default=50, help="Number of results")
@click.pass_context
def list_books(ctx, sort, status, author, search, rating, category, limit):
    """List books with sorting and filtering."""
    all_books = db.load_books(ctx.obj["data_dir"])
    if not all_books:
        console.print("[yellow]No books found. Run 'mybooklog fetch' first.[/yellow]")
        return

    books = db.query_books(all_books, sort=sort, status=status, author=author, search=search, rating=rating, category=category, limit=limit)

    if not books:
        console.print("[yellow]No books match filters.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("タイトル", max_width=40)
    table.add_column("著者", max_width=20)
    table.add_column("★", width=5, justify="center")
    table.add_column("状態", width=8)
    table.add_column("棚", width=10)
    table.add_column("登録日", width=10)
    table.add_column("頁", width=5, justify="right")

    for i, book in enumerate(books, 1):
        rating_str = "★" * book["rating"] if book.get("rating") else ""
        date = (book.get("created_at") or "")[:10]
        pages = str(book["pages"]) if book.get("pages") else ""
        table.add_row(
            str(i), book["title"][:40], (book.get("author") or "")[:20],
            rating_str, book.get("status_name", ""), book.get("category_name", ""),
            date, pages,
        )

    console.print(table)
    console.print(f"[dim]Showing {len(books)} of {len(all_books)} books[/dim]")


@cli.command()
@click.pass_context
def stats(ctx):
    """Show collection statistics."""
    all_books = db.load_books(ctx.obj["data_dir"])
    if not all_books:
        console.print("[yellow]No books found. Run 'mybooklog fetch' first.[/yellow]")
        return

    s = db.get_stats(all_books)

    console.print(f"\n[bold cyan]== 蔵書統計 ==[/bold cyan]")
    console.print(f"  総冊数: [bold]{s['total']}[/bold]")
    console.print(f"  総ページ数: {s['total_pages']:,}")
    console.print(f"  平均ページ数: {s['avg_pages']}")

    console.print(f"\n[bold]ステータス別[/bold]")
    for name, cnt in s["by_status"]:
        console.print(f"  {name}: {cnt}")

    console.print(f"\n[bold]評価別[/bold]")
    for rating, cnt in s["by_rating"]:
        bar = "█" * cnt + f" {cnt}"
        console.print(f"  {'★' * rating:　<5s} {bar}")

    console.print(f"\n[bold]著者別 TOP 20[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("著者", max_width=30)
    table.add_column("冊数", justify="right")
    table.add_column("", max_width=30)
    for author, cnt in s["top_authors"][:20]:
        bar = "█" * min(cnt, 30)
        table.add_row(author[:30], str(cnt), bar)
    console.print(table)

    console.print(f"\n[bold]出版社別 TOP 10[/bold]")
    for pub, cnt in s["top_publishers"][:10]:
        console.print(f"  {pub}: {cnt}")

    console.print(f"\n[bold]カテゴリ別[/bold]")
    for cat, cnt in s["by_category"]:
        console.print(f"  {cat}: {cnt}")

    meta = db.get_meta(ctx.obj["data_dir"])
    if "last_fetch" in meta:
        console.print(f"\n[dim]Last fetched: {meta['last_fetch']}[/dim]")


@cli.command()
@click.option("--format", "-f", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="Export format")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file (default: stdout)")
@click.option("--sort", "-s", type=click.Choice(list(db.SORT_KEYS.keys())), default="date")
@click.pass_context
def export(ctx, fmt, output, sort):
    """Export books to CSV or JSON."""
    all_books = db.load_books(ctx.obj["data_dir"])
    if not all_books:
        console.print("[yellow]No books found. Run 'mybooklog fetch' first.[/yellow]")
        return

    books = db.query_books(all_books, sort=sort)
    out = open(output, "w", encoding="utf-8") if output else sys.stdout

    if fmt == "json":
        json.dump(books, out, ensure_ascii=False, indent=2)
    else:
        writer = csv.DictWriter(out, fieldnames=books[0].keys())
        writer.writeheader()
        writer.writerows(books)

    if output:
        out.close()
        console.print(f"[green]Exported {len(books)} books to {output}[/green]")


@cli.command()
@click.option("--output", "-o", type=click.Path(), default=None, help="Output HTML file (default: output/index.html)")
@click.option("--open/--no-open", default=True, help="Open in browser after build")
@click.pass_context
def build(ctx, output, open):
    """Generate static HTML viewer."""
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader

    all_books = db.load_books(ctx.obj["data_dir"])
    if not all_books:
        console.print("[yellow]No books found. Run 'mybooklog fetch' first.[/yellow]")
        return

    pkg_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(pkg_dir / "templates")), autoescape=False)
    template = env.get_template("index.html")

    css = (pkg_dir / "static" / "style.css").read_text(encoding="utf-8")
    js = (pkg_dir / "static" / "app.js").read_text(encoding="utf-8")

    meta = db.get_meta(ctx.obj["data_dir"])
    fetched_at = meta.get("last_fetch", "")
    if fetched_at:
        fetched_at = datetime.fromisoformat(fetched_at).strftime("%Y-%m-%d %H:%M")

    html = template.render(
        css=css,
        js=js,
        books_json=json.dumps(all_books, ensure_ascii=False),
        stats=db.get_stats(all_books),
        categories=db.get_all_categories(all_books),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        fetched_at=fetched_at,
    )

    default_output = Path(__file__).resolve().parent.parent / "output" / "index.html"
    out_path = Path(output) if output else default_output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    console.print(f"[bold green]Generated: {out_path} ({len(all_books)}冊)[/bold green]")

    if open:
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")


if __name__ == "__main__":
    cli()
