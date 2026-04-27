(function () {
  var index = null;
  var input = document.getElementById('searchInput');
  var results = document.getElementById('searchResults');
  if (!input) return;

  function load(cb) {
    if (index) { cb(); return; }
    fetch('/data/search.json')
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; cb(); })
      .catch(function () { index = []; });
  }

  function search(q) {
    if (!q) { results.innerHTML = ''; results.style.display = 'none'; return; }
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    var hits = index.filter(function (e) {
      var hay = (e.title + ' ' + (e.alt || '')).toLowerCase();
      return words.every(function (w) { return hay.indexOf(w) !== -1; });
    }).slice(0, 10);
    if (!hits.length) { results.innerHTML = ''; results.style.display = 'none'; return; }
    results.innerHTML = hits.map(function (e) {
      return '<li><a href="' + e.url + '">' + e.title + '</a></li>';
    }).join('');
    results.style.display = 'block';
  }

  input.addEventListener('input', function () {
    var q = input.value.trim();
    if (!q) { results.innerHTML = ''; results.style.display = 'none'; return; }
    load(function () { search(q); });
  });

  document.addEventListener('click', function (e) {
    if (!input.contains(e.target) && !results.contains(e.target)) {
      results.style.display = 'none';
    }
  });
})();
