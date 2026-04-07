"""Tests for API data normalization and fetch logic."""

from unittest.mock import patch, MagicMock

import pytest

from blg.api import _normalize_book, _fetch_status, fetch_all_books, _get_with_retry


# --- Normalize tests ---

SAMPLE_API_BOOK = {
    "book_id": "12345",
    "id": "4003104285",
    "service_id": "1",
    "rank": "4",
    "title": "下谷叢話 (岩波文庫)",
    "image": "https://example.com/img.jpg",
    "create_on": "2024-05-22 10:00:00",
    "read_at": "2024-06-01 00:00:00",
    "category_name": "Life",
    "tags": ["名作", "文庫"],
    "item": {
        "author": "永井荷風",
        "authors": ["永井荷風"],
        "publisher": "岩波書店",
        "pages": 300,
        "release_date": "2000-09-14",
        "EAN": "9784003104286",
        "url": "https://www.amazon.co.jp/dp/4003104285",
        "large_image_url": "https://example.com/large.jpg",
    },
}


class TestNormalizeBook:
    def test_basic_fields(self):
        result = _normalize_book(SAMPLE_API_BOOK, 3, "読み終わった")
        assert result["book_id"] == "12345"
        assert result["title"] == "下谷叢話 (岩波文庫)"
        assert result["author"] == "永井荷風"
        assert result["publisher"] == "岩波書店"
        assert result["rating"] == 4
        assert result["status_code"] == 3
        assert result["status_name"] == "読み終わった"

    def test_authors_join(self):
        result = _normalize_book(SAMPLE_API_BOOK, 3, "読み終わった")
        assert result["authors"] == "永井荷風"

    def test_multiple_authors(self):
        book = {**SAMPLE_API_BOOK, "item": {**SAMPLE_API_BOOK["item"], "authors": ["著者A", "著者B"]}}
        result = _normalize_book(book, 3, "読み終わった")
        assert result["authors"] == "著者A, 著者B"

    def test_tags_join(self):
        result = _normalize_book(SAMPLE_API_BOOK, 3, "読み終わった")
        assert result["tags"] == "名作, 文庫"

    def test_empty_tags(self):
        book = {**SAMPLE_API_BOOK, "tags": []}
        result = _normalize_book(book, 1, "読みたい")
        assert result["tags"] == ""

    def test_missing_item(self):
        book = {"book_id": "999", "title": "Test", "rank": "0", "tags": []}
        result = _normalize_book(book, 1, "読みたい")
        assert result["author"] == ""
        assert result["pages"] == 0

    def test_null_read_at(self):
        book = {**SAMPLE_API_BOOK, "read_at": None}
        result = _normalize_book(book, 3, "読み終わった")
        assert result["read_at"] == ""

    def test_isbn(self):
        result = _normalize_book(SAMPLE_API_BOOK, 3, "読み終わった")
        assert result["isbn"] == "9784003104286"

    def test_urls(self):
        result = _normalize_book(SAMPLE_API_BOOK, 3, "読み終わった")
        assert "amazon.co.jp" in result["amazon_url"]
        assert "booklog.jp" in result["booklog_url"]


# --- Retry tests ---

class TestGetWithRetry:
    @patch("blg.api.requests.get")
    def test_success_first_try(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        result = _get_with_retry("http://test", {}, retries=3)
        assert result == mock_resp
        assert mock_get.call_count == 1

    @patch("blg.api.time.sleep")
    @patch("blg.api.requests.get")
    def test_retry_on_503(self, mock_get, mock_sleep):
        mock_503 = MagicMock()
        mock_503.status_code = 503
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_get.side_effect = [mock_503, mock_200]
        result = _get_with_retry("http://test", {}, retries=3)
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("blg.api.time.sleep")
    @patch("blg.api.requests.get")
    def test_retry_on_connection_error(self, mock_get, mock_sleep):
        import requests
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_get.side_effect = [requests.ConnectionError(), mock_200]
        result = _get_with_retry("http://test", {}, retries=3)
        assert result == mock_200

    @patch("blg.api.time.sleep")
    @patch("blg.api.requests.get")
    def test_max_retries_exhausted(self, mock_get, mock_sleep):
        import requests
        mock_get.side_effect = requests.ConnectionError()
        with pytest.raises(requests.ConnectionError):
            _get_with_retry("http://test", {}, retries=2)
        assert mock_get.call_count == 2


# --- Fetch status tests ---

class TestFetchStatus:
    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_single_page(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            # First _fetch_pages call (all books)
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": []}),
            # Second _fetch_pages call (reviewed books)
            MagicMock(json=lambda: {"books": []}),
        ]
        books = _fetch_status("testuser", 3, "読み終わった")
        assert len(books) == 1
        assert books[0]["title"] == "下谷叢話 (岩波文庫)"

    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_multiple_pages(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": []}),
            # reviewed
            MagicMock(json=lambda: {"books": []}),
        ]
        books = _fetch_status("testuser", 3, "読み終わった")
        assert len(books) == 2

    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_empty_result(self, mock_get, mock_sleep):
        mock_get.return_value = MagicMock(json=lambda: {"books": []})
        books = _fetch_status("testuser", 1, "読みたい")
        assert books == []

    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_on_page_callback(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": []}),
            # reviewed
            MagicMock(json=lambda: {"books": []}),
        ]
        calls = []
        _fetch_status("testuser", 3, "読み終わった", on_page=lambda *a: calls.append(a))
        assert len(calls) == 1
        assert calls[0] == ("読み終わった", 1, 1)

    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_review_merged(self, mock_get, mock_sleep):
        reviewed_book = {**SAMPLE_API_BOOK, "review": {"description": "素晴らしい本", "public": "1", "create_on": "2024-01-01"}}
        mock_get.side_effect = [
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": []}),
            # reviewed
            MagicMock(json=lambda: {"books": [reviewed_book]}),
            MagicMock(json=lambda: {"books": []}),
        ]
        books = _fetch_status("testuser", 3, "読み終わった")
        assert len(books) == 1
        assert books[0]["review"] == "素晴らしい本"

    @patch("blg.api.time.sleep")
    @patch("blg.api._get_with_retry")
    def test_no_review(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            MagicMock(json=lambda: {"books": [SAMPLE_API_BOOK]}),
            MagicMock(json=lambda: {"books": []}),
            MagicMock(json=lambda: {"books": []}),
        ]
        books = _fetch_status("testuser", 3, "読み終わった")
        assert books[0]["review"] == ""


# --- Fetch all books tests ---

class TestFetchAllBooks:
    @patch("blg.api._fetch_status")
    def test_aggregates_all_statuses(self, mock_fetch):
        mock_fetch.return_value = [{"book_id": "1", "title": "Test"}]
        books = fetch_all_books("testuser", workers=1)
        assert len(books) == 4  # 4 statuses × 1 book each
        assert mock_fetch.call_count == 4

    @patch("blg.api._fetch_status")
    def test_on_batch_callback(self, mock_fetch):
        mock_fetch.return_value = [{"book_id": "1", "title": "Test"}]
        batches = []
        fetch_all_books("testuser", on_batch=lambda b, s: batches.append(s), workers=1)
        assert len(batches) == 4

    @patch("blg.api._fetch_status")
    def test_empty_statuses(self, mock_fetch):
        mock_fetch.return_value = []
        books = fetch_all_books("testuser", workers=1)
        assert books == []
