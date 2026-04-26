#!/usr/bin/env python3
"""
LiveBand.Ru static site generator.
Reads livebandru-arc/data/{bands,clubs,cities,genres,gigs}/ → writes liveband-site/.
"""

import yaml
import json
import math
import hashlib
import shutil
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

from jinja2 import Environment, FileSystemLoader

ARC    = Path(__file__).parent.parent
SITE   = ARC / "liveband-site"
DATA   = ARC / "data"
TMPL   = ARC / "templates"
STATIC   = ARC / "static"

ITEMS_PER_PAGE = 50
RECENT_GIGS_COUNT = 5
TOP_VENUES_COUNT = 7

WEEKDAY_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
WEEKDAY_FULL  = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
WEEKEND_DAYS  = {5, 6}  # sat, sun


def load_entities(name: str) -> list:
    """Load all {name}/{slug}.yaml files, return as flat list sorted by slug."""
    items = []
    for f in sorted((DATA / name).glob("*.yaml")):
        item = yaml.safe_load(f.read_text(encoding="utf-8"))
        if item:
            items.append(item)
    return items


def load_gigs() -> list:
    """Load all gigs/{club}/{year}.yaml files, return as flat list."""
    gigs = []
    for year_file in sorted((DATA / "gigs").rglob("*.yaml")):
        batch = yaml.safe_load(year_file.read_text(encoding="utf-8"))
        if batch:
            gigs.extend(batch)
    return gigs


def enrich_data(bands, clubs, cities, genres, gigs):
    """Add computed/denormalized fields back after loading from clean YAML."""
    cities_by_id = {c['id']: c for c in cities}
    genres_by_id = {g['id']: g for g in genres}

    # Count gigs per band and club
    band_gig_counts: dict[int, int] = defaultdict(int)
    club_gig_counts: dict[int, int] = defaultdict(int)
    for g in gigs:
        if g.get('band_id'):
            band_gig_counts[g['band_id']] += 1
        if g.get('club_id'):
            club_gig_counts[g['club_id']] += 1

    for b in bands:
        city  = cities_by_id.get(b.get('city_id'), {})
        genre = genres_by_id.get(b.get('genre_id'), {})
        sec   = genres_by_id.get(b.get('secondary_genre_id'), {})
        b['city_name']              = city.get('name')
        b['city_token']             = city.get('token')
        b['genre_name']             = genre.get('name')
        b['genre_token']            = genre.get('token')
        b['secondary_genre_name']   = sec.get('name')
        b['secondary_genre_token']  = sec.get('token')
        b['gig_count']              = band_gig_counts.get(b['id'], 0)

    for c in clubs:
        city = cities_by_id.get(c.get('city_id'), {})
        c['city_name']  = city.get('name')
        c['city_token'] = city.get('token')
        c['gig_count']  = club_gig_counts.get(c['id'], 0)

    bands_per_city: dict[int, int] = defaultdict(int)
    clubs_per_city: dict[int, int] = defaultdict(int)
    for b in bands:
        if b.get('city_id'):
            bands_per_city[b['city_id']] += 1
    for c in clubs:
        if c.get('city_id'):
            clubs_per_city[c['city_id']] += 1
    for c in cities:
        c['band_count'] = bands_per_city.get(c['id'], 0)
        c['club_count'] = clubs_per_city.get(c['id'], 0)

    bands_per_genre: dict[int, int] = defaultdict(int)
    for b in bands:
        if b.get('genre_id'):
            bands_per_genre[b['genre_id']] += 1
        if b.get('secondary_genre_id'):
            bands_per_genre[b['secondary_genre_id']] += 1
    for g in genres:
        g['band_count'] = bands_per_genre.get(g['id'], 0)


def write_html(path, html):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')


def page_seed(token):
    """Deterministic 1–6 header image selector based on token."""
    return (int(hashlib.md5((token or 'x').encode()).hexdigest(), 16) % 6) + 1


def parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


def fmt_short_date(d):
    """27.02.YYYY format."""
    if not d:
        return ''
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def fmt_long_date(d):
    if not d:
        return ''
    return f"{d.strftime('%d.%m.%Y')}"


