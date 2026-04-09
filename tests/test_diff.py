"""Tests for diff detection and changelog."""

import json

import pytest

from mybooklog.db import (
    BookChange,
    DiffResult,
    diff_books,
    load_changelog,
    save_changelog_entry,
)


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


def _book(book_id="1", title="Book A", rating=3, status_code=1, status_name="読みたい", **kw):
    return {"book_id": book_id, "title": title, "author": "Author",
            "rating": rating, "status_code": status_code, "status_name": status_name, **kw}


class TestDiffBooks:
    def test_no_changes(self):
        books = [_book("1"), _book("2")]
        diff = diff_books(books, books)
        assert not diff.has_changes
        assert diff.summary == "変更なし"

    def test_added(self):
        old = [_book("1")]
        new = [_book("1"), _book("2", title="Book B")]
        diff = diff_books(old, new)
        assert len(diff.added) == 1
        assert diff.added[0].book_id == "2"
        assert diff.added[0].title == "Book B"
        assert diff.added[0].change_type == "added"
        assert not diff.removed
        assert not diff.updated

    def test_removed(self):
        old = [_book("1"), _book("2", title="Book B")]
        new = [_book("1")]
        diff = diff_books(old, new)
        assert len(diff.removed) == 1
        assert diff.removed[0].book_id == "2"
        assert diff.removed[0].change_type == "removed"

    def test_updated_single_field(self):
        old = [_book("1", rating=3)]
        new = [_book("1", rating=5)]
        diff = diff_books(old, new)
        assert len(diff.updated) == 1
        c = diff.updated[0]
        assert c.change_type == "updated"
        assert c.fields["rating"] == (3, 5)

    def test_updated_multiple_fields(self):
        old = [_book("1", rating=3, status_code=1, status_name="読みたい")]
        new = [_book("1", rating=4, status_code=3, status_name="読み終わった")]
        diff = diff_books(old, new)
        assert len(diff.updated) == 1
        assert "rating" in diff.updated[0].fields
        assert "status_code" in diff.updated[0].fields
        assert "status_name" in diff.updated[0].fields

    def test_non_diff_fields_ignored(self):
        old = [_book("1", image_url="http://old.jpg")]
        new = [_book("1", image_url="http://new.jpg")]
        diff = diff_books(old, new)
        assert not diff.has_changes

    def test_mixed_changes(self):
        old = [_book("1"), _book("2", title="Book B"), _book("3", title="Book C")]
        new = [_book("1", rating=5), _book("3", title="Book C"), _book("4", title="Book D")]
        diff = diff_books(old, new)
        assert len(diff.added) == 1
        assert diff.added[0].book_id == "4"
        assert len(diff.removed) == 1
        assert diff.removed[0].book_id == "2"
        assert len(diff.updated) == 1
        assert diff.updated[0].book_id == "1"

    def test_empty_to_full(self):
        diff = diff_books([], [_book("1"), _book("2")])
        assert len(diff.added) == 2
        assert diff.summary == "追加2冊"

    def test_full_to_empty(self):
        diff = diff_books([_book("1"), _book("2")], [])
        assert len(diff.removed) == 2
        assert diff.summary == "削除2冊"

    def test_both_empty(self):
        diff = diff_books([], [])
        assert not diff.has_changes


class TestDiffResultSummary:
    def test_added_only(self):
        r = DiffResult(added=[BookChange("1", "A", "added")])
        assert r.summary == "追加1冊"

    def test_updated_only(self):
        r = DiffResult(updated=[BookChange("1", "A", "updated", {"rating": (3, 5)})])
        assert r.summary == "更新1冊"

    def test_mixed(self):
        r = DiffResult(
            added=[BookChange("1", "A", "added")],
            updated=[BookChange("2", "B", "updated")],
            removed=[BookChange("3", "C", "removed")],
        )
        assert r.summary == "追加1冊、更新1冊、削除1冊"


class TestChangelog:
    def test_save_and_load(self, data_dir):
        diff = DiffResult(added=[BookChange("1", "New Book", "added")])
        save_changelog_entry(diff, data_dir)
        entries = load_changelog(data_dir)
        assert len(entries) == 1
        assert entries[0]["summary"] == "追加1冊"
        assert entries[0]["added"][0]["title"] == "New Book"
        assert "timestamp" in entries[0]

    def test_newest_first(self, data_dir):
        diff1 = DiffResult(added=[BookChange("1", "First", "added")])
        diff2 = DiffResult(removed=[BookChange("2", "Second", "removed")])
        save_changelog_entry(diff1, data_dir)
        save_changelog_entry(diff2, data_dir)
        entries = load_changelog(data_dir)
        assert len(entries) == 2
        assert entries[0]["summary"] == "削除1冊"
        assert entries[1]["summary"] == "追加1冊"

    def test_limit(self, data_dir):
        for i in range(5):
            diff = DiffResult(added=[BookChange(str(i), f"Book {i}", "added")])
            save_changelog_entry(diff, data_dir)
        entries = load_changelog(data_dir, limit=3)
        assert len(entries) == 3

    def test_max_entries_trimmed(self, data_dir):
        for i in range(105):
            diff = DiffResult(added=[BookChange(str(i), f"Book {i}", "added")])
            save_changelog_entry(diff, data_dir)
        entries = load_changelog(data_dir)
        assert len(entries) == 100

    def test_load_empty(self, data_dir):
        assert load_changelog(data_dir) == []

    def test_updated_fields_serialized(self, data_dir):
        diff = DiffResult(updated=[
            BookChange("1", "Book", "updated", {"rating": (3, 5), "status_name": ("読みたい", "読み終わった")}),
        ])
        save_changelog_entry(diff, data_dir)
        entries = load_changelog(data_dir)
        fields = entries[0]["updated"][0]["fields"]
        assert fields["rating"] == [3, 5]
        assert fields["status_name"] == ["読みたい", "読み終わった"]
