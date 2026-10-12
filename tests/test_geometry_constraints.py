import unittest

from optimizer.geometry_constraints import minimum_center_spacing, repair_individual, validate_individual


class GeometryConstraintTests(unittest.TestCase):
    def test_three_centimeter_clearance_includes_both_wire_radii(self):
        self.assertAlmostEqual(minimum_center_spacing(0.03), 0.042)

    def test_repair_clamps_crossover_spacings_to_required_clearance(self):
        individual = [0.30, 0.40, 0.60, 0.01, 0.30]
        required_spacing = minimum_center_spacing(0.03)

        repaired = repair_individual(
            individual,
            num_elements=3,
            min_length=0.25,
            max_length=0.50,
            min_spacing=required_spacing,
            max_spacing=0.20,
        )

        self.assertEqual(repaired, 3)
        self.assertEqual(individual, [0.30, 0.40, 0.50, required_spacing, 0.20])
        validate_individual(individual, num_elements=3, min_spacing=required_spacing)

    def test_impossible_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "below the required minimum"):
            repair_individual([0.3, 0.3, 0.1], 2, 0.25, 0.5, 0.15, 0.1)


if __name__ == "__main__":
    unittest.main()