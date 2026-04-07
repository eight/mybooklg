"""Tests for search, filter, and sort in db.query_books."""

import pytest

from blg.db import query_books, get_stats, get_all_authors, get_all_categories


BOOKS = [
    {
        "book_id": "1", "title": "百年の孤独", "author": "ガルシア・マルケス",
        "authors": "ガルシア・マルケス, 鼓直", "publisher": "新潮社",
        "rating": 5, "status_code": 3, "status_name": "読み終わった",
        "category_name": "Life", "pages": 672, "tags": "名作",
        "created_at": "2024-05-22 10:00:00", "release_date": "2006-12-01",
        "review": "マジックリアリズムの最高傑作。圧倒的な世界観。",
    },
    {
        "book_id": "2", "title": "ペスト", "author": "アルベール・カミュ",
        "authors": "アルベール・カミュ, 中条省平", "publisher": "光文社",
        "rating": 4, "status_code": 2, "status_name": "いま読んでる",
        "category_name": "Kindle", "pages": 496, "tags": "",
        "created_at": "2025-11-16 06:18:48", "release_date": "2021-09-14",
        "review": "",
    },
    {
        "book_id": "3", "title": "浮世の画家", "author": "カズオ・イシグロ",
        "authors": "カズオ・イシグロ, 飛田茂雄", "publisher": "早川書房",
        "rating": 3, "status_code": 3, "status_name": "読み終わった",
        "category_name": "U-NEXT", "pages": 336, "tags": "UNEXT",
        "created_at": "2025-11-26 18:32:31", "release_date": "2019-01-10",
        "review": "戦後日本の画家の記憶を辿る。静かで深い。",
    },
    {
        "book_id": "4", "title": "分別と多感", "author": "ジェイン・オースティン",
        "authors": "ジェイン・オースティン", "publisher": "筑摩書房",
        "rating": 0, "status_code": 1, "status_name": "読みたい",
        "category_name": "図書館", "pages": 0, "tags": "",
        "created_at": "2026-01-10 12:00:00", "release_date": "",
        "review": "",
    },
    {
        "book_id": "5", "title": "暴力の人類史 上", "author": "スティーブン・ピンカー",
        "authors": "スティーブン・ピンカー", "publisher": "青土社",
        "rating": 5, "status_code": 4, "status_name": "積読",
        "category_name": "Life", "pages": 700, "tags": "",
        "created_at": "2017-06-13 00:00:00", "release_date": "2015-01-28",
        "review": "",
    },
]


# --- Filter tests ---

class TestFilterStatus:
    def test_filter_status_read(self):
        result = query_books(BOOKS, status=3)
        assert len(result) == 2
        assert all(b["status_code"] == 3 for b in result)

    def test_filter_status_reading(self):
        result = query_books(BOOKS, status=2)
        assert len(result) == 1
        assert result[0]["title"] == "ペスト"

    def test_filter_status_want(self):
        result = query_books(BOOKS, status=1)
        assert len(result) == 1
        assert result[0]["title"] == "分別と多感"

    def test_filter_status_tsundoku(self):
        result = query_books(BOOKS, status=4)
        assert len(result) == 1
        assert result[0]["author"] == "スティーブン・ピンカー"

    def test_filter_status_none_returns_all(self):
        result = query_books(BOOKS, status=None)
        assert len(result) == len(BOOKS)


class TestFilterRating:
    def test_filter_rating_5(self):
        result = query_books(BOOKS, rating=5)
        assert len(result) == 2
        assert all(b["rating"] == 5 for b in result)

    def test_filter_rating_0(self):
        result = query_books(BOOKS, rating=0)
        assert len(result) == 1
        assert result[0]["title"] == "分別と多感"

    def test_filter_rating_none_returns_all(self):
        result = query_books(BOOKS, rating=None)
        assert len(result) == len(BOOKS)


class TestFilterAuthor:
    def test_filter_author_exact(self):
        result = query_books(BOOKS, author="カミュ")
        assert len(result) == 1
        assert result[0]["title"] == "ペスト"

    def test_filter_author_case_insensitive(self):
        result = query_books(BOOKS, author="カズオ・イシグロ")
        assert len(result) == 1

    def test_filter_author_partial(self):
        result = query_books(BOOKS, author="ピンカー")
        assert len(result) == 1

    def test_filter_author_matches_coauthors(self):
        result = query_books(BOOKS, author="鼓直")
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"

    def test_filter_author_no_match(self):
        result = query_books(BOOKS, author="太宰治")
        assert len(result) == 0


