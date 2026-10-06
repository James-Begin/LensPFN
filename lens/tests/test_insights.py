from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import numpy as np

from lens.feed.insights import Insights
from lens.feed.bridge import Companion
from lens.feed.rank import Profile, FeedRanker
from test_rank import paper


class InsightsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.insights = Insights(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_predictions_are_prospective_frozen_and_persistent(self):
        self.insights.observe('old', 1)
        self.insights.forecasts([{'id': 'old', 'match': .99}, {'id': 'a', 'match': .85}, {'id': 'rated', 'match': .95}], {'rated'})
        self.insights.observe('a', -1)
        self.insights.forecasts([{'id': 'a', 'match': .99}], set())
        result = Insights(self.root).reliability()
        self.assertEqual((result['count'], result['liked']), (1, 0))
        self.assertEqual(result['mean_prediction'], .85)
        self.assertAlmostEqual(result['brier'], .85**2)
        self.assertEqual(self.insights.path.stat().st_mode & 0o777, 0o600)

    def test_boundary_invalid_predictions_and_rating_changes(self):
        self.insights.forecasts([{'id': str(i), 'match': score} for i, score in enumerate([.8, .799, float('nan'), 1.1, True])], set())
        self.insights.observe('0', 1)
        self.insights.observe('1', -1)
        self.assertEqual(self.insights.reliability()['count'], 1)
        self.assertEqual(self.insights.reliability()['liked'], 1)
        self.insights.observe('0', -1)
        self.assertEqual(self.insights.reliability()['liked'], 0)
        self.insights.observe('0', 0)
        self.assertEqual(self.insights.reliability()['count'], 0)
        self.assertEqual(self.insights.reliability()['rated_forecasts'], 1)

    def test_digest_is_opt_in_strictly_above_threshold_and_acknowledged(self):
        c = Companion(self.root/'profile', self.root/'cache')
        with patch.object(c, 'shortlist', return_value={'warning': ''}):
            c.scored_pool = [{**paper(i), 'match': score} for i, score in enumerate([.8, .8001, .9, .5])]
            self.assertFalse(c.digest()['enabled'])
            c.digest_preferences({'enabled': True})
            result = c.digest()
            self.assertEqual([p['match'] for p in result['papers']], [.9, .8001])
            self.assertEqual(len(c.digest()['new_ids']), 2)  # Reading is not delivery.
            with self.assertRaises(ValueError): c.digest_delivered({'ids': [paper(0)['id']]})
            c.scored_pool=[]  # Delivery acknowledgment survives a simultaneous rating/refresh.
            c.digest_delivered({'ids': result['new_ids']})
            self.assertEqual(c.digest()['new_ids'], [])
            self.assertEqual(Companion(self.root/'profile', self.root/'cache').insights.load()['delivered'], sorted(result['new_ids']))
            c.digest_preferences({'enabled': False})
            with self.assertRaises(ValueError): c.digest_delivered({'ids': []})
        for value in (1, 'true', None):
            with self.assertRaises(ValueError): c.digest_preferences({'enabled': value})

    def test_learning_pilot_uses_uncertainty_without_lowering_match_threshold(self):
        ranker = FeedRanker()
        model = Mock(classes_=np.array([0, 1]))
        model.predict_proba.return_value = np.array([[.51, .49]])
        ranker._model = model
        profile = Profile(likes=[paper(i) for i in range(3)], dislikes=[paper(i) for i in range(3, 6)])
        vectors = np.tile([[1., 0.]], (6, 1))
        regular = ranker.rank([paper(100)], vectors[:1], profile, vectors)
        self.assertTrue(np.isnan(regular.match[0]))
        model.fit.assert_not_called()
        pilot = ranker.rank([paper(100)], vectors[:1], profile, vectors, learning=True)
        self.assertAlmostEqual(pilot.match[0], .49)
        self.assertEqual(ranker.ready(profile), 24)

    def test_learning_selects_uncertain_diverse_unrated_papers_and_falls_back(self):
        c = Companion(self.root/'profile', self.root/'cache')
        rows = [paper(i) for i in range(16)]
        profile = Profile(likes=rows[:3], dislikes=rows[3:6])
        c.store.save_profile(profile)
        import json
        (c.store.root/'pool-test.json').write_text(json.dumps(rows))
        c.embedder = Mock()
        c.embedder.papers.side_effect = lambda papers: np.array([[1., 0.] if p['id'] == rows[6]['id'] else [0., 1.] for p in papers])
        ranker = Mock()
        # Highly certain paper 6 should lose to the uncertain group.
        ranker.rank.return_value = Mock(match=np.array([.99]+[.5]*9))
        c.rankers['tabpfn-fast'] = ranker
        with patch.object(c, 'status', return_value={'tabpfn_configured': True}):
            result = c.learning()
            self.assertEqual(result['strategy'], 'uncertainty')
            self.assertNotIn(rows[6]['id'], [p['id'] for p in result['papers']])
            self.assertEqual(len(set(p['id'] for p in result['papers'])), 6)
            self.assertTrue(all(p['match'] is None for p in result['papers']))
            self.assertFalse(set(p['id'] for p in result['papers']) & set(p['id'] for p in profile.labeled))
            self.assertEqual(c.insights.reliability()['rated_forecasts'], 0)
            c.learning_cache.clear()
            ranker.rank.side_effect = RuntimeError('test failure')
            result = c.learning()
            self.assertEqual(result['strategy'], 'diversity')
            self.assertEqual(len(result['papers']), 6)
            self.assertIn('unavailable', result['warning'])

if __name__ == '__main__':
    unittest.main()
