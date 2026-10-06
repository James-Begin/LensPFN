"""Benchmark argument validation works without model or dataset downloads."""

import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import numpy as np

from lens.feedbench import _fit_predict, _shard_users


class BenchmarkShardTest(unittest.TestCase):
    def test_shards_partition_the_same_sorted_users(self):
        users = [8, 1, 4, 3, 2]
        shards = [_shard_users(users, f"{i}/3") for i in range(3)]
        self.assertEqual(shards, [[1, 4], [2, 8], [3]])
        self.assertEqual(sorted(u for shard in shards for u in shard), sorted(users))

    def test_invalid_shards_fail_instead_of_silently_skipping_users(self):
        for value in ["0/0", "-1/2", "2/2", "a/b", "0", "0/1/2"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "user-shard"):
                _shard_users([1, 2, 3], value)


class BenchmarkModelTest(unittest.TestCase):
    def test_fast_and_full_versions_keep_separate_cached_models(self):
        fast, full = object(), object()
        classifier = Mock()
        models = []

        def create(version, **kwargs):
            model = Mock(classes_=np.array([0, 1]))
            model.fit.return_value = model
            model.predict_proba.return_value = np.array([[0.25, 0.75]])
            models.append(model)
            return model

        classifier.create_default_for_version.side_effect = create
        state = {"device": "cpu"}
        with patch.dict(
            "sys.modules",
            {
                "tabpfn": SimpleNamespace(TabPFNClassifier=classifier),
                "tabpfn.constants": SimpleNamespace(
                    ModelVersion=SimpleNamespace(V3_5_FAST=fast, V3_5=full)
                ),
            },
        ):
            for learner in ["tabpfnfast", "tabpfn", "tabpfnfast"]:
                score = _fit_predict(
                    learner, np.zeros((2, 1)), np.array([0, 1]), np.zeros((1, 1)), state
                )
                np.testing.assert_equal(score, [0.75])
        self.assertEqual(
            [c.args[0] for c in classifier.create_default_for_version.call_args_list], [fast, full]
        )
        self.assertEqual(models[0].fit.call_count, 2)
        self.assertEqual(models[1].fit.call_count, 1)
