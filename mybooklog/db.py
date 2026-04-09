"""JSON file storage for booklog data."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / ".mybooklog"

_lock = Lock()

DIFF_FIELDS = frozenset({
    "title", "author", "authors", "publisher", "rating",
    "status_code", "status_name", "category_name", "tags",
    "pages", "review", "read_at", "release_date",
})

FIELD_LABELS = {
    "title": "タイトル",
    "author": "著者",
    "authors": "著者一覧",
    "publisher": "出版社",
    "rating": "評価",
    "status_code": "ステータスコード",
    "status_name": "ステータス",
    "category_name": "カテゴリ",
    "tags": "タグ",
    "pages": "ページ数",
    "review": "レビュー",
    "read_at": "読了日",
    "release_date": "発売日",
}

_CHANGELOG_MAX_ENTRIES = 100


@dataclass
class BookChange:
    """A single book's change record."""
    book_id: str
    title: str
    change_type: str  # "added" | "removed" | "updated"
    fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class DiffResult:
    """Result of comparing two book lists."""
    added: list[BookChange] = field(default_factory=list)
    removed: list[BookChange] = field(default_factory=list)
    updated: list[BookChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.updated)

    @property
    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"追加{len(self.added)}冊")
        if self.updated:
            parts.append(f"更新{len(self.updated)}冊")
        if self.removed:
            parts.append(f"削除{len(self.removed)}冊")
        return "、".join(parts) if parts else "変更なし"


def diff_books(old_books: list[dict], new_books: list[dict]) -> DiffResult:
    """Compare two book lists and return structured diff. Pure function, no side effects."""
    old_map = {b["book_id"]: b for b in old_books}
    new_map = {b["book_id"]: b for b in new_books}

    result = DiffResult()

    for bid, book in new_map.items():
        if bid not in old_map:
            result.added.append(BookChange(
                book_id=bid, title=book.get("title", ""), change_type="added",
            ))
            continue
        old_book = old_map[bid]
        changed_fields: dict[str, tuple[Any, Any]] = {}
        for f in DIFF_FIELDS:
            old_val = old_book.get(f)
            new_val = book.get(f)
            if old_val != new_val:
                changed_fields[f] = (old_val, new_val)
        if changed_fields:
            result.updated.append(BookChange(
                book_id=bid, title=book.get("title", ""),
                change_type="updated", fields=changed_fields,
            ))

    for bid, book in old_map.items():
        if bid not in new_map:
            result.removed.append(BookChange(
                book_id=bid, title=book.get("title", ""), change_type="removed",
            ))

    return result


def _data_dir(data_dir: Path | None = None) -> Path:
    d = data_dir or DEFAULT_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _books_path(data_dir: Path | None = None) -> Path:
    return _data_dir(data_dir) / "books.json"


def _meta_path(data_dir: Path | None = None) -> Path:
    return _data_dir(data_dir) / "meta.json"


