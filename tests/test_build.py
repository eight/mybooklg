"""Tests for HTML build: template rendering, filters, tabs, stats."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from blg.cli import cli
from blg import db


SAMPLE_BOOKS = [
    {
        "book_id": "1", "asin": "123", "title": "百年の孤独", "author": "マルケス",
        "authors": "マルケス, 鼓直", "publisher": "新潮社", "image_url": "", "large_image_url": "",
        "pages": 672, "rating": 5, "status_code": 3, "status_name": "読み終わった",
        "category_name": "Life", "tags": "", "release_date": "2006-12-01",
        "created_at": "2024-05-22", "read_at": "", "isbn": "", "amazon_url": "", "booklog_url": "",
    },
    {
        "book_id": "2", "asin": "456", "title": "ペスト", "author": "カミュ",
        "authors": "カミュ", "publisher": "光文社", "image_url": "", "large_image_url": "",
        "pages": 496, "rating": 4, "status_code": 2, "status_name": "いま読んでる",
        "category_name": "Kindle", "tags": "", "release_date": "2021-09-14",
        "created_at": "2025-11-16", "read_at": "", "isbn": "", "amazon_url": "", "booklog_url": "",
    },
    {
        "book_id": "3", "asin": "789", "title": "浮世の画家", "author": "イシグロ",
        "authors": "イシグロ", "publisher": "早川書房", "image_url": "", "large_image_url": "",
        "pages": 336, "rating": 3, "status_code": 3, "status_name": "読み終わった",
        "category_name": "U-NEXT", "tags": "", "release_date": "2019-01-10",
        "created_at": "2025-11-26", "read_at": "", "isbn": "", "amazon_url": "", "booklog_url": "",
    },
    {
        "book_id": "4", "asin": "000", "title": "分別と多感", "author": "オースティン",
        "authors": "オースティン", "publisher": "筑摩書房", "image_url": "", "large_image_url": "",
        "pages": 0, "rating": 0, "status_code": 1, "status_name": "読みたい",
        "category_name": "図書館", "tags": "", "release_date": "",
        "created_at": "2026-01-10", "read_at": "", "isbn": "", "amazon_url": "", "booklog_url": "",
    },
]


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def populated_dir(data_dir):
    db.save_books(SAMPLE_BOOKS, data_dir)
    return data_dir


@pytest.fixture
def runner():
    return CliRunner()


def build_html(runner, data_dir, output_path):
    result = runner.invoke(cli, ["--data-dir", str(data_dir), "build", "--no-open", "-o", str(output_path)])
    assert result.exit_code == 0, result.output
    return output_path.read_text(encoding="utf-8")


# --- HTML structure tests ---

class TestHtmlStructure:
    def test_generates_html_file(self, runner, populated_dir, tmp_path):
        out = tmp_path / "out.html"
        html = build_html(runner, populated_dir, out)
        assert out.exists()
        assert "<!DOCTYPE html>" in html

    def test_contains_css(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert "<style>" in html
        assert "--accent:" in html

    def test_contains_js(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert "window.ALL_BOOKS" in html
        assert "function render()" in html

    def test_contains_generated_timestamp(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert "Generated:" in html


# --- Category filter tests ---

class TestCategoryFilter:
    def test_all_categories_in_select(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '<option value="Life">Life</option>' in html
        assert '<option value="Kindle">Kindle</option>' in html
        assert '<option value="U-NEXT">U-NEXT</option>' in html
        assert '<option value="図書館">図書館</option>' in html

    def test_default_all_option(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert 'カテゴリ' in html

    def test_status_filter_options(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '<option value="1">読みたい</option>' in html
        assert '<option value="3">読み終わった</option>' in html

    def test_rating_filter_options(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '<option value="5">★★★★★</option>' in html
        assert '<option value="1">★</option>' in html


# --- Tab and stats tests ---

class TestTabsAndStats:
    def test_tab_buttons_exist(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '一覧' in html
        assert '統計</button>' in html

    def test_tab_onclick_handlers(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert "books-view" in html
        assert "stats-view" in html
        assert "onclick=" in html

    def test_stats_view_has_hidden_class(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert 'id="stats-view" class="hidden"' in html

    def test_stats_total(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '>4</div>' in html  # total books
        assert '総冊数' in html

    def test_stats_total_pages(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '1,504' in html  # 672+496+336
        assert '総ページ' in html

    def test_stats_by_status(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '読み終わった' in html
        assert '読みたい' in html
        assert 'いま読んでる' in html

    def test_stats_by_rating(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '★★★★★' in html
        assert '評価分布' in html

    def test_stats_top_authors(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert 'マルケス' in html
        assert '著者 TOP 20' in html

    def test_stats_top_publishers(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '新潮社' in html
        assert '出版社 TOP 10' in html

    def test_stats_categories(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert 'カテゴリ' in html
        assert 'U-NEXT' in html
        assert '図書館' in html


# --- Books JSON embedding tests ---

class TestBooksJson:
    def test_books_json_valid(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        # Extract JSON between "window.ALL_BOOKS = " and ";\n"
        start = html.index("window.ALL_BOOKS = ") + len("window.ALL_BOOKS = ")
        end = html.index(";", start)
        books = json.loads(html[start:end])
        assert len(books) == 4

    def test_books_json_has_all_fields(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        start = html.index("window.ALL_BOOKS = ") + len("window.ALL_BOOKS = ")
        end = html.index(";", start)
        books = json.loads(html[start:end])
        required = {"book_id", "title", "author", "rating", "status_code", "status_name", "category_name"}
        for book in books:
            assert required.issubset(book.keys())

    def test_books_json_unicode(self, runner, populated_dir, tmp_path):
        html = build_html(runner, populated_dir, tmp_path / "out.html")
        assert '百年の孤独' in html
        assert 'マルケス' in html


# --- CLI build edge cases ---

class TestBuildEdgeCases:
    def test_build_no_data(self, runner, data_dir, tmp_path):
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "build", "--no-open", "-o", str(tmp_path / "out.html")])
        assert result.exit_code == 0
        assert "No books found" in result.output

    def test_build_creates_output_dir(self, runner, populated_dir, tmp_path):
        out = tmp_path / "new_dir" / "index.html"
        result = runner.invoke(cli, ["--data-dir", str(populated_dir), "build", "--no-open", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()
