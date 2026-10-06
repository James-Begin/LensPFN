"""Private, prospective prediction history and opt-in digest delivery state."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path


class Insights:
    def __init__(self, root: Path):
        self.path = root / 'insights.json'

    def load(self):
        if not self.path.exists():
            return {'digest_enabled': False, 'forecasts': {}, 'delivered': [], 'offered': []}
        data = json.loads(self.path.read_text())
        data.setdefault('offered', [])
        return data

    def save(self, data):
        temp = self.path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, allow_nan=False)
        temp.replace(self.path)

    def forecasts(self, rows, rated_ids):
        """Freeze the first genuine prediction before feedback, never backfill history."""
        data = self.load()
        changed = False
        for row in rows:
            score = row.get('match')
            pid = row['id']
            if pid in rated_ids or pid in data['forecasts']:
                continue
            if not isinstance(score, (float, int)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1:
                continue
            data['forecasts'][pid] = {'score': float(score), 'predicted_at': datetime.now(timezone.utc).isoformat(), 'rating': 0}
            changed = True
        if changed:
            self.save(data)

    def observe(self, pid, rating):
        data = self.load()
        # A feedback-only entry blocks any later, contaminated prediction backfill.
        entry = data['forecasts'].setdefault(pid, {'score': None})
        entry['rating'] = rating
        self.save(data)

    def reliability(self):
        rows = [r for r in self.load()['forecasts'].values()
                if r.get('score') is not None and r.get('rating') in (-1, 1)]
        high = [r for r in rows if r['score'] >= .8]
        count = len(high)
        return {'count': count, 'liked': sum(r['rating'] == 1 for r in high),
                'mean_prediction': sum(r['score'] for r in high) / count if count else None,
                'rated_forecasts': len(rows),
                'brier': sum((r['score'] - (r['rating'] == 1)) ** 2 for r in rows) / len(rows) if rows else None}

    def configure(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Digest preference must be true or false.')
        data = self.load()
        data['digest_enabled'] = enabled
        self.save(data)

    def offer(self, ids):
        data = self.load()
        offered = set(data['offered']) | set(ids)
        if offered != set(data['offered']):
            data['offered'] = sorted(offered)
            self.save(data)

    def delivered(self, ids):
        data = self.load()
        data['delivered'] = sorted(set(data['delivered']) | set(ids))
        self.save(data)
