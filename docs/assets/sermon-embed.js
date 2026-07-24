/**
 * Atonement Sermon Archive — WordPress embed.
 *
 * Usage: drop the accompanying embed-snippet.html into a WordPress
 * Custom HTML block. It loads this script and points it at the
 * sermons.json feed published by sermon-scribe's Jekyll build.
 *
 * Palette and type are pulled from atonementchicago.org's own Wix
 * theme tokens (gold action color, crimson logo color, teal link
 * color, Arial body/title stack, Georgia italic for the one accent
 * spot) rather than a generic invented style, so this reads as part
 * of the same site rather than a bolted-on widget. System fonts only
 * — no external font request.
 *
 * No build step, no dependencies. Renders a list + detail view inside
 * whichever element(s) carry [data-atonement-sermons].
 */
(function () {
  'use strict';

  var CACHE_KEY_PREFIX = 'atonement-sermons-cache:';
  var CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

  // Sourced from atonementchicago.org's real theme custom properties
  // (--wst-color-action, --color_13/14, --wst-color-fill-accent-2, etc.)
  var COLOR_CRIMSON = '#A51D3F'; // logo / heritage color
  var COLOR_CRIMSON_DARK = '#6E132A'; // penitential variant of the same hue
  var COLOR_GOLD = '#E4B50A'; // site action/button color
  var COLOR_TEAL = '#0BA3AE'; // site link/accent color
  var COLOR_TAN = '#977A5F'; // site neutral custom color

  var SEASONS = [
    { test: /palm sunday|passion|holy week|maundy thursday|good friday|day of pentecost|whitsun/i, name: 'Holy Week & Pentecost', color: COLOR_CRIMSON },
    { test: /advent|lent/i, name: 'Advent & Lent', color: COLOR_CRIMSON_DARK },
    { test: /christmas|epiphany|easter|ascension/i, name: 'Christmastide & Eastertide', color: COLOR_GOLD },
    { test: /pentecost|trinity sunday|proper \d+/i, name: 'Ordinary Time', color: COLOR_TEAL }
  ];
  var DEFAULT_SEASON = { name: 'Feast', color: COLOR_TAN };

  function seasonFor(title) {
    for (var i = 0; i < SEASONS.length; i++) {
      if (SEASONS[i].test.test(title || '')) return SEASONS[i];
    }
    return DEFAULT_SEASON;
  }

  function formatDate(iso) {
    var d = new Date(iso + 'T00:00:00');
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  function metaLine(sermon) {
    var parts = [];
    if (sermon.author) parts.push(escapeHtml(sermon.author));
    parts.push(formatDate(sermon.date));
    return parts.join(' &middot; ');
  }

  function truncate(text, maxLen) {
    text = (text || '').trim();
    if (text.length <= maxLen) return text;
    var cut = text.slice(0, maxLen);
    var lastSpace = cut.lastIndexOf(' ');
    if (lastSpace > 0) cut = cut.slice(0, lastSpace);
    return cut.replace(/[.,;:\s]+$/, '') + '…';
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  var STYLE_ID = 'atonement-sermons-style';
  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;

    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = [
      '.as-root{--as-bg:#FFFFFF;--as-card:#FFFFFF;--as-ink:#505050;--as-muted:#929292;--as-line:#CFCCCC;',
      '  font-family:Arial,Helvetica,sans-serif;color:var(--as-ink);background:var(--as-bg);',
      '  max-width:720px;margin:0 auto;padding:2rem 1.25rem;line-height:1.5}',
      '.as-root *{box-sizing:border-box}',
      '.as-list{list-style:none;margin:0;padding:0}',
      '.as-card{position:relative;background:var(--as-card);border:1px solid var(--as-line);',
      '  border-left-width:4px;border-radius:2px;padding:1.25rem 1.5rem;margin-bottom:1rem}',
      '.as-tag{font-family:Georgia,"Times New Roman",serif;font-style:italic;font-size:.72rem;',
      '  display:block;margin:0 0 .35rem}',
      '.as-meta{font-size:.85rem;color:var(--as-muted);margin:0 0 .6rem}',
      '.as-title{font-family:Arial,Helvetica,sans-serif;font-weight:bold;font-size:1.4rem;',
      '  line-height:1.3;margin:0 0 .5rem}',
      '.as-title a{color:var(--as-ink);text-decoration:none}',
      '.as-title a:hover, .as-title a:focus-visible{color:' + COLOR_TEAL + '}',
      '.as-excerpt{font-size:.95rem;color:var(--as-ink);margin:0 0 .85rem;',
      '  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
      '.as-links{font-size:.85rem;display:flex;gap:1.5rem;border-top:1px solid var(--as-line);padding-top:.75rem}',
      '.as-links a{color:' + COLOR_TEAL + ';text-decoration:none}',
      '.as-links a:hover, .as-links a:focus-visible{text-decoration:underline}',
      '.as-back{font-size:.85rem;color:' + COLOR_TEAL + ';text-decoration:none;display:inline-block;margin-bottom:1.75rem}',
      '.as-back:hover, .as-back:focus-visible{text-decoration:underline}',
      '.as-detail-head{margin-bottom:2rem}',
      '.as-detail-title{font-family:Arial,Helvetica,sans-serif;font-weight:bold;font-size:1.9rem;',
      '  line-height:1.25;margin:0 0 .5rem}',
      '.as-detail-meta{font-size:.9rem;color:var(--as-muted)}',
      '.as-watch{display:inline-block;margin-top:1.1rem;font-size:.85rem;font-weight:bold;',
      '  padding:.6rem 1.3rem;border:1px solid ' + COLOR_GOLD + ';border-radius:2px;',
      '  background:' + COLOR_GOLD + ';color:#FFFFFF;text-decoration:none}',
      '.as-watch:hover, .as-watch:focus-visible{background:#FFFFFF;color:' + COLOR_GOLD + '}',
      '.as-content{font-size:1.02rem;text-align:left}',
      '.as-content p{margin:0 0 1.25rem}',
      '.as-content p.as-lede::first-letter{font-family:Georgia,"Times New Roman",serif;',
      '  font-style:italic;font-size:3.2em;float:left;line-height:.82;padding:.05em .08em 0 0;',
      '  color:var(--as-season,' + COLOR_CRIMSON + ')}',
      '.as-empty,.as-error{color:var(--as-muted);padding:2rem 0}',
      '.as-root a{outline-offset:3px}',
      '@media(max-width:520px){.as-detail-title{font-size:1.5rem}.as-title{font-size:1.2rem}}'
    ].join('\n');
    document.head.appendChild(style);
  }

  function cardHtml(sermon, index) {
    var season = seasonFor(sermon.title);

    var links = '<a href="#/sermon/' + index + '">Read sermon &rarr;</a>';
    if (sermon.youtube_id) {
      links += '<a href="https://www.youtube.com/watch?v=' + encodeURIComponent(sermon.youtube_id) +
        '" target="_blank" rel="noopener">Watch on YouTube &nearr;</a>';
    }

    return (
      '<li class="as-card" style="border-left-color:' + season.color + '">' +
        '<span class="as-tag" style="color:' + season.color + '">' + season.name + '</span>' +
        '<div class="as-meta">' + metaLine(sermon) + '</div>' +
        '<h3 class="as-title"><a href="#/sermon/' + index + '">' + escapeHtml(sermon.title) + '</a></h3>' +
        '<p class="as-excerpt">' + escapeHtml(truncate(sermon.description, 150)) + '</p>' +
        '<div class="as-links">' + links + '</div>' +
      '</li>'
    );
  }

  function renderList(root, sermons) {
    if (!sermons.length) {
      root.innerHTML = '<div class="as-root"><p class="as-empty">No sermons published yet.</p></div>';
      return;
    }
    var items = sermons.map(cardHtml).join('');
    root.innerHTML = '<div class="as-root"><ul class="as-list">' + items + '</ul></div>';
  }

  function renderDetail(root, sermon) {
    var season = seasonFor(sermon.title);

    var watch = sermon.youtube_id
      ? '<a class="as-watch" href="https://www.youtube.com/watch?v=' + encodeURIComponent(sermon.youtube_id) +
        '" target="_blank" rel="noopener">Watch on YouTube</a>'
      : '';

    root.innerHTML =
      '<div class="as-root" style="--as-season:' + season.color + '">' +
        '<a class="as-back" href="#">&larr; All sermons</a>' +
        '<header class="as-detail-head">' +
          '<span class="as-tag" style="color:' + season.color + '">' + season.name + '</span>' +
          '<h2 class="as-detail-title">' + escapeHtml(sermon.title) + '</h2>' +
          '<div class="as-detail-meta">' + metaLine(sermon) + '</div>' +
          watch +
        '</header>' +
        '<article class="as-content">' + (sermon.content || '<p>' + escapeHtml(sermon.description) + '</p>') + '</article>' +
      '</div>';

    var firstP = root.querySelector('.as-content p');
    if (firstP) firstP.classList.add('as-lede');
  }

  function renderError(root, message) {
    root.innerHTML = '<div class="as-root"><p class="as-error">' + escapeHtml(message) + '</p></div>';
  }

  function route(root, sermons) {
    var match = /^#\/sermon\/(\d+)$/.exec(location.hash);
    if (match && sermons[+match[1]]) {
      renderDetail(root, sermons[+match[1]]);
    } else {
      renderList(root, sermons);
    }
    root.scrollIntoView({ block: 'nearest' });
  }

  function readCache(feedUrl) {
    try {
      var raw = localStorage.getItem(CACHE_KEY_PREFIX + feedUrl);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function writeCache(feedUrl, sermons) {
    try {
      localStorage.setItem(CACHE_KEY_PREFIX + feedUrl, JSON.stringify({ time: Date.now(), sermons: sermons }));
    } catch (e) {
      /* storage unavailable or full — degrade silently */
    }
  }

  function init(el) {
    var feedUrl = el.getAttribute('data-feed-url');
    if (!feedUrl) return;

    ensureStyles();
    el.innerHTML = '<div class="as-root"><p class="as-empty">Loading sermons&hellip;</p></div>';

    var cached = readCache(feedUrl);
    var sermons = cached ? cached.sermons : null;
    var isFresh = cached && Date.now() - cached.time < CACHE_TTL_MS;

    if (sermons) route(el, sermons);
    window.addEventListener('hashchange', function () {
      if (sermons) route(el, sermons);
    });

    if (isFresh) return;

    fetch(feedUrl)
      .then(function (res) {
        if (!res.ok) throw new Error('Feed request failed (' + res.status + ')');
        return res.json();
      })
      .then(function (data) {
        sermons = data;
        writeCache(feedUrl, sermons);
        route(el, sermons);
      })
      .catch(function (err) {
        if (!sermons) renderError(el, 'Sermons could not be loaded right now. Please try again shortly.');
        console.error('[atonement-sermons]', err);
      });
  }

  function boot() {
    var els = document.querySelectorAll('[data-atonement-sermons]');
    for (var i = 0; i < els.length; i++) init(els[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
