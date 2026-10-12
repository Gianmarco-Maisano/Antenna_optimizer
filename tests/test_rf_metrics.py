import unittest

from optimizer.rf_metrics import realized_gain_db, vswr_from_impedance


class RealizedGainTests(unittest.TestCase):
    def test_matched_load_keeps_power_gain(self):
        self.assertAlmostEqual(realized_gain_db(8.0, 50.0, 0.0), 8.0)

    def test_matched_impedance_has_unity_vswr(self):
        self.assertAlmostEqual(vswr_from_impedance(50.0, 0.0), 1.0)

    def test_strongly_mismatched_candidate_loses_feed_mismatch_power(self):
        realized = realized_gain_db(25.03, 6.6372, -539.31, 50.0)
        self.assertAlmostEqual(realized, 1.58, delta=0.02)

    def test_short_candidate_exceeds_three_to_one_vswr_gate(self):
        self.assertGreater(vswr_from_impedance(12.953, -353.53), 3.0)

    def test_matched_impedance_has_unity_vswr(self):
        self.assertAlmostEqual(vswr_from_impedance(50.0, 0.0), 1.0)

    def test_short_element_reactance_exceeds_configured_vswr_limit(self):
        self.assertGreater(vswr_from_impedance(12.953, -353.53), 3.0)


if __name__ == "__main__":
    unittest.main()