def russian_plural(n, one, few, many):
    n = abs(n)
    if 11 <= (n % 100) <= 19:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def gig_to_display(g):
    """Convert a raw gig dict to display-ready dict."""
    d = parse_date(g.get('date'))
    weekday = d.weekday() if d else None
    return {
        'date': g.get('date'),
        'short_date': fmt_short_date(d),
        'long_date': fmt_long_date(d),
        'weekday': WEEKDAY_FULL[weekday].capitalize() if weekday is not None else '',
        'weekday_short': WEEKDAY_SHORT[weekday] if weekday is not None else '',
        'is_weekend': weekday in WEEKEND_DAYS if weekday is not None else False,
        'time': g.get('time'),
        'band_id': g.get('band_id'),
        'band_name': g.get('band_name'),
        'band_token': g.get('band_token'),
        'club_id': g.get('club_id'),
        'club_name': g.get('club_name'),
        'club_token': g.get('club_token'),
        'city_name': g.get('city_name'),
        'price': g.get('price'),
        'extra_bands': g.get('extra_bands') or [],
    }


def group_gigs_by_year(gigs):
    """Group gigs by year (descending), sorted by date descending within year."""
    by_year = defaultdict(list)
    for g in gigs:
        d = parse_date(g.get('date'))
        if d:
            by_year[d.year].append(gig_to_display(g))
    result = []
    for year in sorted(by_year.keys(), reverse=True):
        year_gigs = sorted(by_year[year], key=lambda g: g['date'], reverse=True)
        result.append((year, year_gigs))
    return result


def gig_year_stats(gig_list):
    """Return [(year, count), ...] sorted by year descending."""
    by_year = defaultdict(int)
    for g in gig_list:
        d = parse_date(g.get('date'))
        if d:
            by_year[d.year] += 1
    return sorted(by_year.items(), reverse=True)


def clips_for_band(band):
    """Return web links and music clips separately."""
    web_links, youtube_clips, audio_clips, photo_clips = [], [], [], []
    clips = sorted(band.get('clips') or [], key=lambda c: (c.get('sort_order') or 0, c.get('name') or ''))
    for c in clips:
        t = c.get('type', '')
        if t == 'weblink':
            web_links.append(c)
        elif t == 'youtube':
            youtube_id = None
            url = c.get('url') or ''
            if 'youtube.com/watch?v=' in url:
                youtube_id = url.split('v=')[-1].split('&')[0]
            elif 'youtu.be/' in url:
                youtube_id = url.split('youtu.be/')[-1].split('?')[0]
            elif 'youtube.com/embed/' in url:
                youtube_id = url.split('embed/')[-1].split('?')[0]
            elif 'youtube.com/?' in url and 'v=' in url:
                # http://www.youtube.com/?v=KbrPrmC5OFw
                qs = parse_qs(urlparse(url).query)
                ids = qs.get('v', [])
                if ids:
                    youtube_id = ids[0]
            if youtube_id:
                youtube_clips.append({**c, 'youtube_id': youtube_id, 'li_class': 'video'})
        elif t in ('mp3', 'audio'):
            audio_clips.append({**c, 'li_class': 'sound'})
        elif t in ('photo', 'image'):
            photo_clips.append(c)
    return web_links, youtube_clips, audio_clips, photo_clips


def thumb_url_for(url):
    return url


def get_main_photo(clips_list):
    """Return first photo clip with a URL, or None (adds thumb_url field)."""
    for c in clips_list:
        if c.get('type') in ('photo', 'image') and c.get('url'):
            return {**c, 'thumb_url': thumb_url_for(c['url'])}
    return None


def build_item_pages(token, base_url, has_gigs, has_music, has_reviews):
    """Build the contextMenu pages list for a band."""
    pages = [{'url': base_url + '/', 'title': 'О группе', 'order': 0}]
    if has_gigs:
        pages.append({'url': base_url + '/gigs/', 'title': 'Концерты', 'order': 1})
    if has_music:
        pages.append({'url': base_url + '/music/', 'title': 'Музыка', 'order': 2})
    if has_reviews:
        pages.append({'url': base_url + '/reviews/', 'title': 'Рецензии', 'order': 3})
    return pages


def build_club_pages(token, base_url, has_gigs, has_reviews):
    pages = [{'url': base_url + '/', 'title': 'О клубе', 'order': 0}]
    if has_gigs:
        pages.append({'url': base_url + '/gigs/', 'title': 'Концерты', 'order': 1})
    if has_reviews:
        pages.append({'url': base_url + '/reviews/', 'title': 'Рецензии', 'order': 2})
    return pages


