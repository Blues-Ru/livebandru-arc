(function () {
  var NAV = {
    bands:  { ul: null, all: '/all/bands',  label: 'все группы' },
    clubs:  { ul: null, all: '/all/clubs',  label: 'все клубы' },
    cities: { ul: null, all: '/all/cities', label: 'все города' },
    genres: { ul: null, all: '/all/genres', label: 'все жанры' },
  };
  var topData   = null;
  var searchIdx = null;

  function init() {
    NAV.bands.ul  = document.getElementById('nav-bands');
    NAV.clubs.ul  = document.getElementById('nav-clubs');
    NAV.cities.ul = document.getElementById('nav-cities');
    NAV.genres.ul = document.getElementById('nav-genres');
    var input = document.getElementById('searchInput');
    if (!input) return;

    input.focus();

    loadJson('/data/top.json', function (data) {
      topData = data;
      restoreTop();
    });

    input.addEventListener('input', function () {
      var q = input.value.trim();
      if (!q) { restoreTop(); return; }
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
    xhr.open('GET', url);
    xhr.onload = function () {
      if (xhr.status === 200) cb(JSON.parse(xhr.responseText));
    };
    xhr.send();
  }

  function fillList(ul, items, allUrl, allLabel) {
    if (!ul) return;
    var html = items.map(function (e) {
      return '<li><em><a href="' + e.url + '">' + e.title + '</a></em></li>';
    }).join('');
    html += '<li><em><a href="' + allUrl + '" class="more">' + allLabel + '</a></em></li>';
    ul.innerHTML = html;
  }

  function restoreTop() {
    if (!topData) return;
    Object.keys(NAV).forEach(function (key) {
      var n = NAV[key];
      fillList(n.ul, topData[key] || [], n.all, n.label);
    });
  }

  function applySearch(q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    var buckets = { bands: [], clubs: [], cities: [], genres: [] };
    var typeMap = { band: 'bands', club: 'clubs', city: 'cities', genre: 'genres' };

    for (var i = 0; i < searchIdx.length; i++) {
      var e = searchIdx[i];
      var bucket = typeMap[e.type];
      if (!bucket || buckets[bucket].length >= 5) continue;
      var hay = (e.title + ' ' + (e.alt || '')).toLowerCase();
      if (words.every(function (w) { return hay.indexOf(w) !== -1; })) {
        buckets[bucket].push(e);
      }
    }

    Object.keys(NAV).forEach(function (key) {
      var n = NAV[key];
      fillList(n.ul, buckets[key], n.all, n.label);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
