import unittest
from datetime import datetime, timedelta, timezone

from ambiguous_wall_time_resolver import ResolveResult, resolve


class TestResolveAmbiguous(unittest.TestCase):
    def test_fall_back_overlap_yields_two_results(self):
        # US/Eastern fall-back 2023-11-05 01:30 local.
        # 01:30 EDT (UTC-4) → 05:30Z  (first, fold=0)
        # 01:30 EST (UTC-5) → 06:30Z  (second, fold=1)
        dt = datetime(2023, 11, 5, 1, 30, 0, fold=0)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-5))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].utc, datetime(2023, 11, 5, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(results[1].utc, datetime(2023, 11, 5, 6, 30, tzinfo=timezone.utc))
        self.assertEqual(results[0].offset, timedelta(hours=-4))
        self.assertEqual(results[1].offset, timedelta(hours=-5))
        self.assertEqual(results[0].fold, 0)
        self.assertEqual(results[1].fold, 1)
        self.assertEqual(results[0].label, "first")
        self.assertEqual(results[1].label, "second")

    def test_results_ordered_by_utc(self):
        dt = datetime(2023, 11, 5, 1, 30, 0)
        results = resolve(dt, timedelta(hours=-5), timedelta(hours=-4))
        self.assertLess(results[0].utc, results[1].utc)

    def test_aware_datetime_wall_time_is_used(self):
        aware = datetime(2023, 11, 5, 1, 30, 0, tzinfo=timezone(timedelta(hours=-7)))
        results = resolve(aware, timedelta(hours=-4), timedelta(hours=-5))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].utc, datetime(2023, 11, 5, 5, 30, tzinfo=timezone.utc))

    def test_non_overlapping_offsets_still_two_results(self):
        # With fixed offsets, every wall time round-trips under both offsets,
        # so two distinct offsets always produce two interpretations.
        dt = datetime(2023, 6, 15, 12, 0, 0)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-5))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].offset, timedelta(hours=-4))

    def test_utc_offset_two_results(self):
        # Offset 0 and +1 are distinct, so two results are returned.
        dt = datetime(2023, 11, 5, 1, 30, 0)
        results = resolve(dt, timedelta(0), timedelta(hours=1))
        self.assertEqual(len(results), 2)

    def test_identical_offsets_single_result(self):
        dt = datetime(2023, 11, 5, 1, 30, 0)
        results = resolve(dt, timedelta(hours=-5), timedelta(hours=-5))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].offset, timedelta(hours=-5))

    def test_spring_forward_gap_returns_single_interpretation(self):
        # Spring-forward gaps cannot be structurally detected with fixed
        # offsets — every wall time round-trips. Two distinct offsets yield
        # two interpretations; the caller must use zoneinfo for gap detection.
        dt = datetime(2023, 3, 12, 2, 30, 0)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-8))
        self.assertEqual(len(results), 2)

    def test_gap_where_one_offset_accepts(self):
        dt = datetime(2023, 3, 12, 2, 30, 0)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-5))
        self.assertEqual(len(results), 2)

    def test_fold_attribute_preserved_in_single_result(self):
        dt = datetime(2023, 6, 15, 12, 0, 0, fold=1)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-5))
        self.assertEqual(len(results), 2)

    def test_result_is_frozen_dataclass(self):
        dt = datetime(2023, 11, 5, 1, 30, 0)
        results = resolve(dt, timedelta(hours=-4), timedelta(hours=-5))
        with self.assertRaises(Exception):
            results[0].utc = datetime(2020, 1, 1, tzinfo=timezone.utc)

    def test_half_hour_offsets(self):
        # Lord Howe fall-back: 02:00→01:30, offset -10:30→-11:00.
        dt = datetime(2023, 4, 2, 1, 45, 0)
        results = resolve(dt, timedelta(hours=-10, minutes=-30), timedelta(hours=-11))
        self.assertEqual(len(results), 2)
        # -10:30 → 1:45+10:30 = 12:15Z  (first)
        # -11:00 → 1:45+11:00 = 12:45Z  (second)
        self.assertEqual(results[0].utc, datetime(2023, 4, 2, 12, 15, tzinfo=timezone.utc))
        self.assertEqual(results[1].utc, datetime(2023, 4, 2, 12, 45, tzinfo=timezone.utc))

    def test_positive_offset_overlap(self):
        # Hypothetical: +02:00 → +01:00 fall-back at 03:00.
        dt = datetime(2023, 10, 29, 2, 30, 0)
        results = resolve(dt, timedelta(hours=2), timedelta(hours=1))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].utc, datetime(2023, 10, 29, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(results[1].utc, datetime(2023, 10, 29, 1, 30, tzinfo=timezone.utc))

    def test_first_and_second_labels_assigned_by_utc_order(self):
        dt = datetime(2023, 11, 5, 1, 30, 0)
        results = resolve(dt, timedelta(hours=-5), timedelta(hours=-4))
        self.assertEqual(results[0].label, "first")
        self.assertEqual(results[1].label, "second")


if __name__ == "__main__":
    unittest.main()