def format_review_text(text):
    """Convert raw DB text to HTML: double newline → paragraph break, single → <br>."""
    if not text:
        return ''
    import re
    # Normalise CRLF
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Split on blank lines → paragraphs
    paras = re.split(r'\n{2,}', text.strip())
    parts = []
    for p in paras:
        # Single newlines within a paragraph → <br>
        p = p.replace('\n', '<br/>')
        parts.append(f'<p>{p}</p>')
    return '\n'.join(parts)


def first_review_sample(reviews, max_chars=250):
    """Return first non-press-release review with text sample, or press-release if that's all."""
    if not reviews:
        return None, None
    sorted_reviews = sorted(reviews, key=lambda r: (not r.get('is_press_release', False), -(r.get('id') or 0)))
    for rev in sorted_reviews:
        text = rev.get('text') or ''
        if text:
            sample = text[:max_chars].rsplit(' ', 1)[0] + '…' if len(text) > max_chars else text
            return {**rev, 'text_sample': sample}, sorted_reviews
    return None, sorted_reviews


def compute_top_clubs_for_band(band_id, gigs_by_band_id, clubs_by_id, n=TOP_VENUES_COUNT):
    """Top clubs by gig count for a band."""
    counts = defaultdict(int)
    for g in gigs_by_band_id.get(band_id, []):
        cid = g.get('club_id')
        if cid:
            counts[cid] += 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:n]
    result = []
    for cid, _ in top:
        club = clubs_by_id.get(cid)
        if club:
            result.append({'name': club['name'], 'token': club['token']})
    return result


def compute_top_bands_for_club(club_id, gigs_by_club_id, bands_by_id, n=TOP_VENUES_COUNT):
    counts = defaultdict(int)
    for g in gigs_by_club_id.get(club_id, []):
        bid = g.get('band_id')
        if bid:
            counts[bid] += 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:n]
    result = []
    for bid, count in top:
        band = bands_by_id.get(bid)
        if band:
            result.append({'name': band['name'], 'token': band['token'], 'gig_count': count})
    return result


def paginate_list(items, page_size=ITEMS_PER_PAGE):
    """Split items into pages."""
    pages = []
    for i in range(0, max(1, len(items)), page_size):
        pages.append(items[i:i+page_size])
    return pages


def build_letter_index(items_sorted):
    """Build letter → page mapping for alphabetical navigation."""
    letters = []
    seen_chars = set()
    for i, item in enumerate(items_sorted):
        name = item.get('name') or ''
        first = name[0].upper() if name else ''
        if first and first not in seen_chars:
            seen_chars.add(first)
            page = i // ITEMS_PER_PAGE
            enc = first.lower().replace(' ', '_')
            letters.append({'char': first, 'enc': enc, 'page': page})
    return letters


def cyrillic_sort_key(s):
    """Sort key: skip leading punctuation/quotes so 'Band' sorts as 'Band'."""
    import re
    s = (s or '').lower()
    m = re.search(r'[a-zа-яё0-9]', s)
    if m:
        s = s[m.start():]
    return s


# ---------------------------------------------------------------------------
# Main generators
# ---------------------------------------------------------------------------

