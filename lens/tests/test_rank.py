from datetime import date
import unittest
from unittest.mock import Mock

import numpy as np

from lens.feed.rank import FEATURES, PRODUCT_SIGNALS, FeedRanker, Profile, features, session_groups


def paper(i, day='2026-10-01'):
    return {'id':f'2401.{i:05d}', 'title':f'Paper {i}', 'abstract':'A ranking fixture.',
            'authors':[f'Author {i}'], 'primary':'cs.LG', 'categories':['cs.LG'],
            'created':'2024-01-01', 'rated_at':day}


class RankTest(unittest.TestCase):
    def test_model_starts_at_thirty_balanced_ratings_and_omits_age(self):
        rows=[paper(i) for i in range(30)]
        vectors=np.tile(np.array([[1.,0.]],dtype=np.float32),(30,1))
        pool=[paper(100)]
        ranker=FeedRanker()
        model=Mock(classes_=np.array([0,1]))
        model.predict_proba.return_value=np.array([[.2,.8]])
        ranker._model=model
        before=Profile(likes=rows[:26],dislikes=rows[26:29])
        result=ranker.rank(pool,vectors[:1],before,vectors[:29],None)
        self.assertEqual(result.engine,'similarity')
        self.assertTrue(np.isnan(result.match).all())
        model.fit.assert_not_called()
        ready=Profile(likes=rows[:27],dislikes=rows[27:])
        result=ranker.rank(pool,vectors[:1],ready,vectors,None)
        self.assertAlmostEqual(result.match[0],.8)
        self.assertEqual(model.fit.call_args.args[0].shape,(30,12))
        self.assertNotIn('days_old',PRODUCT_SIGNALS)

    def test_session_groups_keep_rating_days_or_cross_fit_one_session(self):
        rows=[paper(i) for i in range(10)]
        profile=Profile(likes=rows[:5],dislikes=rows[5:])
        days=[date(2026,10,1)]*10
        groups=session_groups(profile,days)
        self.assertEqual(len(set(groups)),5)
        self.assertTrue(all(groups.count(g)==2 for g in set(groups)))
        days=[date(2026,10,1+i%3) for i in range(10)]
        self.assertEqual(session_groups(profile,days),days)

    def test_history_features_hide_same_day_and_measure_age_at_rating_time(self):
        rows=[paper(0),paper(1),paper(2,'2026-10-02')]
        profile=Profile(likes=rows)
        vectors=np.array([[1.,0.],[1.,0.],[0.,1.]],dtype=np.float32)
        days=[date.fromisoformat(p['rated_at']) for p in rows]
        table=features(rows,vectors,profile,vectors,None,date(2026,10,4),
                       self_index=np.arange(3),as_of=days,groups=days,profile_groups=days)
        np.testing.assert_array_equal(table[:,FEATURES.index('sim_like_max')],[0.,0.,0.])
        np.testing.assert_array_equal(table[:,FEATURES.index('days_old')],
                                      [(d-date(2024,1,1)).days for d in days])


if __name__=='__main__':
    unittest.main()
