(function () {
  var SECTIONS = {
    bands:  { key: 'bands',  all: '/all/bands',  label: 'все группы' },
    clubs:  { key: 'clubs',  all: '/all/clubs',  label: 'все клубы'  },
    cities: { key: 'cities', all: '/all/cities', label: 'все города' },
    genres: { key: 'genres', all: '/all/genres', label: 'все жанры'  },
  };
  var ORDER = ['bands', 'clubs', 'cities', 'genres'];

  var topData   = null;
  var searchIdx = null;

  function init() {
    var input = document.getElementById('searchInput');
    if (!input) return;

    // Resolve DOM refs
    ORDER.forEach(function (key) {
      var s = SECTIONS[key];
      s.ul   = document.getElementById('nav-' + key);
      s.wrap = document.getElementById('nav-section-' + key);
    });

    // Load top list on startup
    loadJson('/data/top.json', function (data) {
      topData = data;
      restoreTop();
    });

    input.addEventListener('input', function () {
      var q = input.value.trim();
      if (!q) {
        restoreTop();
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
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          try { cb(JSON.parse(xhr.responseText)); } catch (e) {}
        }
      }
    };
    xhr.send();
  }

  function setSection(key, items, showAll) {
    var s = SECTIONS[key];
    if (!s.ul || !s.wrap) return;
    if (items.length === 0 && !showAll) {
      s.wrap.style.display = 'none';
      return;
    }
    s.wrap.style.display = '';
    var html = items.map(function (e) {
      return '<li><a href="' + e.url + '">' + e.title + '</a></li>';
    }).join('');
    if (showAll) {
      html += '<li><a href="' + s.all + '" class="more">' + s.label + '</a></li>';
    }
    s.ul.innerHTML = html;
  }

  function restoreTop() {
    if (!topData) return;
    ORDER.forEach(function (key) {
      setSection(key, topData[key] || [], true);
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
      var match = true;
      for (var j = 0; j < words.length; j++) {
        if (hay.indexOf(words[j]) === -1) { match = false; break; }
      }
      if (match) buckets[bucket].push(e);
    }

    ORDER.forEach(function (key) {
      var list = buckets[key];
      list.sort(function (a, b) { return (b.n || 0) - (a.n || 0); });
      setSection(key, list.slice(0, 5), false);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
