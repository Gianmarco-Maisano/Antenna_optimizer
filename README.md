
Antenna Optimizer
=================

Python application for optimizing Yagi-Uda antennas with a genetic algorithm and
NEC-2 simulations.

Features
--------

- Multi-objective optimization using NSGA-II.
- Single-frequency and frequency-sweep optimization.
- Configurable antenna geometry and genetic algorithm parameters.
- Enforced 3 cm minimum free clearance between elements. With 6 mm wire radius,
    this means at least 4.2 cm between wire axes.
- Configurable maximum VSWR; candidates above the limit are excluded from the
    feasible population. At 144 MHz, 0.85-1.05 m element lengths are a resonant
    starting range; 0.25-0.5 m elements are electrically short and capacitive.
- Antenna height and finite-ground electrical properties are included in NEC.
- Optional lossy coax and an ideal balun impedance ratio transform the feed
    impedance to the radio end. Coax defaults to disabled until its parameters are
    set to match the installation.
- Radiation patterns are saved as a complete 360-degree azimuth cut at the
    configured elevation above the horizon. Optimization gain and the highlighted
    peak use only azimuths from 0 to 180 degrees; the other half remains visible
    for pattern inspection.
- Optimization uses realized gain, including mismatch loss to the configured
    target feed resistance; raw NEC power gain is retained separately in the CSV.
- NEC input impedance is read at segment 5 of the center element (center tag
    selected from the configured element count). The CSV distinguishes antenna
    feedpoint impedance from radio-input impedance. In a frequency sweep the saved
    pattern corresponds to the middle sweep frequency; fitness averages realized
    gain and impedance penalties over all sweep frequencies.
- Live generation status: simulation count, valid individuals, repaired genes,
  and best gain.
- Population CSV, generation-history CSV, Pareto trade-off, convergence plots,
  and best-individual geometry.
- NEC2++ solver source included in `third_party/necpp`.

Installation
------------

Install Python dependencies:

    pip install -r requirements.txt

Build the included NEC2++ solver on Linux or macOS with CMake and a C++17
compiler:

    sh build_necpp.sh

The application also builds the solver automatically on first use if its local
binary is missing. No separate NEC executable download is required.

Run the application:

    python3 main.py

The known NEC2++ reference checks and geometry-constraint tests can be run with:

    python3 -m unittest discover -s tests -v

The simulator reference tests compare the measured impedance and gain with
values documented in the vendored NEC2++ test suite.

Licensing
---------

This project, including the vendored NEC2++ solver, is distributed under the
GNU General Public License version 2 or (at your option) any later version.
The complete license text is in `LICENSE`. NEC2++ is pinned to upstream release
v2.3.4; its original license and attribution are retained in
`third_party/necpp/COPYING`, and provenance is recorded in
`third_party/necpp/UPSTREAM`. The generated solver binary and build directory
are not committed; build them from the included source with `sh build_necpp.sh`.