def generate_bands(env, bands, gigs_by_band, gigs_by_club, clubs_by_id, bands_by_id):
    print("  Generating band pages...")
    tmpl_main    = env.get_template('band.html.j2')
    tmpl_gigs    = env.get_template('band_gigs.html.j2')
    tmpl_reviews = env.get_template('band_reviews.html.j2')
    tmpl_music   = env.get_template('band_music.html.j2')

    for band in bands:
        token    = band['token']
        base_url = f"/band/{token}"
        bid      = band['id']

        web_links, youtube_clips, audio_clips, photo_clips = clips_for_band(band)
        main_photo = get_main_photo(photo_clips)

        has_gigs    = band['gig_count'] > 0
        has_music   = bool(youtube_clips or audio_clips)
        has_reviews = bool(band.get('reviews'))

        item_pages = build_item_pages(token, base_url, has_gigs, has_music, has_reviews)

        top_clubs = compute_top_clubs_for_band(bid, gigs_by_band, clubs_by_id)

        first_rev, all_revs = first_review_sample(band.get('reviews') or [])
        other_revs = [r for r in (all_revs or []) if r != first_rev] if first_rev else []

        main_yt = youtube_clips[0]['youtube_id'] if youtube_clips else None
        music_clips_nav = []
        for c in (youtube_clips + audio_clips)[:7]:
            li_cls = 'video' if c.get('type') == 'youtube' else 'sound'
            music_clips_nav.append({**c, 'li_class': li_cls})

        band_gig_list = sorted(gigs_by_band.get(bid, []), key=lambda g: g.get('date') or '', reverse=True)
        year_stats = gig_year_stats(band_gig_list)

        ctx = {
            'band': band,
            'page_seed': f"{page_seed(token):02d}",
            'item_title': band['name'],
            'item_type': 'band',
            'item_type_name': 'Группа',
            'item_alive': band['alive'],
            'item_categories': [
                {'url': f"/city/{band['city_token']}", 'title': band['city_name']}
            ] if band.get('city_token') else [],
            'item_pages': item_pages,
            'current_page_url': base_url + '/',
            'web_links': web_links,
            'main_photo': main_photo,
            'top_clubs': top_clubs,
            'first_review': first_rev,
            'first_review_section_title': 'В прессе' if first_rev and first_rev.get('is_press_release') else 'О группе',
            'other_reviews': other_revs,
            'main_youtube': main_yt,
            'music_clips': music_clips_nav,
            'year_stats': year_stats,
            'gigs_block_align': 'lBlock' if has_music else 'wBlock',
            'music_block_align': 'rBlock' if has_gigs else 'wBlock',
        }

        write_html(SITE / 'band' / token / 'index.html', tmpl_main.render(**ctx))

        # Gigs history page
        if has_gigs:
            gig_ctx = {
                **ctx,
                'current_page_url': base_url + '/gigs/',
                'gigs_by_year': group_gigs_by_year(band_gig_list),
            }
            write_html(SITE / 'band' / token / 'gigs' / 'index.html', tmpl_gigs.render(**gig_ctx))

        # Reviews page
        if has_reviews:
            rev_ctx = {
                **ctx,
                'current_page_url': base_url + '/reviews/',
                'reviews': [{**r, 'text': format_review_text(r.get('text') or '')}
                            for r in sorted(band.get('reviews') or [], key=lambda r: -(r.get('id') or 0))],
                'main_photo': main_photo,
            }
            write_html(SITE / 'band' / token / 'reviews' / 'index.html', tmpl_reviews.render(**rev_ctx))

        # Music page
        if has_music:
            mus_ctx = {
                **ctx,
                'current_page_url': base_url + '/music/',
                'youtube_clips': youtube_clips,
                'audio_clips': audio_clips,
            }
            write_html(SITE / 'band' / token / 'music' / 'index.html', tmpl_music.render(**mus_ctx))


def generate_clubs(env, clubs, gigs_by_club, bands_by_id):
    print("  Generating club pages...")
    tmpl_main    = env.get_template('club.html.j2')
    tmpl_gigs    = env.get_template('club_gigs.html.j2')
    tmpl_reviews = env.get_template('club_reviews.html.j2')

    for club in clubs:
        token    = club['token']
        base_url = f"/club/{token}"
        cid      = club['id']

        web_links = [c for c in (club.get('clips') or []) if c.get('type') == 'weblink']
        photo_clips = [c for c in (club.get('clips') or []) if c.get('type') in ('photo', 'image')]
        main_photo = get_main_photo(photo_clips)

        has_gigs    = club['gig_count'] > 0
        has_reviews = bool(club.get('reviews'))

        item_pages = build_club_pages(token, base_url, has_gigs, has_reviews)
        top_bands  = compute_top_bands_for_club(cid, gigs_by_club, bands_by_id)

        first_rev, all_revs = first_review_sample(club.get('reviews') or [])

        club_gig_list = sorted(gigs_by_club.get(cid, []), key=lambda g: g.get('date') or '', reverse=True)
        year_stats = gig_year_stats(club_gig_list)

        ctx = {
            'club': club,
            'page_seed': f"{page_seed(token):02d}",
            'item_title': club['name'],
            'item_type': 'club',
            'item_type_name': 'Клуб',
            'item_alive': club['alive'],
            'item_categories': [
                {'url': f"/city/{club['city_token']}", 'title': club['city_name']}
            ] if club.get('city_token') else [],
            'item_pages': item_pages,
            'current_page_url': base_url + '/',
            'web_links': web_links,
            'main_photo': main_photo,
            'top_bands': top_bands,
            'first_review': first_rev,
            'year_stats': year_stats,
        }

        write_html(SITE / 'club' / token / 'index.html', tmpl_main.render(**ctx))

        if has_gigs:
            gig_ctx = {
                **ctx,
                'current_page_url': base_url + '/gigs/',
                'gigs_by_year': group_gigs_by_year(club_gig_list),
            }
            write_html(SITE / 'club' / token / 'gigs' / 'index.html', tmpl_gigs.render(**gig_ctx))

        if has_reviews:
            rev_ctx = {
                **ctx,
                'current_page_url': base_url + '/reviews/',
                'reviews': [{**r, 'text': format_review_text(r.get('text') or '')}
                            for r in sorted(club.get('reviews') or [], key=lambda r: -(r.get('id') or 0))],
            }
            write_html(SITE / 'club' / token / 'reviews' / 'index.html', tmpl_reviews.render(**rev_ctx))


