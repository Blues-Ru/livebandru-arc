(function () {
  var SECTIONS = [
    { key: 'bands',  all: '/all/bands',  label: 'все группы' },
    { key: 'clubs',  all: '/all/clubs',  label: 'все клубы'  },
    { key: 'cities', all: '/all/cities', label: 'все города' },
    { key: 'genres', all: '/all/genres', label: 'все жанры'  },
  ];

  var searchIdx = null;

  function init() {
    var input = document.getElementById('searchInput');
    if (!input) return;

    SECTIONS.forEach(function (s) {
      s.ul   = document.getElementById('nav-' + s.key);
      s.wrap = document.getElementById('nav-section-' + s.key);
    });

    input.addEventListener('input', function () {
      var q = input.value.trim();
      if (!q) {
        restoreAll();
        return;
      }
      if (!searchIdx) {
        loadJson('/data/search.json', function (data) {
          searchIdx = data;
          applySearch(q);
        });
      } else {
        applySearch(q);
      }
    });
  }

  function loadJson(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4 && xhr.status === 200) {
        try { cb(JSON.parse(xhr.responseText)); } catch (e) {}
      }
    };
    xhr.send();
  }

  function restoreAll() {
    SECTIONS.forEach(function (s) {
      if (s.wrap) s.wrap.className = 'nav-section';
      // Restore original baked-in list by removing any search-injected content.
      // The baked HTML is stored in s.origHTML (set on first search).
      if (s.origHTML !== undefined && s.ul) s.ul.innerHTML = s.origHTML;
    });
  }

  function applySearch(q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    var buckets = { bands: [], clubs: [], cities: [], genres: [] };
    var typeMap  = { band: 'bands', club: 'clubs', city: 'cities', genre: 'genres' };

    for (var i = 0; i < searchIdx.length; i++) {
      var e      = searchIdx[i];
      var bucket = typeMap[e.type];
      if (!bucket) continue;
      var hay = (e.title + ' ' + (e.alt || '')).toLowerCase();
      var ok = true;
      for (var j = 0; j < words.length; j++) {
        if (hay.indexOf(words[j]) === -1) { ok = false; break; }
      }
      if (ok) buckets[bucket].push(e);
    }

    SECTIONS.forEach(function (s) {
      if (!s.ul || !s.wrap) return;
      // Save original HTML the first time we touch this section.
      if (s.origHTML === undefined) s.origHTML = s.ul.innerHTML;

      var list = buckets[s.key] || [];
      list.sort(function (a, b) { return (b.n || 0) - (a.n || 0); });
      list = list.slice(0, 5);

      if (list.length === 0) {
        s.wrap.className = 'nav-section hidden';
      } else {
        s.wrap.className = 'nav-section';
        s.ul.innerHTML = list.map(function (e) {
          return '<li><a href="' + e.url + '">' + e.title + '</a></li>';
        }).join('');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