class TestFilterCategory:
    def test_filter_category_life(self):
        result = query_books(BOOKS, category="Life")
        assert len(result) == 2

    def test_filter_category_unext(self):
        result = query_books(BOOKS, category="U-NEXT")
        assert len(result) == 1
        assert result[0]["title"] == "浮世の画家"

    def test_filter_category_library(self):
        result = query_books(BOOKS, category="図書館")
        assert len(result) == 1
        assert result[0]["title"] == "分別と多感"

    def test_filter_category_kindle(self):
        result = query_books(BOOKS, category="Kindle")
        assert len(result) == 1

    def test_filter_category_case_insensitive(self):
        result = query_books(BOOKS, category="life")
        assert len(result) == 2

    def test_filter_category_no_match(self):
        result = query_books(BOOKS, category="青空文庫")
        assert len(result) == 0


class TestFilterReview:
    def test_filter_review_has(self):
        result = query_books(BOOKS, review="has")
        assert len(result) == 2
        assert all(b["review"] for b in result)

    def test_filter_review_none(self):
        result = query_books(BOOKS, review="none")
        assert len(result) == 3
        assert all(not b.get("review") for b in result)

    def test_filter_review_none_returns_all(self):
        result = query_books(BOOKS, review=None)
        assert len(result) == len(BOOKS)

    def test_search_matches_review_text(self):
        result = query_books(BOOKS, search="マジックリアリズム")
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"

    def test_combined_review_and_status(self):
        result = query_books(BOOKS, review="has", status=3)
        assert len(result) == 2

    def test_combined_review_and_rating(self):
        result = query_books(BOOKS, review="has", rating=5)
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"


# --- Search tests ---

class TestSearch:
    def test_search_by_title(self):
        result = query_books(BOOKS, search="孤独")
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"

    def test_search_by_author(self):
        result = query_books(BOOKS, search="イシグロ")
        assert len(result) == 1

    def test_search_by_publisher(self):
        result = query_books(BOOKS, search="新潮社")
        assert len(result) == 1

    def test_search_by_tag(self):
        result = query_books(BOOKS, search="名作")
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"

    def test_search_case_insensitive(self):
        result = query_books(BOOKS, search="kindle")
        # "Kindle" is a category, not in search fields (title/author/publisher/tags)
        assert len(result) == 0

    def test_search_no_match(self):
        result = query_books(BOOKS, search="存在しない本")
        assert len(result) == 0

    def test_search_empty_returns_all(self):
        result = query_books(BOOKS, search="")
        assert len(result) == len(BOOKS)


# --- Combined filter tests ---

class TestCombinedFilters:
    def test_status_and_rating(self):
        result = query_books(BOOKS, status=3, rating=5)
        assert len(result) == 1
        assert result[0]["title"] == "百年の孤独"

    def test_search_and_status(self):
        result = query_books(BOOKS, search="カミュ", status=2)
        assert len(result) == 1

    def test_search_and_status_no_match(self):
        result = query_books(BOOKS, search="カミュ", status=3)
        assert len(result) == 0

    def test_category_and_author(self):
        result = query_books(BOOKS, category="Life", author="ピンカー")
        assert len(result) == 1

    def test_all_filters(self):
        result = query_books(BOOKS, status=3, rating=5, author="マルケス", search="孤独", category="Life")
        assert len(result) == 1
        assert result[0]["book_id"] == "1"


# --- Sort tests ---

