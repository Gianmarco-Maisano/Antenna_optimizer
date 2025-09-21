import sys
import threading
import pandas as pd
import matplotlib.pyplot as plt
import os

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QRadioButton, QLineEdit, QPushButton, QProgressBar, QMessageBox,
    QTabWidget, QFileDialog, QCheckBox
)

from optimizer import genetic_optimizer
from config_writer import update_config


class OptimizerGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Yagi Antenna Optimization")
        self.setGeometry(100, 100, 600, 700)

        tabs = QTabWidget()

        # Tabs
        self.simulation_tab = QWidget()
        self.advanced_tab = QWidget()
        self.paths_tab = QWidget()
        self.output_tab = QWidget()

        tabs.addTab(self.simulation_tab, "Simulation")
        tabs.addTab(self.advanced_tab, "Advanced")
        tabs.addTab(self.paths_tab, "Paths")
        tabs.addTab(self.output_tab, "Output")

        # Build Tabs
        self.build_simulation_tab()
        self.build_advanced_tab()
        self.build_paths_tab()
        self.build_output_tab()

        # Main Layout
        layout = QVBoxLayout()
        layout.addWidget(tabs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.start_button = QPushButton("Start Optimization")
        self.start_button.clicked.connect(self.start_optimization_thread)

        self.plot_button = QPushButton("Show Plot")
        self.plot_button.clicked.connect(self.show_plot)

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

        self.freq_entry = self.create_entry("Central Frequency (MHz)", "144.0")
        self.min_freq_entry = self.create_entry("Sweep Minimum Frequency (MHz)", "143.0")
        self.max_freq_entry = self.create_entry("Sweep Maximum Frequency (MHz)", "145.0")
        self.num_steps_entry = self.create_entry("Number of Sweep Steps", "3")

        self.pop_size_entry = self.create_entry("Population Size", "50")
        self.num_gen_entry = self.create_entry("Number of Generations", "100")

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

        self.k_start_entry = self.create_entry("k_start", "-1")
        self.k_stop_entry = self.create_entry("k_stop", "1")
        self.k_step_entry = self.create_entry("k_step", "0.05")

        self.num_elements_entry = self.create_entry("Number of Elements", "3")
        self.min_length_entry = self.create_entry("Min Length", "0.25")
        self.max_length_entry = self.create_entry("Max Length", "0.5")
        self.total_distance_entry = self.create_entry("Total Distance", "1.0")

        self.lock_lengths_entry = QCheckBox("Lock Lengths")
        self.lock_distances_entry = QCheckBox("Lock Distances")

        self.crossover_prob_entry = self.create_entry("Crossover Probability", "0.2")
        self.mutation_prob_entry = self.create_entry("Mutation Probability", "0.1")
        self.target_imp_entry = self.create_entry("Target Real Impedance", "50")
        self.imp_tolerance_entry = self.create_entry("Impedance Tolerance", "5")

        for item in [
            self.k_start_entry, self.k_stop_entry, self.k_step_entry,
            self.num_elements_entry, self.min_length_entry, self.max_length_entry,
            self.total_distance_entry, self.crossover_prob_entry,
            self.mutation_prob_entry, self.target_imp_entry, self.imp_tolerance_entry
        ]:
            layout.addLayout(item["layout"])

        layout.addWidget(self.lock_lengths_entry)
        layout.addWidget(self.lock_distances_entry)

        self.advanced_tab.setLayout(layout)

      # ---------------- Paths Tab ----------------
    def build_paths_tab(self):
        layout = QVBoxLayout()

        self.exe_dir_entry = self.create_browse_entry("Executable Directory", "exe", directory=True)
        self.input_dir_entry = self.create_browse_entry("Input Directory", "optimizer\data", directory=True)
        self.output_dir_entry = self.create_browse_entry("Output Directory", "optimizer\data", directory=True)
        self.exe_file_entry = self.create_browse_entry("Executable File", "nec2dxs1K5.exe", directory=False)
        tmp_path = os.path.join("optimizer", "nec2dSopt.tmp")
        self.tmp_file_entry = self.create_browse_entry("Temp File", tmp_path, directory=False)
        self.main_input_file_entry = self.create_browse_entry("Main Input File", "input.nec", directory=False)
        self.main_output_file_entry = self.create_browse_entry("Main Output File", "output.out", directory=False)

        # aggiungo al layout tutte le entry
        for item in [
            self.exe_dir_entry, self.input_dir_entry, self.output_dir_entry,
            self.exe_file_entry, self.tmp_file_entry,
            self.main_input_file_entry, self.main_output_file_entry
        ]:
            layout.addLayout(item["layout"])

        layout.addStretch()  # spinge tutto verso l’alto e bilancia
        self.paths_tab.setLayout(layout)

    # ---------------- Output Tab ----------------
    def build_output_tab(self):
        layout = QVBoxLayout()

        self.csv_output_entry = self.create_browse_entry("CSV Output File", "optimized_individuals.csv", directory=False)
        self.enable_plots_entry = QCheckBox("Enable Plots")
        self.enable_plots_entry.setChecked(True)

        layout.addLayout(self.csv_output_entry["layout"])
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
        thread = threading.Thread(target=self.start_optimization)
        thread.start()

    def save_all_to_config(self, mode):
        # --- Simulation ---
        update_config('Simulation', 'frequency', self.freq_entry["entry"].text())
        if mode == "sweep":
            update_config('Simulation', 'min_freq', self.min_freq_entry["entry"].text())
            update_config('Simulation', 'max_freq', self.max_freq_entry["entry"].text())
            update_config('Simulation', 'num_freq_steps', self.num_steps_entry["entry"].text())

        # --- Genetic Algorithm ---
        update_config('GeneticAlgorithm', 'num_elements', self.num_elements_entry["entry"].text())
        update_config('GeneticAlgorithm', 'min_length', self.min_length_entry["entry"].text())
        update_config('GeneticAlgorithm', 'max_length', self.max_length_entry["entry"].text())
        update_config('GeneticAlgorithm', 'total_distance', self.total_distance_entry["entry"].text())
        update_config('GeneticAlgorithm', 'lock_lengths', str(self.lock_lengths_entry.isChecked()))
        update_config('GeneticAlgorithm', 'lock_distances', str(self.lock_distances_entry.isChecked()))
        update_config('GeneticAlgorithm', 'population_size', self.pop_size_entry["entry"].text())
        update_config('GeneticAlgorithm', 'num_generations', self.num_gen_entry["entry"].text())
        update_config('GeneticAlgorithm', 'crossover_probability', self.crossover_prob_entry["entry"].text())
        update_config('GeneticAlgorithm', 'mutation_probability', self.mutation_prob_entry["entry"].text())
        update_config('GeneticAlgorithm', 'target_real_impedance', self.target_imp_entry["entry"].text())
        update_config('GeneticAlgorithm', 'impedance_tolerance', self.imp_tolerance_entry["entry"].text())

        # --- Paths ---
        update_config('Paths', 'exe_dir', self.exe_dir_entry["entry"].text())
        update_config('Paths', 'input_dir', self.input_dir_entry["entry"].text())
        update_config('Paths', 'output_dir', self.output_dir_entry["entry"].text())
        update_config('Paths', 'exe_file', self.exe_file_entry["entry"].text())
        update_config('Paths', 'tmp_file', self.tmp_file_entry["entry"].text())
        update_config('Paths', 'main_input_file', self.main_input_file_entry["entry"].text())
        update_config('Paths', 'main_output_file', self.main_output_file_entry["entry"].text())

        # --- Output ---
        update_config('Output', 'csv_output_file', self.csv_output_entry["entry"].text())
        update_config('Output', 'enable_plots', str(self.enable_plots_entry.isChecked()))


    def start_optimization(self):
        try:
            self.start_button.setEnabled(False)
            self.progress_bar.setValue(0)

            mode = "single" if self.mode_single.isChecked() else "sweep"
            self.save_all_to_config(mode)

            # Run optimizer inside try/except
            try:
                if mode == 'single':
                    genetic_optimizer.run_optimization(mode='single', progress_callback=self.update_progress)
                else:
                    genetic_optimizer.run_optimization(mode='sweep', progress_callback=self.update_progress)
            except Exception as e:
                print("❌ Error in optimizer:", e)
                raise  # Reraise to outer catch

            print("✅ Optimization completed successfully")

        except Exception as e:
            print("❌ Fatal error in GUI or optimizer:", e)
            # Close app safely
            QApplication.quit()
            sys.exit(1)
        finally:
            self.start_button.setEnabled(True)
            self.progress_bar.setValue(100)


    def update_progress(self, progress):
        self.progress_bar.setValue(int(progress * 100))

    def show_plot(self):
        try:
            df = pd.read_csv(self.csv_output_entry["entry"].text())

            plt.figure(figsize=(8, 5))
            plt.plot(df['Max Gain (dB)'], label='Gain (dB)')
            plt.plot(df['Real Impedance Penalty'], label='Real Impedance Penalty')
            plt.plot(df['Imaginary Impedance Penalty'], label='Imaginary Impedance Penalty')
            plt.xlabel('Individual')
            plt.ylabel('Value')
            plt.title('Optimization Results')
            plt.legend()
            plt.grid()
            plt.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while displaying plot:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OptimizerGUI()
    window.show()
    sys.exit(app.exec())
