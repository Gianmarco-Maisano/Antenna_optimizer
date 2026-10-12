import os
import textwrap
import tempfile
import unittest

from optimizer import genetic_optimizer
from optimizer.NEC_tools import read_nec_output, read_nec_results, run_necpp
from optimizer.rf_metrics import realized_gain_db, transform_feed_impedance


class SolverReferenceTests(unittest.TestCase):
    def test_maximum_gain_uses_only_zero_to_180_azimuth_but_keeps_full_pattern(self):
        output = textwrap.dedent("""\
            RADIATION PATTERNS
            80.0 0.0 0.0 0.0 2.0
            80.0 90.0 0.0 0.0 6.0
            80.0 180.0 0.0 0.0 4.0
            80.0 270.0 0.0 0.0 99.0
            *****
            TOTAL RUN TIME
            """)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'pattern.out')
            with open(output_path, 'w', encoding='ascii') as output_file:
                output_file.write(output)

            result = read_nec_results(output_path)

        self.assertEqual(result['max_gain_db'], 6.0)
        self.assertEqual(len(result['radiation_pattern']), 4)
        self.assertEqual(result['radiation_pattern'][-1]['phi_deg'], 270.0)

    def test_optimizer_deck_uses_physical_theta_sweep_for_suspect_candidate(self):
        lengths = [0.9399321908, 0.2811085134, 0.9961755109]
        distances = [0.1820618070, 0.042]

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'input.nec')
            genetic_optimizer.create_nec_input(
                lengths,
                distances,
                input_path,
                144.0,
                min_spacing=0.042,
            )

            output_path = os.path.join(temp_dir, 'output.out')
            with open(input_path, encoding='ascii') as input_file:
                deck = input_file.read()
            self.assertIn('RP  0  1  72  1000 80.0000 0 0 5', deck)
            self.assertIn('GN  0  0  0  0  13.0000 0.005000', deck)

            _, error = run_necpp(input_path, output_path)
            self.assertEqual(error, '')
            parsed = read_nec_results(output_path)
            pattern = parsed['radiation_pattern']
            self.assertEqual(len(pattern), 72)
            self.assertTrue(all(sample['theta_deg'] == 80.0 for sample in pattern))
            self.assertEqual(pattern[0]['phi_deg'], 0.0)
            self.assertEqual(pattern[-1]['phi_deg'], 355.0)
            self.assertIsNotNone(parsed['real_impedance'])

    def test_coax_transform_has_zero_loss_when_disabled_and_changes_impedance_when_enabled(self):
        antenna_impedance = (42.0, -8.0)
        direct = transform_feed_impedance(*antenna_impedance, 144.0)
        coax = transform_feed_impedance(*antenna_impedance, 144.0, 3.5, 50.0, 0.66, 4.0, 1.0)
        self.assertEqual(direct, (42.0, -8.0, 0.0))
        self.assertGreater(coax[2], 0.0)
        self.assertNotAlmostEqual(coax[0], direct[0], places=3)

    def test_balun_impedance_ratio_is_applied_at_feed(self):
        transformed = transform_feed_impedance(200.0, 0.0, 144.0, balun_impedance_ratio=4.0)
        self.assertEqual(transformed, (50.0, 0.0, 0.0))

    def test_optimizer_feeds_center_element_for_seven_element_yagi(self):
        lengths = [0.30] * 7
        distances = [0.10] * 6

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'seven_element.nec')
            genetic_optimizer.create_nec_input(lengths, distances, input_path, 144.0, min_spacing=0.042)
            with open(input_path, encoding='ascii') as input_file:
                deck = input_file.read()

        self.assertIn('EX  0  4  5 0  1 0', deck)

    def test_reference_dipole_impedance_matches_upstream_values(self):
        deck = textwrap.dedent("""\
            CM
            CE
            GW 0 8 0 0 -.25 0 0 .25 .00001
            GE
            FR 0 1 0 0 200 0
            EX 5 0 5 1 1 0 50
            XQ
            EN
            """)
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "reference.nec")
            output_path = os.path.join(temp_dir, "reference.out")
            with open(input_path, "w", encoding="ascii") as input_file:
                input_file.write(deck)

            _, error = run_necpp(input_path, output_path)
            self.assertEqual(error, "")
            real_impedance, imag_impedance, _ = read_nec_output(output_path)

        self.assertAlmostEqual(real_impedance, 26.5762, delta=0.02)
        self.assertAlmostEqual(imag_impedance, -632.060, delta=0.1)

    def test_reference_grounded_antenna_gain_matches_upstream_value(self):
        deck = textwrap.dedent("""\
            CM
            CE
            GW 0 9 0 0 2 0 0 7 0.03
            GE 1
            EK
            FR 0 1 0 0 30 0
            EX 0 0 5 0 1 0
            GN 1
            RP 0 10 2 1301 0 0 10 90
            EN
            """)
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "grounded_reference.nec")
            output_path = os.path.join(temp_dir, "grounded_reference.out")
            with open(input_path, "w", encoding="ascii") as input_file:
                input_file.write(deck)

            _, error = run_necpp(input_path, output_path)
            self.assertEqual(error, "")
            real_impedance, imag_impedance, max_gain = read_nec_output(output_path)

        self.assertAlmostEqual(real_impedance, 83.755229, delta=0.01)
        self.assertAlmostEqual(imag_impedance, 45.322052, delta=0.01)
        self.assertAlmostEqual(max_gain, 8.393876, delta=0.02)


if __name__ == "__main__":
    unittest.main()