class TestSort:
    def test_sort_by_date_default_desc(self):
        result = query_books(BOOKS, sort="date")
        dates = [b["created_at"] for b in result]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_rating_desc(self):
        result = query_books(BOOKS, sort="rating")
        ratings = [b["rating"] for b in result]
        assert ratings == sorted(ratings, reverse=True)

    def test_sort_by_title_asc(self):
        result = query_books(BOOKS, sort="title")
        titles = [b["title"] for b in result]
        assert titles == sorted(titles)

    def test_sort_by_author_asc(self):
        result = query_books(BOOKS, sort="author")
        authors = [b["author"] for b in result]
        assert authors == sorted(authors)

    def test_sort_by_pages_desc(self):
        result = query_books(BOOKS, sort="pages")
        pages = [b["pages"] for b in result]
        assert pages == sorted(pages, reverse=True)

    def test_sort_by_publisher_asc(self):
        result = query_books(BOOKS, sort="publisher")
        publishers = [b["publisher"] for b in result]
        assert publishers == sorted(publishers)

    def test_sort_reverse_flips_direction(self):
        normal = query_books(BOOKS, sort="rating")
        reversed_ = query_books(BOOKS, sort="rating", reverse=True)
        normal_ratings = [b["rating"] for b in normal]
        reversed_ratings = [b["rating"] for b in reversed_]
        assert normal_ratings == sorted(normal_ratings, reverse=True)
        assert reversed_ratings == sorted(reversed_ratings)

    def test_sort_with_filter(self):
        result = query_books(BOOKS, sort="rating", status=3)
        assert len(result) == 2
        assert result[0]["rating"] >= result[1]["rating"]


# --- Limit / Offset tests ---

class TestLimitOffset:
    def test_limit(self):
        result = query_books(BOOKS, limit=2)
        assert len(result) == 2

    def test_offset(self):
        all_ = query_books(BOOKS, sort="date")
        offset = query_books(BOOKS, sort="date", offset=2)
        assert offset == all_[2:]

    def test_limit_and_offset(self):
        all_ = query_books(BOOKS, sort="date")
        result = query_books(BOOKS, sort="date", limit=2, offset=1)
        assert result == all_[1:3]

    def test_offset_beyond_length(self):
        result = query_books(BOOKS, offset=100)
        assert result == []


# --- Stats tests ---

class TestStats:
    def test_total(self):
        s = get_stats(BOOKS)
        assert s["total"] == 5

    def test_by_status(self):
        s = get_stats(BOOKS)
        status_dict = dict(s["by_status"])
        assert status_dict["読み終わった"] == 2
        assert status_dict["いま読んでる"] == 1

    def test_by_rating(self):
        s = get_stats(BOOKS)
        rating_dict = dict(s["by_rating"])
        assert rating_dict[5] == 2
        assert 0 not in rating_dict  # rating 0 excluded

    def test_top_authors(self):
        s = get_stats(BOOKS)
        authors = dict(s["top_authors"])
        assert all(v == 1 for v in authors.values())

    def test_total_pages(self):
        s = get_stats(BOOKS)
        assert s["total_pages"] == 672 + 496 + 336 + 700

    def test_avg_pages(self):
        s = get_stats(BOOKS)
        expected = round((672 + 496 + 336 + 700) / 4, 1)
        assert s["avg_pages"] == expected

    def test_by_category(self):
        s = get_stats(BOOKS)
        cat_dict = dict(s["by_category"])
        assert cat_dict["Life"] == 2
        assert cat_dict["U-NEXT"] == 1
        assert cat_dict["図書館"] == 1


# --- Helper tests ---

class TestHelpers:
    def test_get_all_authors(self):
        authors = get_all_authors(BOOKS)
        assert len(authors) == 5
        assert authors == sorted(authors)

    def test_get_all_categories(self):
        cats = get_all_categories(BOOKS)
        assert "U-NEXT" in cats
        assert "図書館" in cats
        assert "Life" in cats
        assert cats == sorted(cats)


# --- Edge cases ---

class TestEdgeCases:
    def test_empty_books(self):
        assert query_books([]) == []

    def test_empty_books_stats(self):
        s = get_stats([])
        assert s["total"] == 0
        assert s["total_pages"] == 0
        assert s["avg_pages"] == 0

    def test_missing_fields(self):
        books = [{"book_id": "x", "title": "test"}]
        result = query_books(books, search="test")
        assert len(result) == 1

    def test_none_values_in_fields(self):
        books = [{"book_id": "x", "title": "test", "author": None, "publisher": None,
                   "category_name": None, "rating": None, "status_code": None,
                   "pages": None, "created_at": None, "tags": None}]
        result = query_books(books, sort="rating")
        assert len(result) == 1
