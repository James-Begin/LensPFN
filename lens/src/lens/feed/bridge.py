"""Authenticated loopback companion for the Lens arXiv extension.

Run from the project root: python -m lens.feed.bridge
"""
from __future__ import annotations

import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit, parse_qs

import numpy as np
from lens.feed.embed import Embedder
from lens.feed.rank import FeedRanker, Profile, explain
from lens.feed.sources import fetch_paper, harvest, recent_window, TOP_LEVEL_SETS, cached_papers
from lens.feed.store import Store, rate, unrate
from lens.feed.references import resolve, title_key
from lens.feed.access import configure_token
from difflib import SequenceMatcher

ID_PATTERN = re.compile(r'(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\Z')


def paper_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError('Use a valid arXiv paper ID.')
    return re.sub(r'v\d+$', '', value)


class Companion:
    def __init__(self, root: Path, cache: Path, device='cpu'):
        self.store = Store(root)
        self.cache, self.device = cache, device
        self.tabpfn_token_path=Path(os.environ.get('LENS_TABPFN_TOKEN_FILE',Path.home()/'.cache/tabpfn/auth_token'))
        self.lock = threading.RLock()
        self.reference_papers = cached_papers(cache/'arxiv')
        for path in (cache/'reference-papers').glob('*.json'):
            try:
                paper = json.loads(path.read_text())
                pid = paper_id(paper['id'])
                if paper.get('source') == 'datacite' and paper.get('title') and paper.get('abstract'):
                    self.reference_papers[pid] = paper
            except (OSError,ValueError,KeyError,TypeError):
                continue
        self.embedder = None
        self.rankers = {}
        self.revision = 0
        self.ranking_cache = {}
        self.paper_score_cache = {}
        self.citation_session = secrets.token_hex(8)
        self.citation_revision = 0
        self.citation_changes = 0
        self.citation_profile = None
        self.citation_stamp = None
        self.refresh_state = {'state': 'idle'}
        self.refresh_lock = threading.Lock()
        token_path = root / 'bridge-token'
        if not token_path.exists():
            fd = os.open(token_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(secrets.token_urlsafe(32))
        self.token = token_path.read_text().strip()

    def _reset_citations(self, profile):
        self.citation_revision += 1
        self.citation_changes = 0
        self.paper_score_cache.clear()
        self.citation_profile = profile
        self.citation_stamp = self.store.profile_path.stat().st_mtime_ns if self.store.profile_path.exists() else 0

    def _sync_citations(self, profile):
        stamp = self.store.profile_path.stat().st_mtime_ns if self.store.profile_path.exists() else 0
        if self.citation_profile is None:
            self.citation_profile = profile
            self.citation_stamp = stamp
        elif stamp != self.citation_stamp:
            # Changes made outside the companion cannot be counted safely.
            self._reset_citations(profile)

    def status(self):
        with self.lock:
            p = self.store.load_profile()
            self._sync_citations(p)
            pool, name = self.store.latest_pool()
            ranker = FeedRanker()
            return {'likes': len(p.likes), 'dislikes': len(p.dislikes),
                    'need_ratings': ranker.ready(p), 'match_after': ranker.match_after,
                    'need_likes': max(0, ranker.min_each-len(p.likes)),
                    'need_dislikes': max(0, ranker.min_each-len(p.dislikes)),
                    'interests': p.interests, 'pool_count': len(pool), 'pool_name': name,
                    'categories': sorted({c for row in pool for c in row['categories']}),
                    'ratings': {row['id']: 1 for row in p.likes} | {row['id']: -1 for row in p.dislikes},
                    'refresh': dict(self.refresh_state), 'revision': self.revision,
                    'citation_revision': self.citation_revision, 'citation_changes': self.citation_changes,
                    'citation_session': self.citation_session, 'citation_day': date.today().isoformat(),
                    'citation_refresh_after': 5,
                    'tabpfn_configured': bool(os.environ.get('TABPFN_TOKEN') or
                        self.tabpfn_token_path.exists())}

    def configure_access(self, data):
        configure_token(data.get('token'),self.tabpfn_token_path)
        with self.lock:
            self.ranking_cache.clear()
            self.paper_score_cache.clear()
            self.rankers.clear()
            self._reset_citations(self.store.load_profile())
        return self.status()

    def update_rating(self, data):
        pid = paper_id(data.get('id'))
        value = data.get('rating')
        if type(value) is not int or value not in (-1, 0, 1):
            raise ValueError('Rating must be -1, 0, or 1.')
        with self.lock:
            p = self.store.load_profile()
            self._sync_citations(p)
            before = 1 if any(row['id'] == pid for row in p.likes) else (-1 if any(row['id'] == pid for row in p.dislikes) else 0)
            if before == value:
                return self.status()
            was_ready = FeedRanker().ready(p) == 0
            if value == 0:
                p = unrate(p, pid)
            else:
                pool, _ = self.store.latest_pool()
                paper = next((x for x in p.labeled + pool if x['id'] == pid), None)
                # Use canonical arXiv metadata instead of trusting arbitrary page text.
                if paper is None:
                    paper = fetch_paper(pid, self.cache/'arxiv')
                p = rate(p, paper, liked=value == 1)
            self.store.save_profile(p)
            self.revision += 1
            self.ranking_cache.clear()
            self.citation_stamp = self.store.profile_path.stat().st_mtime_ns
            self.citation_changes += 1
            if self.citation_changes >= 5 or was_ready != (FeedRanker().ready(p) == 0):
                self._reset_citations(p)
            return self.status()

    def paper(self, value):
        """Canonical metadata for a cited arXiv paper, including papers outside the feed."""
        pid = paper_id(value)
        with self.lock:
            profile = self.store.load_profile()
            pool, _ = self.store.latest_pool()
            found = next((row for row in profile.labeled + pool if row['id'] == pid), None)
            found = found if found is not None else self.reference_papers.get(pid)
        return found if found is not None else fetch_paper(pid, self.cache/'arxiv')

    def resolve_reference(self, data):
        fields = {}
        for key, limit in [('title',500),('authors',500),('year',4),('doi',200),('reference',3000)]:
            value = data.get(key, '')
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError('Reference metadata is invalid or too long.')
            fields[key] = value.strip()
        if fields['doi'] and not re.fullmatch(r'10\.\d{4,9}/\S+', fields['doi'], re.I):
            raise ValueError('Use a valid DOI.')
        with self.lock:
            profile = self.store.load_profile()
            pool, _ = self.store.latest_pool()
            local = profile.labeled+pool+list(self.reference_papers.values())
        try:
            result = resolve(fields, self.cache/'references', local)
            if result['state'] == 'resolved':
                metadata_failed = False
                for candidate in result['candidates']:
                    if candidate.get('source') == 'datacite' and candidate.get('abstract'):
                        # arXiv's registered DOI deposits already include title,
                        # authors and abstract; reuse them for scoring and saving.
                        pid = paper_id(candidate['id'])
                        canonical = candidate
                        with self.lock:
                            self.reference_papers[pid] = canonical
                            folder = self.cache/'reference-papers'
                            folder.mkdir(parents=True,exist_ok=True)
                            path = folder/(pid.replace('/','-')+'.json')
                            temp = path.with_suffix('.tmp')
                            temp.write_text(json.dumps(canonical));temp.replace(path)
                    else:
                        try:
                            canonical = self.paper(candidate['id'])
                        except Exception as error:
                            logging.warning('Citation metadata lookup failed: %s',type(error).__name__)
                            metadata_failed = True
                            continue
                    if SequenceMatcher(None,title_key(candidate['title']),title_key(canonical['title'])).ratio() >= .8:
                        return {**result, 'candidates': [canonical]}
                if metadata_failed:
                    return {'state':'unavailable','candidates':[],
                            'warning':'An arXiv version was found, but its paper details could not load. Try hovering again shortly.'}
                return {'state': 'unresolved', 'candidates': [],
                        'warning': 'No matching arXiv version found. You can search by title or paste an arXiv URL.'}
            return result
        except Exception as error:
            logging.warning('Reference resolution failed: %s',type(error).__name__)
            return {'state': 'unavailable', 'candidates': [],
                    'warning': 'Reference lookup is unavailable or busy. You can still search by title or paste an arXiv URL.'}

    def paper_match(self, value):
        """Score a citation independently of the feed shortlist, without its own label."""
        paper = self.paper(value)
        with self.lock:
            profile = self.store.load_profile()
            rating = 1 if any(p['id'] == paper['id'] for p in profile.likes) else (
                -1 if any(p['id'] == paper['id'] for p in profile.dislikes) else 0)
            self._sync_citations(profile)
            snapshot = self.citation_profile
            context = Profile(likes=[p for p in snapshot.likes if p['id'] != paper['id']],
                              dislikes=[p for p in snapshot.dislikes if p['id'] != paper['id']],
                              interests=snapshot.interests)
            ranker = self.rankers.setdefault('tabpfn-fast', FeedRanker(
                engine='tabpfn-fast', device=self.device, shortlist=300))
            result = {'id': paper['id'], 'rating': rating, 'match': None, 'warning': '',
                      'citation_revision': self.citation_revision}
            if ranker.ready(context):
                result['warning'] = ('Keep rating papers to unlock a match estimate.' if not rating else
                    'More ratings are needed to estimate this paper without using its own rating.')
                return result
            if not self.status()['tabpfn_configured']:
                result['warning'] = 'Connect TabPFN to see a match estimate.'
                return result
            key = (self.citation_revision, paper['id'], date.today())
            if key in self.paper_score_cache:
                return {**self.paper_score_cache[key], 'rating': rating}
            try:
                if self.embedder is None:
                    self.embedder = Embedder(self.cache/'feed', self.device)
                V = self.embedder.papers([paper])
                PV = self.embedder.papers(context.labeled)
                q = self.embedder.query(context.interests) if context.interests else None
                ranked = ranker.rank([paper], V, context, PV, q)
                if np.isfinite(ranked.match[0]):
                    result['match'] = float(ranked.match[0])
            except Exception:
                result['warning'] = 'Match estimate unavailable. You can still save this paper.'
            # Retain scores across papers and across up to five rating changes.
            if len(self.paper_score_cache) >= 2048:
                self.paper_score_cache.pop(next(iter(self.paper_score_cache)))
            if result['match'] is not None:
                self.paper_score_cache[key] = result
            return result

    def interests(self, text):
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError('Interests must be at most 2,000 characters.')
        with self.lock:
            p = self.store.load_profile()
            p.interests = text.strip()
            self.store.save_profile(p)
            self.revision += 1
            self.ranking_cache.clear()
            self._reset_citations(p)
            return self.status()

    def library(self):
        with self.lock:
            p = self.store.load_profile()
            papers = [{**x, 'rating': 1} for x in p.likes] + [{**x, 'rating': -1} for x in p.dislikes]
            papers.sort(key=lambda x: x.get('rated_at_time') or x.get('rated_at', ''), reverse=True)
            return {'papers': papers}

    def shortlist(self, category=''):
        if len(category) > 40:
            raise ValueError('Invalid category.')
        with self.lock:
            p = self.store.load_profile()
            pool, name = self.store.latest_pool()
            if category:
                pool = [x for x in pool if category in x['categories']]
            exclude = self.store.hidden() | {x['id'] for x in p.labeled}
            pool = [x for x in pool if x['id'] not in exclude]
            stamp = self.store.profile_path.stat().st_mtime_ns if self.store.profile_path.exists() else 0
            key = (self.revision, stamp, name, category, len(pool))
            if key in self.ranking_cache:
                return self.ranking_cache[key]
            if not pool:
                return {'papers': [], 'engine': 'similarity', 'personalized': bool(p.labeled or p.interests), 'warning': ''}
            warning = ''
            if not p.labeled and not p.interests:
                # New profiles have no personalized signal. Say so and avoid a pointless model download.
                rows = sorted(pool, key=lambda x: (x['created'], x['id']), reverse=True)[:20]
                result = {'papers': [{**x, 'match': None, 'reason': 'New in your selected subject'} for x in rows],
                          'engine': 'recent', 'personalized': False, 'warning': ''}
            else:
                if self.embedder is None:
                    self.embedder = Embedder(self.cache/'feed', self.device)
                V = self.embedder.papers(pool)
                PV = self.embedder.papers(p.labeled) if p.labeled else np.zeros((0, V.shape[1]), np.float32)
                q = self.embedder.query(p.interests) if p.interests else None
                engine = 'tabpfn-fast' if self.status()['tabpfn_configured'] else 'similarity'
                ranker = self.rankers.setdefault(engine, FeedRanker(engine=engine, device=self.device, shortlist=300))
                if engine == 'similarity' and ranker.ready(p) == 0:
                    warning = 'Your profile is ready. Configure TabPFN access to enable match probabilities; similarity ranking is active.'
                try:
                    ranked = ranker.rank(pool, V, p, PV, q)
                except Exception:
                    if engine == 'similarity':
                        raise
                    warning = 'TabPFN could not score this batch. Showing similarity ranking; check model access and the companion log.'
                    ranked = FeedRanker(engine='similarity').rank(pool, V, p, PV, q)
                order = np.argsort(-ranked.scores, kind='stable')[:20]
                rows = []
                for i in order:
                    why = explain(pool[i], V[i], p, PV)
                    reason = ('Similar to '+why['closest_like'][0]) if 'closest_like' in why else 'Related to your interests'
                    rows.append({**pool[i], 'match': None if np.isnan(ranked.match[i]) else float(ranked.match[i]), 'reason': reason})
                result = {'papers': rows, 'engine': ranked.engine, 'personalized': True, 'warning': warning}
            self.ranking_cache = {key: result}
            return result

    def refresh(self, archive, days):
        if archive not in TOP_LEVEL_SETS or type(days) is not int or not 1 <= days <= 14:
            raise ValueError('Choose a supported archive and 1–14 days.')
        with self.refresh_lock:
            if self.refresh_state['state'] == 'running':
                return dict(self.refresh_state)
            self.refresh_state = {'state': 'running', 'count': 0}
        def job():
            try:
                start, end = recent_window(days)
                def progress(page, n):
                    self.refresh_state = {'state': 'running', 'count': n}
                papers = harvest(archive, start, end, self.cache/'arxiv', progress=progress)
                with self.lock:
                    path = self.store.pool_path(archive, start, end)
                    tmp = path.with_suffix('.tmp')
                    tmp.write_text(json.dumps(papers))
                    tmp.replace(path)
                    self.revision += 1
                    self.ranking_cache.clear()
                self.refresh_state = {'state': 'done', 'count': len(papers)}
            except Exception:
                self.refresh_state = {'state': 'error', 'message': 'arXiv could not be refreshed. Your previous feed is still available.'}
        threading.Thread(target=job, daemon=True).start()
        return dict(self.refresh_state)


def make_handler(companion, assets):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log authorization headers, user interests, or pairing keys.

        def allowed(self):
            origin = self.headers.get('Origin', '')
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                return False
            return not origin or origin == f'http://{host}' or bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin))

        def reply(self, status, data, mime='application/json'):
            body = json.dumps(data, allow_nan=False).encode() if mime == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            origin = self.headers.get('Origin', '')
            if self.allowed() and origin:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.reply(204 if self.allowed() else 403, b'', 'text/plain')

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def dispatch(self):
            if not self.allowed():
                return self.reply(403, {'error': 'Origin or host not allowed.'})
            url = urlsplit(self.path)
            if self.command == 'GET' and url.path == '/api/session':
                # Only the same-origin local preview can bootstrap its pairing key.
                if self.headers.get('Sec-Fetch-Site') != 'same-origin':
                    return self.reply(403, {'error': 'Open the local companion page to pair.'})
                return self.reply(200, {'token': companion.token})
            if self.command == 'GET' and url.path == '/setup-preview':
                path=assets/'panel.html'
                if not path.is_file():return self.reply(404,{'error':'Panel assets not found.'})
                page=path.read_text().replace('<script type="module"','<script src="/setup-runtime.js"></script><script type="module"',1)
                return self.reply(200,page.encode(),'text/html')
            assets_map = {'/': 'panel.html', '/panel.html': 'panel.html', '/panel.css': 'panel.css', '/panel.js': 'panel.js', '/icons.js': 'icons.js', '/list-motion.js': 'list-motion.js', '/onboarding.js': 'onboarding.js', '/citation-prefetch.js': 'citation-prefetch.js', '/citation-recommendations.js': 'citation-recommendations.js', '/recommendation-popup.js': 'recommendation-popup.js', '/reference-parser.js': 'reference-parser.js', '/citations.js': 'citations.js', '/citation-popup.js': 'citation-popup.js'}
            assets_map.update({'/html/citation-preview':'../tests/fixtures/citation-preview.html',
                              '/fixture-runtime.js':'../tests/fixtures/citation-runtime.js',
                              '/fixture.css':'../tests/fixtures/citation-preview.css',
                              '/setup-runtime.js':'../tests/fixtures/setup-runtime.js'})
            if self.command == 'GET' and url.path in assets_map:
                path = assets/assets_map[url.path]
                if path.is_file():
                    return self.reply(200, path.read_bytes(), mimetypes.guess_type(path)[0] or 'text/plain')
                return self.reply(404, {'error': 'Panel assets not found.'})
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+companion.token):
                return self.reply(401, {'error': 'Connect Lens with the pairing key from the local companion.'})
            try:
                if self.command == 'GET':
                    if url.path == '/api/status':
                        return self.reply(200, companion.status())
                    if url.path == '/api/library':
                        return self.reply(200, companion.library())
                    if url.path == '/api/paper':
                        return self.reply(200, companion.paper(parse_qs(url.query).get('id', [''])[0]))
                    if url.path == '/api/paper-match':
                        return self.reply(200, companion.paper_match(parse_qs(url.query).get('id', [''])[0]))
                    if url.path == '/api/shortlist':
                        return self.reply(200, companion.shortlist(parse_qs(url.query).get('category', [''])[0]))
                else:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 8192:
                        raise ValueError('Request is empty or too large.')
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict):
                        raise ValueError('Expected a JSON object.')
                    if url.path == '/api/resolve-reference':
                        return self.reply(200, companion.resolve_reference(data))
                    if url.path == '/api/tabpfn-access':
                        return self.reply(200, companion.configure_access(data))
                    if url.path == '/api/rate':
                        return self.reply(200, companion.update_rating(data))
                    if url.path == '/api/interests':
                        return self.reply(200, companion.interests(data.get('interests')))
                    if url.path == '/api/refresh':
                        return self.reply(202, companion.refresh(data.get('archive', 'cs'), data.get('days', 3)))
                return self.reply(404, {'error': 'Unknown endpoint.'})
            except (ValueError, TypeError, KeyError) as exc:
                return self.reply(400, {'error': str(exc)})
            except Exception as exc:
                print(f'Companion request failed: {type(exc).__name__}', flush=True)
                return self.reply(503, {'error': 'Lens could not finish this request. Check the companion terminal and try again.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('LENS_FEED_HOME', '.lens-feed')))
    parser.add_argument('--cache', type=Path, default=Path('.cache'))
    parser.add_argument('--device', default='cpu', choices=['cpu', 'mps', 'cuda'])
    parser.add_argument('--assets', type=Path, default=Path('extension'))
    args = parser.parse_args()
    c = Companion(args.root, args.cache, args.device)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(c, args.assets))
    print(f'Lens companion: http://127.0.0.1:{args.port} (local only)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