def generate_cities(env, cities, bands, clubs):
    print("  Generating city pages...")
    tmpl      = env.get_template('city.html.j2')
    tmpl_list = env.get_template('list_alpha.html.j2')

    bands_by_city  = defaultdict(list)
    for b in bands:
        if b.get('city_token'):
            bands_by_city[b['city_token']].append(b)

    clubs_by_city  = defaultdict(list)
    for c in clubs:
        if c.get('city_token'):
            clubs_by_city[c['city_token']].append(c)

    for city in cities:
        token = city.get('token') or city['name'].lower().replace(' ', '-')
        city = {**city, 'token': token}
        city_bands_alpha = sorted(bands_by_city.get(token, []), key=lambda b: cyrillic_sort_key(b['name']))
        city_clubs_alpha = sorted(clubs_by_city.get(token, []), key=lambda c: cyrillic_sort_key(c['name']))
        city_bands_top   = sorted(bands_by_city.get(token, []), key=lambda b: -(b.get('gig_count') or 0))
        city_clubs_top   = sorted(clubs_by_city.get(token, []), key=lambda c: -(c.get('gig_count') or 0))

        web_links = [c for c in (city.get('clips') or []) if c.get('type') == 'weblink']

        bands_alpha_ctx = [band_item_ctx(b) for b in city_bands_alpha]
        clubs_alpha_ctx = [club_item_ctx(c) for c in city_clubs_alpha]
        alpha_ru_b, alpha_latin_b = split_letter_index(city_bands_alpha)
        alpha_ru_c, alpha_latin_c = split_letter_index(city_clubs_alpha)

        ctx = {
            'city': city,
            'page_seed': f"{page_seed(token):02d}",
            'item_title': city['name'],
            'item_type': 'city',
            'item_type_name': 'Город',
            'item_alive': True,
            'item_categories': [],
            'item_pages': [{'url': f'/city/{token}/', 'title': 'О городе', 'order': 0}],
            'current_page_url': f'/city/{token}/',
            'web_links': web_links,
            'top_bands': city_bands_top[:TOP_LIST_COUNT],
            'top_clubs': city_clubs_top[:TOP_LIST_COUNT],
            'has_all_bands': bool(city_bands_alpha),
            'has_all_clubs': bool(city_clubs_alpha),
            'all_bands_url': f'/city/{token}/bands/',
            'all_clubs_url': f'/city/{token}/clubs/',
        }
        write_html(SITE / 'city' / token / 'index.html', tmpl.render(**ctx))

        if city_bands_alpha:
            by_letter = group_by_letter(bands_alpha_ctx)
            base_lctx = {
                'page_seed': ctx['page_seed'], 'list_title': city['name'],
                'list_type': 'bands', 'base_url': f'/city/{token}/bands',
                'alpha_ru': alpha_ru_b, 'alpha_latin': alpha_latin_b,
            }
            write_html(SITE / 'city' / token / 'bands' / 'index.html',
                       tmpl_list.render(**base_lctx, items=bands_alpha_ctx,
                                        current_letter='', page_title=f"Группы — {city['name']}"))
            for letter, letter_items in by_letter.items():
                write_html(SITE / 'city' / token / 'bands' / letter / 'index.html',
                           tmpl_list.render(**base_lctx, items=letter_items,
                                            current_letter=letter, page_title=f"Группы {city['name']} — {letter.upper()}"))

        if city_clubs_alpha:
            by_letter = group_by_letter(clubs_alpha_ctx)
            base_lctx = {
                'page_seed': ctx['page_seed'], 'list_title': city['name'],
                'list_type': 'clubs', 'base_url': f'/city/{token}/clubs',
                'alpha_ru': alpha_ru_c, 'alpha_latin': alpha_latin_c,
            }
            write_html(SITE / 'city' / token / 'clubs' / 'index.html',
                       tmpl_list.render(**base_lctx, items=clubs_alpha_ctx,
                                        current_letter='', page_title=f"Клубы — {city['name']}"))
            for letter, letter_items in by_letter.items():
                write_html(SITE / 'city' / token / 'clubs' / letter / 'index.html',
                           tmpl_list.render(**base_lctx, items=letter_items,
                                            current_letter=letter, page_title=f"Клубы {city['name']} — {letter.upper()}"))