def load_books(data_dir: Path | None = None) -> list[dict]:
    p = _books_path(data_dir)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_books(books: list[dict], data_dir: Path | None = None):
    with _lock:
        p = _books_path(data_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(books, f, ensure_ascii=False, indent=2)


def merge_books(new_books: list[dict], data_dir: Path | None = None) -> tuple[int, int]:
    """Merge new books into existing data. Returns (total, new_count)."""
    with _lock:
        existing = {}
        p = _books_path(data_dir)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for b in json.load(f):
                    existing[b["book_id"]] = b

        before = len(existing)
        for b in new_books:
            existing[b["book_id"]] = b

        all_books = list(existing.values())
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(all_books, f, ensure_ascii=False, indent=2)

        return len(all_books), len(all_books) - before


def _changelog_path(data_dir: Path | None = None) -> Path:
    return _data_dir(data_dir) / "changelog.json"


def load_changelog(data_dir: Path | None = None, limit: int | None = None) -> list[dict]:
    """Load change history entries (newest first)."""
    p = _changelog_path(data_dir)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        entries = json.load(f)
    if limit:
        entries = entries[:limit]
    return entries


def save_changelog_entry(diff: DiffResult, data_dir: Path | None = None):
    """Append a changelog entry from a DiffResult. Keeps max 100 entries."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "summary": diff.summary,
        "added": [{"book_id": c.book_id, "title": c.title} for c in diff.added],
        "removed": [{"book_id": c.book_id, "title": c.title} for c in diff.removed],
        "updated": [
            {"book_id": c.book_id, "title": c.title,
             "fields": {k: list(v) for k, v in c.fields.items()}}
            for c in diff.updated
        ],
    }
    p = _changelog_path(data_dir)
    existing = []
    if p.exists():
        with open(p, encoding="utf-8") as f:
            existing = json.load(f)
    existing.insert(0, entry)
    existing = existing[:_CHANGELOG_MAX_ENTRIES]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def get_meta(data_dir: Path | None = None) -> dict:
    p = _meta_path(data_dir)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def set_meta(key: str, value: str, data_dir: Path | None = None):
    p = _meta_path(data_dir)
    meta = {}
    if p.exists():
        with open(p, encoding="utf-8") as f:
            meta = json.load(f)
    meta[key] = value
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# --- Query helpers (operate on in-memory list) ---

SORT_KEYS = {
    "title": lambda b: b.get("title", ""),
    "author": lambda b: b.get("author", ""),
    "rating": lambda b: b.get("rating", 0) or 0,
    "date": lambda b: b.get("created_at", "") or "",
    "pages": lambda b: b.get("pages", 0) or 0,
    "release": lambda b: b.get("release_date", "") or "",
    "publisher": lambda b: b.get("publisher", ""),
}

SORT_DESC = {"rating", "date", "pages", "release"}


def query_books(
    books: list[dict],
    sort: str = "date",
    reverse: bool = False,
    status: int | None = None,
    author: str | None = None,
    search: str | None = None,
    rating: int | None = None,
    category: str | None = None,
    review: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    result = books

    if status is not None:
        result = [b for b in result if b.get("status_code") == status]
    if author:
        al = author.lower()
        result = [b for b in result if al in (b.get("author", "") + b.get("authors", "")).lower()]
    if search:
        sl = search.lower()
        result = [b for b in result if sl in f"{b.get('title','')} {b.get('author','')} {b.get('authors','')} {b.get('publisher','')} {b.get('tags','')} {b.get('review','')}".lower()]
    if rating is not None:
        result = [b for b in result if b.get("rating") == rating]
    if category:
        cl = category.lower()
        result = [b for b in result if cl in (b.get("category_name", "") or "").lower()]
    if review == "has":
        result = [b for b in result if b.get("review")]
    elif review == "none":
        result = [b for b in result if not b.get("review")]

    key_fn = SORT_KEYS.get(sort, SORT_KEYS["date"])
    is_desc = sort in SORT_DESC
    result = sorted(result, key=key_fn, reverse=is_desc if not reverse else not is_desc)

    if offset:
        result = result[offset:]
    if limit:
        result = result[:limit]

    return result


def get_stats(books: list[dict]) -> dict:
    from collections import Counter

    stats = {"total": len(books)}

    status_counter = Counter()
    rating_counter = Counter()
    author_counter = Counter()
    publisher_counter = Counter()
    category_counter = Counter()
    total_pages = 0
    pages_count = 0

    for b in books:
        status_counter[b.get("status_name", "不明")] += 1
        if b.get("rating", 0) > 0:
            rating_counter[b["rating"]] += 1
        if b.get("author"):
            author_counter[b["author"]] += 1
        if b.get("publisher"):
            publisher_counter[b["publisher"]] += 1
        if b.get("category_name"):
            category_counter[b["category_name"]] += 1
        p = int(b.get("pages") or 0)
        if p > 0:
            total_pages += p
            pages_count += 1

    # Maintain status order
    status_order = ["読みたい", "いま読んでる", "読み終わった", "積読"]
    stats["by_status"] = [(s, status_counter[s]) for s in status_order if status_counter[s]]

    stats["by_rating"] = sorted(rating_counter.items(), reverse=True)
    stats["top_authors"] = author_counter.most_common(30)
    stats["top_publishers"] = publisher_counter.most_common(20)
    stats["by_category"] = category_counter.most_common()
    stats["total_pages"] = total_pages
    stats["avg_pages"] = round(total_pages / pages_count, 1) if pages_count else 0

    return stats


def get_all_authors(books: list[dict]) -> list[str]:
    return sorted({b.get("author", "") for b in books if b.get("author")})


def get_all_categories(books: list[dict]) -> list[str]:
    return sorted({b.get("category_name", "") for b in books if b.get("category_name")})
