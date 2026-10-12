import configparser
import csv
import os
import tempfile
import unittest
from unittest.mock import patch

from optimizer.genetic_optimizer import run_optimization


class OptimizerSmokeTests(unittest.TestCase):
    def test_small_run_keeps_clearance_and_writes_history(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini'))
        progress_events = []

        with tempfile.TemporaryDirectory() as temp_dir:
            config['Paths']['input_dir'] = temp_dir
            config['Paths']['output_dir'] = temp_dir
            config['Paths']['main_input_file'] = 'smoke.nec'
            config['Paths']['main_output_file'] = 'smoke.out'
            config['Output']['csv_output_file'] = os.path.join(temp_dir, 'population.csv')
            config['Output']['history_output_file'] = os.path.join(temp_dir, 'history.csv')
            config['GeneticAlgorithm']['num_elements'] = '3'
            config['GeneticAlgorithm']['population_size'] = '4'
            config['GeneticAlgorithm']['num_generations'] = '1'
            config['GeneticAlgorithm']['minimum_element_clearance_m'] = '0.03'
            config['GeneticAlgorithm']['wire_radius_m'] = '0.006'
            config['GeneticAlgorithm']['maximum_vswr'] = '100.0'

            with patch('optimizer.genetic_optimizer.configparser.ConfigParser', return_value=config):
                with patch.object(config, 'read', return_value=[]):
                    population, _, _ = run_optimization(
                        mode='single',
                        status_callback=progress_events.append,
                    )

            required_center_spacing = 0.03 + 2 * 0.006
            self.assertTrue(all(all(gap >= required_center_spacing for gap in individual[3:]) for individual in population))
            self.assertTrue(all(individual.fitness.values[0] > -999 for individual in population))
            self.assertTrue(all(individual.vswr <= 3.0 for individual in population))
            self.assertTrue(os.path.isfile(os.path.join(temp_dir, 'population.csv')))
            self.assertTrue(os.path.isfile(os.path.join(temp_dir, 'history.csv')))
            with open(os.path.join(temp_dir, 'population.csv'), newline='') as result_file:
                result_header = next(csv.reader(result_file))
                self.assertIn('VSWR at Radio', result_header)
                self.assertIn('Pattern Elevation (deg)', result_header)
            self.assertEqual(progress_events[-1]['generation'], 1)
            self.assertEqual(progress_events[-1]['feasible'], len(population))


if __name__ == '__main__':
    unittest.main()