def generate_genres(env, genres, bands):
    print("  Generating genre pages...")
    tmpl      = env.get_template('genre.html.j2')
    tmpl_list = env.get_template('list_alpha.html.j2')

    bands_by_genre = defaultdict(list)
    for b in bands:
        if b.get('genre_token'):
            bands_by_genre[b['genre_token']].append(b)
        if b.get('secondary_genre_token'):
            bands_by_genre[b['secondary_genre_token']].append(b)

    for genre in genres:
        token = genre['token']
        genre_bands_alpha = sorted(bands_by_genre.get(token, []), key=lambda b: cyrillic_sort_key(b['name']))
        genre_bands_top   = sorted(bands_by_genre.get(token, []), key=lambda b: -(b.get('gig_count') or 0))

        bands_alpha_ctx = [band_item_ctx(b) for b in genre_bands_alpha]
        alpha_ru, alpha_latin = split_letter_index(genre_bands_alpha)

        ctx = {
            'genre': genre,
            'page_seed': f"{page_seed(token):02d}",
            'item_title': genre['name'],
            'item_type': 'genre',
            'item_type_name': 'Жанр',
            'item_alive': True,
            'item_categories': [],
            'item_pages': [{'url': f'/genre/{token}/', 'title': 'О жанре', 'order': 0}],
            'current_page_url': f'/genre/{token}/',
            'top_bands': genre_bands_top[:TOP_LIST_COUNT],
            'all_bands_url': f'/genre/{token}/bands/',
            'has_all_bands': bool(genre_bands_alpha),
        }
        write_html(SITE / 'genre' / token / 'index.html', tmpl.render(**ctx))

        if genre_bands_alpha:
            by_letter = group_by_letter(bands_alpha_ctx)
            base_lctx = {
                'page_seed': ctx['page_seed'], 'list_title': genre['name'],
                'list_type': 'bands', 'base_url': f'/genre/{token}/bands',
                'alpha_ru': alpha_ru, 'alpha_latin': alpha_latin,
            }
            write_html(SITE / 'genre' / token / 'bands' / 'index.html',
                       tmpl_list.render(**base_lctx, items=bands_alpha_ctx,
                                        current_letter='', page_title=f"Группы — {genre['name']}"))
            for letter, letter_items in by_letter.items():
                write_html(SITE / 'genre' / token / 'bands' / letter / 'index.html',
                           tmpl_list.render(**base_lctx, items=letter_items,
                                            current_letter=letter, page_title=f"Группы {genre['name']} — {letter.upper()}"))


