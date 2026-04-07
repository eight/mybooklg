// blg - booklog viewer
(function() {
  'use strict';

  var DESC_SORTS = { rating: 1, created_at: 1, pages: 1 };
  var currentSort = 'created_at';
  var sortAsc = false;
  var viewMode = 'table'; // 'table' or 'card'

  function cmp(a, b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function stars(n) {
    var s = '';
    for (var i = 0; i < (n || 0); i++) s += '\u2605';
    return s;
  }

  function getFiltered() {
    var books = window.ALL_BOOKS;
    var status = document.getElementById('status-filter').value;
    var rating = document.getElementById('rating-filter').value;
    var category = document.getElementById('category-filter').value;
    var reviewFilter = document.getElementById('review-filter').value;
    var search = document.getElementById('search').value.toLowerCase();

    if (status) books = books.filter(function(b) { return b.status_code == status; });
    if (rating) books = books.filter(function(b) { return b.rating == rating; });
    if (category) books = books.filter(function(b) { return b.category_name === category; });
    if (reviewFilter === 'has') books = books.filter(function(b) { return b.review; });
    if (reviewFilter === 'none') books = books.filter(function(b) { return !b.review; });
    if (search) books = books.filter(function(b) {
      return (b.title + ' ' + b.author + ' ' + (b.authors || '') + ' ' + (b.publisher || '') + ' ' + (b.tags || '') + ' ' + (b.review || '')).toLowerCase().indexOf(search) >= 0;
    });

    books = books.slice().sort(function(a, b) {
      var va = a[currentSort] || '';
      var vb = b[currentSort] || '';
      return sortAsc ? cmp(va, vb) : cmp(vb, va);
    });

    return books;
  }

  function renderTable(books) {
    var tbody = document.getElementById('book-tbody');
    var rows = [];
    for (var i = 0; i < books.length; i++) {
      var b = books[i];
      var date = (b.created_at || '').slice(0, 10);
      var link = b.amazon_url || b.booklog_url || '#';
      var reviewHtml = b.review ? '<div class="book-review">' + esc(b.review) + '</div>' : '';
      rows.push('<tr>' +
        '<td class="col-img"><img class="book-img" src="' + esc(b.image_url || '') + '" loading="lazy" onerror="this.style.visibility=\'hidden\'"></td>' +
        '<td class="col-title"><a class="book-title" href="' + esc(link) + '" target="_blank">' + esc(b.title) + '</a>' +
          '<div class="book-author">' + esc(b.author) + '</div>' + reviewHtml + '</td>' +
        '<td class="pub-cell">' + esc(b.publisher || '') + '</td>' +
        '<td class="rating">' + stars(b.rating) + '</td>' +
        '<td><span class="badge badge-' + b.status_code + '">' + esc(b.status_name) + '</span></td>' +
        '<td class="cat-cell">' + esc(b.category_name || '') + '</td>' +
        '<td class="pages-cell">' + (b.pages || '') + '</td>' +
        '<td class="date-cell">' + date + '</td>' +
        '</tr>');
    }
    tbody.innerHTML = rows.join('');
  }

  function renderCards(books) {
    var container = document.getElementById('card-container');
    var cards = [];
    for (var i = 0; i < books.length; i++) {
      var b = books[i];
      var link = b.amazon_url || b.booklog_url || '#';
      cards.push(
        '<div class="book-card">' +
          '<a href="' + esc(link) + '" target="_blank">' +
            '<img class="book-card-img" src="' + esc(b.large_image_url || b.image_url || '') + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">' +
          '</a>' +
          '<div class="book-card-body">' +
            '<div class="book-card-title">' + esc(b.title) + '</div>' +
            '<div class="book-card-author">' + esc(b.author) + '</div>' +
            '<div class="book-card-meta">' +
              '<span class="book-card-rating">' + stars(b.rating) + '</span>' +
              '<span class="badge badge-' + b.status_code + '">' + esc(b.status_name) + '</span>' +
            '</div>' +
          '</div>' +
        '</div>');
    }
    container.innerHTML = cards.join('');
  }

  function render() {
    var books = getFiltered();

    if (viewMode === 'table') {
      renderTable(books);
    } else {
      renderCards(books);
    }

    document.getElementById('book-count').textContent =
      books.length + ' / ' + window.ALL_BOOKS.length + ' \u518a';

    // Update sort indicators
    var ths = document.querySelectorAll('th[data-sort]');
    for (var i = 0; i < ths.length; i++) {
      var th = ths[i];
      var arrow = th.querySelector('.arrow');
      if (arrow) arrow.remove();
      if (th.dataset.sort === currentSort) {
        th.classList.add('sorted');
        th.insertAdjacentHTML('beforeend',
          '<span class="arrow">' + (sortAsc ? '\u25b2' : '\u25bc') + '</span>');
      } else {
        th.classList.remove('sorted');
      }
    }
  }

  function setViewMode(mode) {
    viewMode = mode;
    var tableEl = document.querySelector('.table-view');
    var cardEl = document.getElementById('card-container');
    var btns = document.querySelectorAll('.view-toggle button');

    if (mode === 'table') {
      tableEl.classList.remove('hidden');
      cardEl.classList.add('hidden');
      btns[0].classList.add('active');
      btns[1].classList.remove('active');
    } else {
      tableEl.classList.add('hidden');
      cardEl.classList.remove('hidden');
      btns[0].classList.remove('active');
      btns[1].classList.add('active');
    }
    render();
  }

  // Sort click
  var ths = document.querySelectorAll('th[data-sort]');
  for (var i = 0; i < ths.length; i++) {
    ths[i].addEventListener('click', function() {
      if (currentSort === this.dataset.sort) {
        sortAsc = !sortAsc;
      } else {
        currentSort = this.dataset.sort;
        sortAsc = !DESC_SORTS[currentSort];
      }
      render();
    });
  }

  // Filter change
  var filterIds = ['status-filter', 'rating-filter', 'category-filter', 'review-filter'];
  for (var i = 0; i < filterIds.length; i++) {
    document.getElementById(filterIds[i]).addEventListener('change', render);
  }

  // Search
  var searchTimer;
  document.getElementById('search').addEventListener('input', function() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(render, 200);
  });

  // Reset filters
  var resetBtn = document.getElementById('reset-filters');
  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      document.getElementById('search').value = '';
      for (var i = 0; i < filterIds.length; i++) {
        document.getElementById(filterIds[i]).value = '';
      }
      render();
    });
  }

  // View toggle
  var viewBtns = document.querySelectorAll('.view-toggle button');
  for (var i = 0; i < viewBtns.length; i++) {
    viewBtns[i].addEventListener('click', function() {
      setViewMode(this.dataset.view);
    });
  }

  // Init
  render();
})();
