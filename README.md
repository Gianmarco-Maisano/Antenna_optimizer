
Antenna Optimizer

Python tool for automatic optimization of Yagi-Uda antennas using a genetic algorithm and NEC-2D simulations.

Overview

This project automates the optimization of Yagi-Uda antennas using a genetic algorithm and the NEC-2D simulation engine.

🚀 Features

✅ Multi-objective optimization using the NSGA-II genetic algorithm.

✅ Dual-band antenna placement optimization.

✅ Configurable number of elements and parameters.

✅ Graphical visualization of optimization results.



⚙️ Installation

Clone the repository

Install dependencies:

    pip install -r requirements.txt

Place the NEC solver in the exe folder (nec2dxs1k5.exe), downloadable from https://www.qsl.net/4nec2/


🛠️ Usage

Run the project using:

    python3 main.py


📊 Output

Optimized antenna configurations. (plot_geometry.py)

Simulation results including:

Maximum Gain (dB)

Real and Imaginary Impedance Penalties

Graphical plots of optimization performance.