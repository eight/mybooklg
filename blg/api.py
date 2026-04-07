"""Fetch book data from booklog.jp."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests


STATUS_MAP = {1: "読みたい", 2: "いま読んでる", 3: "読み終わった", 4: "積読"}

BASE_URL = "https://booklog.jp/users/{user_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "ja,en;q=0.9",
}

MAX_RETRIES = 3


def _get_with_retry(url, params, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 503 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        except requests.ConnectionError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return resp


def _fetch_pages(user_id: str, status_code: int, extra_params=None, on_page=None) -> list[dict]:
    """Fetch all pages for a single status with optional extra params."""
    raw_books = []
    page = 1
    url = BASE_URL.format(user_id=user_id)
    while True:
        params = {"status": status_code, "page": page, "json": "true"}
        if extra_params:
            params.update(extra_params)
        resp = _get_with_retry(url, params)
        data = resp.json()
        page_books = data.get("books", [])
        if not page_books:
            break
        raw_books.extend(page_books)
        if on_page:
            on_page(page, len(raw_books))
        page += 1
        time.sleep(0.5)
    return raw_books


def _fetch_status(user_id: str, status_code: int, status_name: str, on_page=None) -> list[dict]:
    """Fetch all books + reviews for a single status."""
    def _on_page(pg, cnt):
        if on_page:
            on_page(status_name, pg, cnt)

    # Fetch all books
    raw_books = _fetch_pages(user_id, status_code, on_page=_on_page)

    # Fetch reviewed books to get review text
    reviewed = _fetch_pages(user_id, status_code, extra_params={"reviewed": "1"})
    review_map = {}
    for rb in reviewed:
        review = rb.get("review", {})
        if review and review.get("description"):
            review_map[rb["book_id"]] = review["description"]

    # Normalize and merge
    books = []
    for book in raw_books:
        normalized = _normalize_book(book, status_code, status_name)
        normalized["review"] = review_map.get(book.get("book_id"), "")
        books.append(normalized)

    return books


def fetch_all_books(user_id: str, on_progress=None, on_batch=None, workers=4) -> list[dict]:
    """Fetch all books from booklog.jp, parallelized by status.

    Args:
        user_id: booklog.jp user ID
        on_progress: callback(status_name, page, status_total) for progress display
        on_batch: callback(books_list) called per-status when done, for incremental DB writes
        workers: number of parallel threads
    """
    all_books = []
    lock = Lock()

    def _do_status(status_code, status_name):
        def _on_page(sn, pg, cnt):
            if on_progress:
                on_progress(sn, pg, cnt)
        books = _fetch_status(user_id, status_code, status_name, on_page=_on_page)
        if on_batch and books:
            on_batch(books, status_name)
        with lock:
            all_books.extend(books)
        return status_name, len(books)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_do_status, code, name): name
            for code, name in STATUS_MAP.items()
        }
        results = {}
        for future in as_completed(futures):
            name, count = future.result()
            results[name] = count

    return all_books


def _normalize_book(book: dict, status_code: int, status_name: str) -> dict:
    """Normalize a book record from the API into a flat dict for storage."""
    item = book.get("item", {})
    authors = item.get("authors", [])
    return {
        "book_id": book.get("book_id"),
        "asin": book.get("id", ""),
        "title": book.get("title", ""),
        "author": item.get("author", ""),
        "authors": ", ".join(authors) if authors else item.get("author", ""),
        "publisher": item.get("publisher", ""),
        "image_url": book.get("image", ""),
        "large_image_url": item.get("large_image_url", ""),
        "pages": item.get("pages") or 0,
        "rating": int(book.get("rank", 0)),
        "status_code": status_code,
        "status_name": status_name,
        "category_name": book.get("category_name", ""),
        "tags": ", ".join(book.get("tags", [])),
        "release_date": item.get("release_date", ""),
        "created_at": book.get("create_on", ""),
        "read_at": book.get("read_at") or "",
        "isbn": item.get("EAN", ""),
        "amazon_url": item.get("url", ""),
        "booklog_url": f"https://booklog.jp/users/{book.get('service_id', '1')}/archives/{book.get('id', '')}",
    }
