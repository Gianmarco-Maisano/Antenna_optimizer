import sys
import configparser
import json
import math
import pandas as pd
import matplotlib.pyplot as plt
import os
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QRadioButton, QLineEdit, QPushButton, QProgressBar, QMessageBox,
    QTabWidget, QFileDialog, QCheckBox
)

from optimizer import genetic_optimizer
from config_writer import update_config


class OptimizationWorker(QThread):
    progress_changed = Signal(int, str)
    optimization_completed = Signal()
    optimization_failed = Signal(str)

    def __init__(self, mode, parent=None):
        super().__init__(parent)
        self.mode = mode

    def run(self):
        try:
            genetic_optimizer.run_optimization(mode=self.mode, status_callback=self.report_status)
            self.optimization_completed.emit()
        except Exception as error:
            self.optimization_failed.emit(str(error))

    def report_status(self, status):
        generation = status['generation']
        total_generations = status['total_generations']
        progress = round(100 * generation / max(total_generations, 1))
        if status['phase'] == 'initializing':
            message = f"Preparing population | clear gap {100 * status['clearance_m']:.1f} cm"
        else:
            message = (
                f"Generation {generation}/{total_generations} | {status['evaluations']} simulations | "
                f"{status['feasible']}/{status['population_size']} valid | "
                f"{status['repaired_genes']} genes repaired | best realized gain {status['best_gain']:.2f} dBi"
            )
        self.progress_changed.emit(progress, message)


class OptimizerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.config = configparser.ConfigParser()
        self.config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

        self.setWindowTitle("Yagi Antenna Optimization")
        self.setGeometry(100, 100, 600, 700)

        tabs = QTabWidget()

        # Tabs
        self.simulation_tab = QWidget()
        self.advanced_tab = QWidget()
        self.installation_tab = QWidget()
        self.paths_tab = QWidget()
        self.output_tab = QWidget()

        tabs.addTab(self.simulation_tab, "Simulation")
        tabs.addTab(self.advanced_tab, "Advanced")
        tabs.addTab(self.installation_tab, "Installation")
        tabs.addTab(self.paths_tab, "Paths")
        tabs.addTab(self.output_tab, "Output")

        # Build Tabs
        self.build_simulation_tab()
        self.build_advanced_tab()
        self.build_installation_tab()
        self.build_paths_tab()
        self.build_output_tab()

        # Main Layout
        layout = QVBoxLayout()
        layout.addWidget(tabs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Ready")

        self.start_button = QPushButton("Start Optimization")
        self.start_button.clicked.connect(self.start_optimization_thread)

        self.plot_button = QPushButton("Show Plot")
        self.plot_button.clicked.connect(self.show_plot)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.start_button)
        layout.addWidget(self.plot_button)

        self.setLayout(layout)

        self.update_mode_state()

    # ---------------- Simulation Tab ----------------
    def build_simulation_tab(self):
        layout = QVBoxLayout()

        self.mode_single = QRadioButton("Single Frequency")
        self.mode_sweep = QRadioButton("Frequency Sweep")
        self.mode_single.setChecked(True)

        self.mode_single.toggled.connect(self.update_mode_state)
        self.mode_sweep.toggled.connect(self.update_mode_state)

        layout.addWidget(QLabel("Select Mode:"))
        layout.addWidget(self.mode_single)
        layout.addWidget(self.mode_sweep)

        simulation = self.config['Simulation']
        genetic = self.config['GeneticAlgorithm']
        self.freq_entry = self.create_entry("Central Frequency (MHz)", simulation.get('frequency', '144.0'))
        self.min_freq_entry = self.create_entry("Sweep Minimum Frequency (MHz)", simulation.get('min_freq', '143.0'))
        self.max_freq_entry = self.create_entry("Sweep Maximum Frequency (MHz)", simulation.get('max_freq', '145.0'))
        self.num_steps_entry = self.create_entry("Number of Sweep Steps", simulation.get('num_freq_steps', '3'))

        self.pop_size_entry = self.create_entry("Population Size", genetic.get('population_size', '50'))
        self.num_gen_entry = self.create_entry("Number of Generations", genetic.get('num_generations', '100'))

        layout.addLayout(self.freq_entry["layout"])
        layout.addLayout(self.min_freq_entry["layout"])
        layout.addLayout(self.max_freq_entry["layout"])
        layout.addLayout(self.num_steps_entry["layout"])
        layout.addLayout(self.pop_size_entry["layout"])
        layout.addLayout(self.num_gen_entry["layout"])

        layout.addStretch()  # <-- fills vertical space so it looks balanced
        self.simulation_tab.setLayout(layout)


    # ---------------- Advanced Tab ----------------
    def build_advanced_tab(self):
        layout = QVBoxLayout()

        simulation = self.config['Simulation']
        genetic = self.config['GeneticAlgorithm']
        self.k_start_entry = self.create_entry("k_start", simulation.get('k_start', '-1'))
        self.k_stop_entry = self.create_entry("k_stop", simulation.get('k_stop', '1'))
        self.k_step_entry = self.create_entry("k_step", simulation.get('k_step', '0.05'))

        self.num_elements_entry = self.create_entry("Number of Elements", genetic.get('num_elements', '3'))
        self.min_length_entry = self.create_entry("Min Length", genetic.get('min_length', '0.85'))
        self.max_length_entry = self.create_entry("Max Length", genetic.get('max_length', '1.05'))
        self.total_distance_entry = self.create_entry("Total Distance", genetic.get('total_distance', '1.0'))
        minimum_clearance = self.config.get('GeneticAlgorithm', 'minimum_element_clearance_m', fallback='0.03')
        self.minimum_clearance_entry = self.create_entry("Minimum Element Clearance (m)", minimum_clearance)

        self.lock_lengths_entry = QCheckBox("Lock Lengths")
        self.lock_lengths_entry.setChecked(genetic.getboolean('lock_lengths', False))
        self.lock_distances_entry = QCheckBox("Lock Distances")
        self.lock_distances_entry.setChecked(genetic.getboolean('lock_distances', False))

        self.crossover_prob_entry = self.create_entry("Crossover Probability", genetic.get('crossover_probability', '0.2'))
        self.mutation_prob_entry = self.create_entry("Mutation Probability", genetic.get('mutation_probability', '0.1'))
        self.target_imp_entry = self.create_entry("Target Real Impedance", genetic.get('target_real_impedance', '50'))
        maximum_vswr = genetic.get('maximum_vswr', '3.0')
        self.maximum_vswr_entry = self.create_entry("Maximum VSWR", maximum_vswr)
        self.imp_tolerance_entry = self.create_entry("Impedance Tolerance", genetic.get('impedance_tolerance', '5'))

        for item in [
            self.k_start_entry, self.k_stop_entry, self.k_step_entry,
            self.num_elements_entry, self.min_length_entry, self.max_length_entry,
            self.total_distance_entry, self.minimum_clearance_entry, self.crossover_prob_entry,
            self.mutation_prob_entry, self.target_imp_entry, self.maximum_vswr_entry,
            self.imp_tolerance_entry
        ]:
            layout.addLayout(item["layout"])

        layout.addWidget(self.lock_lengths_entry)
        layout.addWidget(self.lock_distances_entry)

        self.advanced_tab.setLayout(layout)

      # ---------------- Paths Tab ----------------
    def build_paths_tab(self):
        layout = QVBoxLayout()

        paths = self.config['Paths']
        self.input_dir_entry = self.create_browse_entry("Input Directory", paths.get('input_dir', 'optimizer/data'), directory=True)
        self.output_dir_entry = self.create_browse_entry("Output Directory", paths.get('output_dir', 'optimizer/data'), directory=True)
        self.main_input_file_entry = self.create_browse_entry("Main Input File", paths.get('main_input_file', 'input.nec'), directory=False)
        self.main_output_file_entry = self.create_browse_entry("Main Output File", paths.get('main_output_file', 'output.out'), directory=False)

        # aggiungo al layout tutte le entry
        for item in [
            self.input_dir_entry, self.output_dir_entry,
            self.main_input_file_entry, self.main_output_file_entry
        ]:
            layout.addLayout(item["layout"])

        layout.addStretch()  # spinge tutto verso l’alto e bilancia
        self.paths_tab.setLayout(layout)

    def build_installation_tab(self):
        layout = QVBoxLayout()
        simulation = self.config['Simulation']
        genetic = self.config['GeneticAlgorithm']

        self.antenna_height_entry = self.create_entry(
            "Antenna height above ground (m)", simulation.get('antenna_height_m', '2.0')
        )
        self.ground_permittivity_entry = self.create_entry(
            "Ground relative permittivity", simulation.get('ground_relative_permittivity', '13.0')
        )
        self.ground_conductivity_entry = self.create_entry(
            "Ground conductivity (S/m)", simulation.get('ground_conductivity_s_per_m', '0.005')
        )
        self.pattern_elevation_entry = self.create_entry(
            "Azimuth pattern elevation above horizon (degrees)", simulation.get('pattern_elevation_deg', '10.0')
        )
        self.coax_enabled_entry = QCheckBox("Include coax feedline")
        self.coax_enabled_entry.setChecked(genetic.getboolean('coax_enabled', False))
        self.coax_length_entry = self.create_entry("Coax length (m)", genetic.get('coax_length_m', '10.0'))
        self.coax_impedance_entry = self.create_entry("Coax characteristic impedance (Ohm)", genetic.get('coax_impedance_ohm', '50.0'))
        self.coax_velocity_entry = self.create_entry("Coax velocity factor", genetic.get('coax_velocity_factor', '0.66'))
        self.coax_loss_entry = self.create_entry("Coax loss (dB/100 m)", genetic.get('coax_loss_db_per_100m', '15.0'))
        self.balun_ratio_entry = self.create_entry(
            "Balun impedance ratio (antenna/radio)", genetic.get('balun_impedance_ratio', '1.0')
        )
        self.coax_fields = [
            self.coax_length_entry['entry'],
            self.coax_impedance_entry['entry'],
            self.coax_velocity_entry['entry'],
            self.coax_loss_entry['entry'],
        ]
        self.coax_enabled_entry.toggled.connect(self.update_coax_controls)
        self.update_coax_controls()

        for entry in (
            self.antenna_height_entry,
            self.ground_permittivity_entry,
            self.ground_conductivity_entry,
            self.pattern_elevation_entry,
            self.coax_length_entry,
            self.coax_impedance_entry,
            self.coax_velocity_entry,
            self.coax_loss_entry,
            self.balun_ratio_entry,
        ):
            layout.addLayout(entry['layout'])
        layout.addWidget(self.coax_enabled_entry)
        self.installation_tab.setLayout(layout)

    def update_coax_controls(self):
        enabled = self.coax_enabled_entry.isChecked()
        for field in self.coax_fields:
            field.setEnabled(enabled)
    # ---------------- Output Tab ----------------
    def build_output_tab(self):
        layout = QVBoxLayout()

        output = self.config['Output']
        self.csv_output_entry = self.create_browse_entry("CSV Output File", output.get('csv_output_file', 'optimized_individuals.csv'), directory=False)
        history_file = self.config.get('Output', 'history_output_file', fallback='optimization_history.csv')
        self.history_output_entry = self.create_browse_entry("Generation History CSV", history_file, directory=False)
        self.enable_plots_entry = QCheckBox("Enable Plots")
        self.enable_plots_entry.setChecked(output.getboolean('enable_plots', True))

        layout.addLayout(self.csv_output_entry["layout"])
        layout.addLayout(self.history_output_entry["layout"])
        layout.addWidget(self.enable_plots_entry)

        self.output_tab.setLayout(layout)

    # ---------------- Utility Methods ----------------
    def create_entry(self, label_text, default_value):
        label = QLabel(label_text)
        entry = QLineEdit()
        entry.setText(default_value)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(entry)
        return {"layout": layout, "entry": entry}

    def create_browse_entry(self, label_text, default_value, directory=False):
        label = QLabel(label_text)
        entry = QLineEdit()
        entry.setText(default_value)
        browse = QPushButton("Browse")

        def browse_action():
            if directory:
                path = QFileDialog.getExistingDirectory(self, f"Select {label_text}")
            else:
                path, _ = QFileDialog.getOpenFileName(self, f"Select {label_text}")
            if path:
                entry.setText(path)

        browse.clicked.connect(browse_action)

        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(entry)
        layout.addWidget(browse)

        return {"layout": layout, "entry": entry}

    def update_mode_state(self):
        """Enable/disable fields depending on selected mode."""
        sweep_enabled = self.mode_sweep.isChecked()
        self.min_freq_entry["entry"].setEnabled(sweep_enabled)
        self.max_freq_entry["entry"].setEnabled(sweep_enabled)
        self.num_steps_entry["entry"].setEnabled(sweep_enabled)

    # ---------------- Optimization Methods ----------------
    def start_optimization_thread(self):
        mode = "single" if self.mode_single.isChecked() else "sweep"
        try:
            self.save_all_to_config(mode)
        except Exception as error:
            QMessageBox.critical(self, "Invalid settings", str(error))
            return

        self.start_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting optimizer...")
        self.worker = OptimizationWorker(mode, self)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.optimization_completed.connect(self.optimization_completed)
        self.worker.optimization_failed.connect(self.optimization_failed)
        self.worker.start()

    def save_all_to_config(self, mode):
        # --- Simulation ---
        update_config('Simulation', 'frequency', self.freq_entry["entry"].text())
        update_config('Simulation', 'antenna_height_m', self.antenna_height_entry["entry"].text())
        update_config('Simulation', 'ground_relative_permittivity', self.ground_permittivity_entry["entry"].text())
        update_config('Simulation', 'ground_conductivity_s_per_m', self.ground_conductivity_entry["entry"].text())
        update_config('Simulation', 'pattern_elevation_deg', self.pattern_elevation_entry["entry"].text())
        if mode == "sweep":
            update_config('Simulation', 'min_freq', self.min_freq_entry["entry"].text())
            update_config('Simulation', 'max_freq', self.max_freq_entry["entry"].text())
            update_config('Simulation', 'num_freq_steps', self.num_steps_entry["entry"].text())

        # --- Genetic Algorithm ---
        update_config('GeneticAlgorithm', 'num_elements', self.num_elements_entry["entry"].text())
        update_config('GeneticAlgorithm', 'min_length', self.min_length_entry["entry"].text())
        update_config('GeneticAlgorithm', 'max_length', self.max_length_entry["entry"].text())
        update_config('GeneticAlgorithm', 'total_distance', self.total_distance_entry["entry"].text())
        update_config('GeneticAlgorithm', 'minimum_element_clearance_m', self.minimum_clearance_entry["entry"].text())
        update_config('GeneticAlgorithm', 'lock_lengths', str(self.lock_lengths_entry.isChecked()))
        update_config('GeneticAlgorithm', 'lock_distances', str(self.lock_distances_entry.isChecked()))
        update_config('GeneticAlgorithm', 'population_size', self.pop_size_entry["entry"].text())
        update_config('GeneticAlgorithm', 'num_generations', self.num_gen_entry["entry"].text())
        update_config('GeneticAlgorithm', 'crossover_probability', self.crossover_prob_entry["entry"].text())
        update_config('GeneticAlgorithm', 'mutation_probability', self.mutation_prob_entry["entry"].text())
        update_config('GeneticAlgorithm', 'target_real_impedance', self.target_imp_entry["entry"].text())
        update_config('GeneticAlgorithm', 'maximum_vswr', self.maximum_vswr_entry["entry"].text())
        update_config('GeneticAlgorithm', 'coax_enabled', str(self.coax_enabled_entry.isChecked()))
        update_config('GeneticAlgorithm', 'coax_length_m', self.coax_length_entry["entry"].text())
        update_config('GeneticAlgorithm', 'coax_impedance_ohm', self.coax_impedance_entry["entry"].text())
        update_config('GeneticAlgorithm', 'coax_velocity_factor', self.coax_velocity_entry["entry"].text())
        update_config('GeneticAlgorithm', 'coax_loss_db_per_100m', self.coax_loss_entry["entry"].text())
        update_config('GeneticAlgorithm', 'balun_impedance_ratio', self.balun_ratio_entry["entry"].text())
        update_config('GeneticAlgorithm', 'impedance_tolerance', self.imp_tolerance_entry["entry"].text())

        # --- Paths ---
        update_config('Paths', 'input_dir', self.input_dir_entry["entry"].text())
        update_config('Paths', 'output_dir', self.output_dir_entry["entry"].text())
        update_config('Paths', 'main_input_file', self.main_input_file_entry["entry"].text())
        update_config('Paths', 'main_output_file', self.main_output_file_entry["entry"].text())

        # --- Output ---
        update_config('Output', 'csv_output_file', self.csv_output_entry["entry"].text())
        update_config('Output', 'history_output_file', self.history_output_entry["entry"].text())
        update_config('Output', 'enable_plots', str(self.enable_plots_entry.isChecked()))


    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        if message:
            self.status_label.setText(message)

    def optimization_completed(self):
        self.start_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText("Optimization complete. Results and generation history saved.")

    def optimization_failed(self, message):
        self.start_button.setEnabled(True)
        self.status_label.setText("Optimization failed.")
        QMessageBox.critical(self, "Optimization failed", message)

    def show_plot(self):
        try:
            csv_path = self.csv_output_entry["entry"].text()
            if not os.path.isabs(csv_path):
                csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), csv_path)
            history_path = self.history_output_entry["entry"].text()
            if not os.path.isabs(history_path):
                history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), history_path)

            population = pd.read_csv(csv_path)
            history = pd.read_csv(history_path)
            required_columns = {
                'Power Gain (dBi)', 'Realized Gain (dBi)',
                'Antenna Feed Impedance Real (Ohm)', 'Antenna Feed Impedance Imaginary (Ohm)',
                'Radio Input Impedance Real (Ohm)', 'Radio Input Impedance Imaginary (Ohm)',
                'VSWR at Radio', 'Maximum Sweep VSWR', 'Coax Loss (dB)',
                'Pattern Frequency (MHz)', 'Pattern Elevation (deg)', 'Radiation Pattern JSON',
            }
            if not required_columns.issubset(population.columns):
                raise ValueError("Results lack installation, impedance or pattern data. Run a new optimization to regenerate them.")
            figure = plt.figure(figsize=(14, 10))
            grid = figure.add_gridspec(2, 2, height_ratios=(1.0, 1.15))
            convergence_axis = figure.add_subplot(grid[0, 0])
            pattern_axis = figure.add_subplot(grid[0, 1], projection='polar')
            scatter_axis = figure.add_subplot(grid[1, 0])
            geometry_grid = grid[1, 1].subgridspec(2, 1, height_ratios=(0.76, 0.24), hspace=0.24)
            geometry_axis = figure.add_subplot(geometry_grid[0, 0])
            details_axis = figure.add_subplot(geometry_grid[1, 0])

            convergence_axis.plot(history['Generation'], history['Best Realized Gain (dBi)'], label='Best realized')
            convergence_axis.plot(history['Generation'], history['Average Realized Gain (dBi)'], label='Average realized')
            convergence_axis.plot(history['Generation'], history['Average Power Gain (dBi)'], label='Average power gain', linestyle=':')
            convergence_axis.set(title='Realized gain by generation', xlabel='Generation', ylabel='Gain (dBi)')
            convergence_axis.legend()
            convergence_axis.grid(True, alpha=0.3)

            pattern_axis.set_title('Selected azimuth pattern (0-360 deg)')
            pattern_axis.set_theta_zero_location('E')
            pattern_axis.set_theta_direction(1)
            pattern_axis.set_thetagrids(range(0, 360, 30))
            pattern_axis.set_ylabel('Total power gain (dBi)')
            pattern_axis.grid(True, alpha=0.3)

            feasible_population = population[population['Realized Gain (dBi)'] > -999].reset_index(drop=True)
            if feasible_population.empty:
                raise ValueError("No valid simulated individuals are available to plot.")
            scatter = scatter_axis.scatter(
                feasible_population['Real Impedance Penalty'],
                feasible_population['Realized Gain (dBi)'],
                c=feasible_population['Imaginary Impedance Penalty'], cmap='viridis', picker=True,
            )
            scatter_axis.set(title='Final population: click a solution', xlabel='Real impedance penalty (Ohm)', ylabel='Realized gain (dBi)')
            figure.colorbar(scatter, ax=scatter_axis, label='Imaginary penalty (Ohm)')
            scatter_axis.grid(True, alpha=0.3)

            geometry_axis.set_title('Selected geometry')
            geometry_axis.set_xlabel('Boom axis (m)')
            geometry_axis.set_ylabel('Element axis (m)')
            geometry_axis.set_aspect('equal', adjustable='datalim')
            geometry_axis.grid(True, alpha=0.3)
            details_axis.set_axis_off()
            length_columns = sorted((column for column in population.columns if column.startswith('Length')), key=lambda column: int(column.removeprefix('Length')))
            spacing_columns = sorted((column for column in population.columns if column.startswith('Distance')), key=lambda column: int(column.removeprefix('Distance')))

            def show_solution(solution_index):
                solution = feasible_population.iloc[solution_index]
                positions = [0.0]
                for spacing_column in spacing_columns:
                    positions.append(positions[-1] + float(solution[spacing_column]))
                geometry_axis.clear()
                geometry_axis.set_title('Selected geometry')
                geometry_axis.set_xlabel('Boom axis (m)')
                geometry_axis.set_ylabel('Element axis (m)')
                geometry_axis.set_aspect('equal', adjustable='datalim')
                geometry_axis.grid(True, alpha=0.3)
                for index, length_column in enumerate(length_columns):
                    half_length = float(solution[length_column]) / 2
                    geometry_axis.plot([positions[index], positions[index]], [-half_length, half_length], color='#d95f02' if index == 1 else '#2878a0', linewidth=3)
                    geometry_axis.text(positions[index], half_length, str(index + 1), ha='center', va='bottom')

                pattern = json.loads(solution['Radiation Pattern JSON'])
                pattern_axis.clear()
                pattern_axis.set_title(f"Azimuth at {float(solution['Pattern Frequency (MHz)']):.3f} MHz, elevation={float(solution['Pattern Elevation (deg)']):.1f} deg")
                pattern_axis.set_theta_zero_location('E')
                pattern_axis.set_theta_direction(1)
                pattern_axis.set_thetagrids(range(0, 360, 30))
                pattern_axis.grid(True, alpha=0.3)
                azimuth_rad = [math.radians(sample['phi_deg']) for sample in pattern]
                power_gain = [sample['total_gain_dbi'] for sample in pattern]
                azimuth_rad.append(2 * math.pi)
                power_gain.append(power_gain[0])
                radial_floor = min(0.0, min(power_gain))
                radii = [gain - radial_floor for gain in power_gain]
                pattern_axis.plot(azimuth_rad, radii, color='#2878a0')
                pattern_axis.set_ylim(0, max(radii) * 1.12 if max(radii) else 1)
                radial_ticks = pattern_axis.get_yticks()
                pattern_axis.set_yticklabels([f'{tick + radial_floor:.1f}' for tick in radial_ticks])
                evaluated_hemisphere = [sample for sample in pattern if 0.0 <= sample['phi_deg'] <= 180.0]
                peak = max(evaluated_hemisphere, key=lambda sample: sample['total_gain_dbi'])
                peak_radius = peak['total_gain_dbi'] - radial_floor
                pattern_axis.scatter([math.radians(peak['phi_deg'])], [peak_radius], color='#d95f02', zorder=3)
                pattern_axis.annotate(f"max 0-180: {peak['total_gain_dbi']:.2f} dBi @ {peak['phi_deg']:.1f} deg", (math.radians(peak['phi_deg']), peak_radius), xytext=(8, 8), textcoords='offset points')

                dimensions = '  '.join(f'L{index + 1} {float(solution[column]):.3f} m' for index, column in enumerate(length_columns))
                spacings = '  '.join(f'd{index + 1} {float(solution[column]):.3f} m' for index, column in enumerate(spacing_columns))
                details_axis.clear()
                details_axis.set_axis_off()
                details_axis.text(0.01, 0.95,
                    f"Z antenna: {float(solution['Antenna Feed Impedance Real (Ohm)']):.2f} {float(solution['Antenna Feed Impedance Imaginary (Ohm)']):+.2f}j Ohm  |  "
                    f"Z radio: {float(solution['Radio Input Impedance Real (Ohm)']):.2f} {float(solution['Radio Input Impedance Imaginary (Ohm)']):+.2f}j Ohm  |  "
                    f"VSWR {float(solution['VSWR at Radio']):.2f}:1  |  coax loss {float(solution['Coax Loss (dB)']):.2f} dB\n{dimensions}\n{spacings}",
                    transform=details_axis.transAxes, ha='left', va='top', fontsize=8)
                figure.canvas.draw_idle()

            def on_solution_pick(event):
                if event.artist is scatter and len(event.ind):
                    show_solution(int(event.ind[0]))

            figure.canvas.mpl_connect('pick_event', on_solution_pick)
            show_solution(int(feasible_population['Realized Gain (dBi)'].idxmax()))
            figure.tight_layout()
            if hasattr(self, 'plot_window'):
                self.plot_window.close()
            self.plot_window = QDialog(self)
            self.plot_window.setWindowTitle('Optimization results')
            self.plot_window.resize(1400, 1000)
            plot_layout = QVBoxLayout(self.plot_window)
            plot_layout.addWidget(NavigationToolbar2QT(figure.canvas, self.plot_window))
            plot_layout.addWidget(figure.canvas)
            self.plot_window.show()

        except Exception as error:
            QMessageBox.critical(self, "Error", f"Error while displaying plot:\n{error}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OptimizerGUI()
    window.show()
    sys.exit(app.exec())