RU_LETTERS = set('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
TOP_LIST_COUNT = 30


def split_letter_index(items_sorted):
    """Return (ru_letters, latin_letters) — each a list of {char, enc} dicts.
    Uses the same stripping as cyrillic_sort_key so quoted names file under their real first letter."""
    import re
    ru, latin = [], []
    seen = set()
    for item in items_sorted:
        name = (item.get('name') or '').lower()
        m = re.search(r'[a-zа-яё0-9]', name)
        first = m.group(0).upper() if m else ''
        if first and first not in seen:
            seen.add(first)
            entry = {'char': first, 'enc': first.lower()}
            if first in RU_LETTERS:
                ru.append(entry)
            else:
                latin.append(entry)
    return ru, latin


def _letter_enc(name):
    """First meaningful letter for alphabetical bucketing, skipping leading punctuation/quotes."""
    import re
    s = (name or '').lower()
    m = re.search(r'[a-zа-яё0-9]', s)
    return m.group(0) if m else ''


def band_item_ctx(b):
    cats = []
    if b.get('city_token') and b.get('city_name'):
        cats.append({'url': f"/city/{b['city_token']}", 'title': b['city_name']})
    if b.get('genre_token') and b.get('genre_name'):
        cats.append({'url': f"/genre/{b['genre_token']}", 'title': b['genre_name']})
    if b.get('secondary_genre_token') and b.get('secondary_genre_name'):
        cats.append({'url': f"/genre/{b['secondary_genre_token']}", 'title': b['secondary_genre_name']})
    return {
        'title': b['name'], 'url': f"/band/{b['token']}",
        'categories': cats, 'description': None,
        'letter_enc': _letter_enc(b['name']), 'gig_count': b.get('gig_count', 0),
    }


def club_item_ctx(c):
    cats = []
    if c.get('city_token') and c.get('city_name'):
        cats.append({'url': f"/city/{c['city_token']}", 'title': c['city_name']})
    return {
        'title': c['name'], 'url': f"/club/{c['token']}",
        'categories': cats,
        'description': (c.get('comments') or '')[:60] or None,
        'letter_enc': _letter_enc(c['name']), 'gig_count': c.get('gig_count', 0),
    }


def group_by_letter(items_ctx):
    """Return {letter_lower: [items]} dict."""
    by_letter = defaultdict(list)
    for item in items_ctx:
        by_letter[item['letter_enc']].append(item)
    return by_letter


def generate_lists(env, bands, clubs, cities, genres):
    print("  Generating listing pages...")
    tmpl_top  = env.get_template('list_top.html.j2')
    tmpl_alpha = env.get_template('list_alpha.html.j2')
    tmpl_full  = env.get_template('list_full.html.j2')

    # ---- Band list ----
    bands_by_gigs  = sorted(bands, key=lambda b: -(b.get('gig_count') or 0))
    bands_alpha    = sorted(bands, key=lambda b: cyrillic_sort_key(b['name']))
    top_bands      = [band_item_ctx(b) for b in bands_by_gigs[:TOP_LIST_COUNT]]
    items_ctx      = [band_item_ctx(b) for b in bands_alpha]
    alpha_ru, alpha_latin = split_letter_index(bands_alpha)
    first_letter   = (alpha_ru or alpha_latin)[0]['enc'] if (alpha_ru or alpha_latin) else ''
    by_letter      = group_by_letter(items_ctx)

    ctx = {
        'page_seed': '01', 'list_title': 'Группы', 'list_type': 'bands',
        'base_url': '/all/bands',
        'top_items': top_bands, 'top_label': 'Самые активные группы',
        'alpha_ru': alpha_ru, 'alpha_latin': alpha_latin,
        'first_letter': first_letter,
    }
    write_html(SITE / 'all' / 'bands' / 'index.html', tmpl_top.render(**ctx))
    for letter, letter_items in by_letter.items():
        lctx = {**ctx, 'items': letter_items, 'current_letter': letter,
                'page_title': f"Группы — {letter.upper()}"}
        write_html(SITE / 'all' / 'bands' / letter / 'index.html', tmpl_alpha.render(**lctx))

    # ---- Club list ----
    clubs_by_gigs  = sorted(clubs, key=lambda c: -(c.get('gig_count') or 0))
    clubs_alpha    = sorted(clubs, key=lambda c: cyrillic_sort_key(c['name']))
    top_clubs      = [club_item_ctx(c) for c in clubs_by_gigs[:TOP_LIST_COUNT]]
    items_ctx      = [club_item_ctx(c) for c in clubs_alpha]
    alpha_ru, alpha_latin = split_letter_index(clubs_alpha)
    first_letter   = (alpha_ru or alpha_latin)[0]['enc'] if (alpha_ru or alpha_latin) else ''
    by_letter      = group_by_letter(items_ctx)

    ctx = {
        'page_seed': '02', 'list_title': 'Клубы', 'list_type': 'clubs',
        'base_url': '/all/clubs',
        'top_items': top_clubs, 'top_label': 'Самые активные клубы',
        'alpha_ru': alpha_ru, 'alpha_latin': alpha_latin,
        'first_letter': first_letter,
    }
    write_html(SITE / 'all' / 'clubs' / 'index.html', tmpl_top.render(**ctx))
    for letter, letter_items in by_letter.items():
        lctx = {**ctx, 'items': letter_items, 'current_letter': letter,
                'page_title': f"Клубы — {letter.upper()}"}
        write_html(SITE / 'all' / 'clubs' / letter / 'index.html', tmpl_alpha.render(**lctx))

    # ---- City list ----
    cities_sorted = sorted(
        [c for c in cities if c.get('token')],
        key=lambda c: cyrillic_sort_key(c['name']))
    items_ctx = [
        {'title': c['name'], 'url': f"/city/{c['token']}", 'categories': [],
         'description': f"{c['band_count']} групп, {c['club_count']} клубов" if c['band_count'] or c['club_count'] else None,
         'letter_enc': _letter_enc(c['name']), 'gig_count': 0}
        for c in cities_sorted
    ]
    alpha_ru, alpha_latin = split_letter_index(cities_sorted)
    ctx = {
        'page_seed': '03', 'list_title': 'Города', 'list_type': 'cities',
        'page_title': 'Города', 'items': items_ctx,
        'alpha_ru': alpha_ru, 'alpha_latin': alpha_latin,
    }
    write_html(SITE / 'all' / 'cities' / 'index.html', tmpl_full.render(**ctx))

    # ---- Genre list ----
    genres_sorted = sorted(genres, key=lambda g: cyrillic_sort_key(g['name']))
    items_ctx = [
        {'title': g['name'], 'url': f"/genre/{g['token']}", 'categories': [],
         'description': f"{g['band_count']} групп" if g['band_count'] else None,
         'letter_enc': _letter_enc(g['name']), 'gig_count': 0}
        for g in genres_sorted
    ]
    alpha_ru, alpha_latin = split_letter_index(genres_sorted)
    ctx = {
        'page_seed': '04', 'list_title': 'Жанры', 'list_type': 'genres',
        'page_title': 'Жанры', 'items': items_ctx,
        'alpha_ru': alpha_ru, 'alpha_latin': alpha_latin,
    }
    write_html(SITE / 'all' / 'genres' / 'index.html', tmpl_full.render(**ctx))


def generate_homepage(env, bands, clubs, cities, genres, gigs):
    print("  Generating homepage...")
    tmpl = env.get_template('homepage.html.j2')

    cities_with_bands = sorted(
        [c for c in cities if c['band_count'] > 0],
        key=lambda c: -c['band_count']
    )
    genres_with_bands = sorted(
        [g for g in genres if g['band_count'] > 0],
        key=lambda g: -g['band_count']
    )

    ctx = {
        'page_seed': '01',
        'band_count': len(bands),
        'club_count': len(clubs),
        'gig_count': len(gigs),
        'cities_with_bands': cities_with_bands,
        'genres_with_bands': genres_with_bands,
    }
    write_html(SITE / 'index.html', tmpl.render(**ctx))


def generate_about(env):
    print("  Generating about page...")
    tmpl = env.get_template('about.html.j2')
    ctx = {'page_seed': '06'}
    write_html(SITE / 'about' / 'index.html', tmpl.render(**ctx))



def copy_static():
    print("  Copying static assets...")
    dst = SITE
    src = STATIC
    if dst.exists():
        # remove only static dirs, not generated content
        for name in ('stage', 'images', 'js', 'css'):
            d = dst / name
            if d.exists():
                shutil.rmtree(d)
    for name in src.iterdir():
        s = src / name.name
        d = dst / name.name
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def main():
    print("Loading data...")
    bands  = load_entities('bands')
    clubs  = load_entities('clubs')
    cities = load_entities('cities')
    genres = load_entities('genres')
    gigs   = load_gigs()

    print(f"  {len(bands)} bands, {len(clubs)} clubs, {len(cities)} cities, {len(genres)} genres, {len(gigs)} gigs")

    enrich_data(bands, clubs, cities, genres, gigs)

    # Build lookup indexes
    bands_by_id = {b['id']: b for b in bands}
    clubs_by_id = {c['id']: c for c in clubs}

    gigs_by_band = defaultdict(list)
    gigs_by_club = defaultdict(list)
    for g in gigs:
        if g.get('band_id'):
            gigs_by_band[g['band_id']].append(g)
        if g.get('club_id'):
            gigs_by_club[g['club_id']].append(g)

    print("Setting up Jinja2...")
    env = Environment(
        loader=FileSystemLoader(str(TMPL)),
        autoescape=False,
    )

    SITE.mkdir(parents=True, exist_ok=True)

    copy_static()
    generate_homepage(env, bands, clubs, cities, genres, gigs)
    generate_about(env)
    generate_bands(env, bands, gigs_by_band, gigs_by_club, clubs_by_id, bands_by_id)
    generate_clubs(env, clubs, gigs_by_club, bands_by_id)
    generate_cities(env, cities, bands, clubs)
    generate_genres(env, genres, bands)
    generate_lists(env, bands, clubs, cities, genres)

    # Count output
    html_count = sum(1 for _ in SITE.rglob('*.html'))
    print(f"\nDone. {html_count} HTML pages → {SITE}/")


if __name__ == '__main__':
    main()
