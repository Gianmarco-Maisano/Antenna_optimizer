# genetic_optimizer.py
import random
import os
import csv
import json
import configparser
from functools import partial
from deap import base, creator, tools, algorithms

from optimizer.NEC_tools import run_necpp, read_nec_results
from optimizer.geometry_constraints import (
    WIRE_RADIUS_M,
    minimum_center_spacing,
    repair_individual,
    validate_individual,
)
from optimizer.rf_metrics import realized_gain_db, transform_feed_impedance, vswr_from_impedance

INVALID_FITNESS = (-999.99, 1_000_000.0, 1_000_000.0)


def init_individual(
    num_elements,
    min_length,
    max_length,
    min_spacing,
    max_spacing,
    lock_lengths,
    lock_distances,
):
    """Create a single individual (list of lengths + distances)."""
    fixed_length = min(max(0.3, min_length), max_length)
    fixed_spacing = min(max(0.15, min_spacing), max_spacing)
    lengths = [random.uniform(min_length, max_length) for _ in range(num_elements)] if not lock_lengths else [fixed_length] * num_elements
    distances = [random.uniform(min_spacing, max_spacing) for _ in range(num_elements - 1)] if not lock_distances else [fixed_spacing] * (num_elements - 1)
    individual = creator.Individual(lengths + distances)
    repair_individual(individual, num_elements, min_length, max_length, min_spacing, max_spacing)
    return individual


def make_custom_mutate(
    num_elements,
    min_length,
    max_length,
    min_spacing,
    max_spacing,
    lock_lengths,
    lock_distances,
    gene_mut_prob,
):
    """Return a mutate function that uses the captured GA parameters."""
    def custom_mutate(individual):
        if not lock_lengths:
            for i in range(num_elements):
                if random.random() < gene_mut_prob:
                    individual[i] = random.uniform(min_length, max_length)
        if not lock_distances:
            for i in range(num_elements - 1):
                if random.random() < gene_mut_prob:
                    individual[num_elements + i] = random.uniform(min_spacing, max_spacing)
        return individual,
    return custom_mutate

def create_nec_input(
    lengths,
    distances,
    input_file,
    frequency,
    min_spacing=None,
    wire_radius=WIRE_RADIUS_M,
    antenna_height_m=2.0,
    ground_relative_permittivity=13.0,
    ground_conductivity_s_per_m=0.005,
    pattern_elevation_deg=10.0,
):
    """Write a NEC input file based on lengths/distances and the chosen frequency."""
    if min_spacing is not None:
        validate_individual(lengths + distances, len(lengths), min_spacing)

    with open(input_file, "w") as file:
        file.write("CM\n")
        file.write("CM forw: 90, 0 ; back:-90, 0\n")
        file.write("CE\n")
        x_position = 0
        for i in range(len(lengths)):
            half_length = lengths[i] / 2
            x1 = x_position
            y1 = -half_length
            y2 = half_length
            file.write(
                f"GW  {i+1:<2} 9   {x1:.4f} {y1:.4f} {antenna_height_m:.4f} "
                f"{x1:.4f} {y2:.4f} {antenna_height_m:.4f} {wire_radius:.4f}\n"
            )
            if i < len(distances):
                x_position += distances[i]
        file.write("GE  0\n")
        file.write(
            f"GN  0  0  0  0  {ground_relative_permittivity:.4f} "
            f"{ground_conductivity_s_per_m:.6f}\n"
        )
        file.write("EK\n")
        source_tag = (len(lengths) + 1) // 2
        file.write(f"EX  0  {source_tag}  5 0  1 0\n")
        file.write(f"FR  0  0  0  0  {frequency}  0\n")
        file.write("XQ\n")
        theta_deg = 90.0 - pattern_elevation_deg
        file.write(f"RP  0  1  72  1000 {theta_deg:.4f} 0 0 5\n")
        file.write("EN\n")

def run_optimization(mode='single', progress_callback=None, status_callback=None):
    """
    Run the GA optimizer.
    mode: 'single' or 'sweep'
    progress_callback: optional function(progress_float_between_0_and_1)
    """

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
    CONFIG_PATH = os.path.abspath(CONFIG_PATH)

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)

    # --- Paths ---
    OUT_DIR = os.path.join(BASE_DIR, config['Paths']['output_dir'])
    INP_DIR = os.path.join(BASE_DIR, config['Paths']['input_dir'])
    INPUT_FILE = config['Paths']['main_input_file']
    OUTPUT_FILE = config['Paths']['main_output_file']
    CSV_OUTPUT_FILE = config['Output']['csv_output_file']
    CSV_OUTPUT_PATH = CSV_OUTPUT_FILE if os.path.isabs(CSV_OUTPUT_FILE) else os.path.join(BASE_DIR, CSV_OUTPUT_FILE)
    HISTORY_OUTPUT_FILE = config['Output'].get('history_output_file', 'optimization_history.csv')
    HISTORY_OUTPUT_PATH = HISTORY_OUTPUT_FILE if os.path.isabs(HISTORY_OUTPUT_FILE) else os.path.join(BASE_DIR, HISTORY_OUTPUT_FILE)

    # create dirs if missing
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(INP_DIR, exist_ok=True)

    # --- Simulation params ---
    frequency = float(config['Simulation'].get('frequency', 144.0))
    min_freq = float(config['Simulation'].get('min_freq', frequency))
    max_freq = float(config['Simulation'].get('max_freq', frequency))
    num_freq_steps = int(config['Simulation'].get('num_freq_steps', 1))
    if num_freq_steps < 1:
        num_freq_steps = 1

    if num_freq_steps == 1:
        frequencies = [frequency]
    else:
        freq_step_size = (max_freq - min_freq) / max(1, (num_freq_steps - 1))
        frequencies = [min_freq + i * freq_step_size for i in range(num_freq_steps)]

    # --- Genetic Algorithm params ---
    target_real_impedance = float(config['GeneticAlgorithm'].get('target_real_impedance', 50.0))
    maximum_vswr = float(config['GeneticAlgorithm'].get('maximum_vswr', 3.0))
    population_size = int(config['GeneticAlgorithm'].get('population_size', 50))
    num_generations = int(config['GeneticAlgorithm'].get('num_generations', 100))
    crossover_probability = float(config['GeneticAlgorithm'].get('crossover_probability', 0.2))
    mutation_probability = float(config['GeneticAlgorithm'].get('mutation_probability', 0.1))
    num_elements = int(config['GeneticAlgorithm'].get('num_elements', 3))
    max_length = float(config['GeneticAlgorithm'].get('max_length', 0.5))
    min_length = float(config['GeneticAlgorithm'].get('min_length', 0.25))
    total_distance = float(config['GeneticAlgorithm'].get('total_distance', 1.0))
    lock_lengths = config['GeneticAlgorithm'].getboolean('lock_lengths', False)
    lock_distances = config['GeneticAlgorithm'].getboolean('lock_distances', False)
    minimum_clearance = float(config['GeneticAlgorithm'].get('minimum_element_clearance_m', 0.03))
    wire_radius = float(config['GeneticAlgorithm'].get('wire_radius_m', WIRE_RADIUS_M))
    antenna_height_m = float(config['Simulation'].get('antenna_height_m', 2.0))
    ground_relative_permittivity = float(config['Simulation'].get('ground_relative_permittivity', 13.0))
    ground_conductivity_s_per_m = float(config['Simulation'].get('ground_conductivity_s_per_m', 0.005))
    pattern_elevation_deg = float(config['Simulation'].get('pattern_elevation_deg', 10.0))
    coax_enabled = config['GeneticAlgorithm'].getboolean('coax_enabled', False)
    coax_length_m = float(config['GeneticAlgorithm'].get('coax_length_m', 0.0)) if coax_enabled else 0.0
    coax_impedance_ohm = float(config['GeneticAlgorithm'].get('coax_impedance_ohm', 50.0))
    coax_velocity_factor = float(config['GeneticAlgorithm'].get('coax_velocity_factor', 0.66))
    coax_loss_db_per_100m = float(config['GeneticAlgorithm'].get('coax_loss_db_per_100m', 0.0)) if coax_enabled else 0.0
    balun_impedance_ratio = float(config['GeneticAlgorithm'].get('balun_impedance_ratio', 1.0))
    min_spacing = minimum_center_spacing(minimum_clearance, wire_radius)
    max_spacing = total_distance / num_elements
    if max_spacing < min_spacing:
        raise ValueError(
            f"Maximum element spacing ({max_spacing:.3f} m) is below the required "
            f"center spacing ({min_spacing:.3f} m). Increase total_distance or reduce num_elements."
        )

    # gene-level mutation probability (used inside custom_mutate)
    gene_mut_prob = mutation_probability

    # --- DEAP setup (safe creation) ---
    try:
        creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0, -1.0))
    except Exception:
        # already created
        pass

    try:
        creator.create("Individual", list, fitness=creator.FitnessMulti)
    except Exception:
        pass

    toolbox = base.Toolbox()
    # register individual factory with current params
    toolbox.register(
        "individual",
        partial(
            init_individual,
            num_elements,
            min_length,
            max_length,
            min_spacing,
            max_spacing,
            lock_lengths,
            lock_distances,
        )
    )
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)

    # custom mutate with captured params
    mutate_func = make_custom_mutate(
        num_elements,
        min_length,
        max_length,
        min_spacing,
        max_spacing,
        lock_lengths,
        lock_distances,
        gene_mut_prob,
    )
    toolbox.register("mutate", mutate_func)

    toolbox.register("select", tools.selNSGA2)

    # --- define evaluation functions capturing local variables ---
    def evaluate_single(individual):
        lengths = individual[:num_elements]
        distances = individual[num_elements:]

        nec_input_file = os.path.join(INP_DIR, INPUT_FILE)
        create_nec_input(
            lengths, distances, nec_input_file, frequency, min_spacing, wire_radius,
            antenna_height_m, ground_relative_permittivity, ground_conductivity_s_per_m,
            pattern_elevation_deg,
        )

        output_file = os.path.join(OUT_DIR, OUTPUT_FILE)
        output, error = run_necpp(nec_input_file, output_file)
        if error:
            return INVALID_FITNESS

        simulation = read_nec_results(output_file)
        real_impedance = simulation['real_impedance']
        imag_impedance = simulation['imag_impedance']
        max_gain_db = simulation['max_gain_db']

        if real_impedance is None or imag_impedance is None or max_gain_db is None or max_gain_db <= -999.99:
            return INVALID_FITNESS

        radio_real, radio_imag, coax_loss_db = transform_feed_impedance(
            real_impedance, imag_impedance, frequency, coax_length_m,
            coax_impedance_ohm, coax_velocity_factor, coax_loss_db_per_100m,
            balun_impedance_ratio,
        )
        vswr = vswr_from_impedance(radio_real, radio_imag, target_real_impedance)
        if vswr > maximum_vswr:
            return INVALID_FITNESS

        real_penalty = abs(radio_real - target_real_impedance)
        imag_penalty = abs(radio_imag)
        individual.power_gain_db = float(max_gain_db)
        individual.antenna_impedance_real = float(real_impedance)
        individual.antenna_impedance_imag = float(imag_impedance)
        individual.radio_impedance_real = float(radio_real)
        individual.radio_impedance_imag = float(radio_imag)
        individual.vswr = float(vswr)
        individual.maximum_sweep_vswr = float(vswr)
        individual.coax_loss_db = float(coax_loss_db)
        individual.pattern_frequency_mhz = frequency
        individual.radiation_pattern = simulation['radiation_pattern']
        gain = realized_gain_db(max_gain_db, radio_real, radio_imag, target_real_impedance) - coax_loss_db

        return float(gain), float(real_penalty), float(imag_penalty)

    def evaluate_sweep(individual):
        lengths = individual[:num_elements]
        distances = individual[num_elements:]

        total_realized_gain = 0.0
        total_power_gain = 0.0
        total_real_penalty = 0.0
        total_imag_penalty = 0.0
        total_coax_loss = 0.0
        pattern_index = len(frequencies) // 2
        maximum_measured_vswr = 0.0

        for frequency_index, freq in enumerate(frequencies):
            nec_input_file = os.path.join(INP_DIR, INPUT_FILE)
            create_nec_input(
                lengths, distances, nec_input_file, freq, min_spacing, wire_radius,
                antenna_height_m, ground_relative_permittivity, ground_conductivity_s_per_m,
                pattern_elevation_deg,
            )

            output_file = os.path.join(OUT_DIR, OUTPUT_FILE)
            output, error = run_necpp(nec_input_file, output_file)
            if error:
                return INVALID_FITNESS

            simulation = read_nec_results(output_file)
            real_impedance = simulation['real_impedance']
            imag_impedance = simulation['imag_impedance']
            max_gain_db = simulation['max_gain_db']
            if real_impedance is None or imag_impedance is None or max_gain_db is None or max_gain_db <= -999.99:
                return INVALID_FITNESS

            radio_real, radio_imag, coax_loss_db = transform_feed_impedance(
                real_impedance, imag_impedance, freq, coax_length_m,
                coax_impedance_ohm, coax_velocity_factor, coax_loss_db_per_100m,
                balun_impedance_ratio,
            )
            vswr = vswr_from_impedance(radio_real, radio_imag, target_real_impedance)
            if vswr > maximum_vswr:
                return INVALID_FITNESS
            maximum_measured_vswr = max(maximum_measured_vswr, vswr)

            if frequency_index == pattern_index:
                individual.antenna_impedance_real = float(real_impedance)
                individual.antenna_impedance_imag = float(imag_impedance)
                individual.radio_impedance_real = float(radio_real)
                individual.radio_impedance_imag = float(radio_imag)
                individual.vswr = float(vswr)
                individual.coax_loss_db = float(coax_loss_db)
                individual.pattern_frequency_mhz = freq
                individual.radiation_pattern = simulation['radiation_pattern']

            total_realized_gain += realized_gain_db(
                max_gain_db,
                radio_real,
                radio_imag,
                target_real_impedance,
            ) - coax_loss_db
            total_power_gain += max_gain_db
            total_real_penalty += abs(radio_real - target_real_impedance)
            total_imag_penalty += abs(radio_imag)
            total_coax_loss += coax_loss_db

        avg_gain = total_realized_gain / len(frequencies)
        individual.power_gain_db = total_power_gain / len(frequencies)
        individual.maximum_sweep_vswr = maximum_measured_vswr
        individual.coax_loss_db = total_coax_loss / len(frequencies)
        avg_real_penalty = total_real_penalty / len(frequencies)
        avg_imag_penalty = total_imag_penalty / len(frequencies)

        return float(avg_gain), float(avg_real_penalty), float(avg_imag_penalty)

    # register chosen fitness/evaluate
    if mode == 'sweep':
        toolbox.register("evaluate", evaluate_sweep)
    else:
        toolbox.register("evaluate", evaluate_single)

    print("🚀 Starting optimization (mode = {})".format(mode))
    if status_callback:
        status_callback({
            'phase': 'initializing',
            'generation': 0,
            'total_generations': num_generations,
            'evaluations': 0,
            'repaired_genes': 0,
            'clearance_m': minimum_clearance,
        })
    random.seed(42)
    # --- Initialize population & evaluate initial individuals ---
    population = toolbox.population(n=population_size)

    # Evaluate initial population
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    for ind in invalid_ind:
        ind.fitness.values = toolbox.evaluate(ind)
    evaluation_count = len(invalid_ind)

    # statistics
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda vals: [sum(x)/len(x) for x in zip(*vals)])
    stats.register("min", lambda vals: [min(x) for x in zip(*vals)])
    stats.register("max", lambda vals: [max(x) for x in zip(*vals)])

    hall_of_fame = tools.HallOfFame(5)
    hall_of_fame.update(population)

    # mu/lambda
    mu = max(1, int(population_size * 0.6))
    lambda_ = max(1, int(population_size * 0.6))

    # --- Evolution loop with NSGA-II selection and progress callback ---
    logbook = tools.Logbook()
    history_rows = []
    for gen in range(1, num_generations + 1):
        # --- Variation: create offspring ---
        offspring = algorithms.varAnd(population, toolbox, cxpb=crossover_probability, mutpb=mutation_probability)
        repaired_genes = 0
        for individual in offspring:
            repaired_genes += repair_individual(individual, num_elements, min_length, max_length, min_spacing, max_spacing)

        # Evaluate offspring
        invalid_off = [ind for ind in offspring if not ind.fitness.valid]
        for ind in invalid_off:
            ind.fitness.values = toolbox.evaluate(ind)
        evaluation_count += len(invalid_off)

        # --- Next population via NSGA-II selection ---
        population = tools.selNSGA2(population + offspring, mu)

        # Update hall of fame and stats
        hall_of_fame.update(population)
        record = stats.compile(population) if stats is not None else {}
        logbook.record(gen=gen, **record)
        feasible = sum(ind.fitness.values != INVALID_FITNESS for ind in population)
        best = max(population, key=lambda individual: individual.fitness.values[0])
        history_row = {
            'Generation': gen,
            'Best Realized Gain (dBi)': record['max'][0],
            'Average Realized Gain (dBi)': record['avg'][0],
            'Best VSWR': min(
                (getattr(ind, 'vswr', float('inf')) for ind in population if ind.fitness.values != INVALID_FITNESS),
                default=float('inf'),
            ),
            'Average Power Gain (dBi)': sum(
                getattr(ind, 'power_gain_db', INVALID_FITNESS[0]) for ind in population
            ) / len(population),
            'Best Real Impedance Penalty (Ohm)': min(ind.fitness.values[1] for ind in population),
            'Average Real Impedance Penalty (Ohm)': record['avg'][1],
            'Best Imaginary Impedance Penalty (Ohm)': min(ind.fitness.values[2] for ind in population),
            'Average Imaginary Impedance Penalty (Ohm)': record['avg'][2],
            'Evaluated Individuals': evaluation_count,
            'Repaired Genes': repaired_genes,
            'Feasible Individuals': feasible,
            'Best Lengths (m)': ';'.join(f'{value:.6f}' for value in best[:num_elements]),
            'Best Spacings (m)': ';'.join(f'{value:.6f}' for value in best[num_elements:]),
        }
        history_rows.append(history_row)

        # Progress callback (0..1)
        if progress_callback:
            try:
                progress_callback(gen / float(num_generations))
            except Exception:
                pass
        if status_callback:
            status_callback({
                'phase': 'evolving',
                'generation': gen,
                'total_generations': num_generations,
                'evaluations': evaluation_count,
                'repaired_genes': repaired_genes,
                'feasible': feasible,
                'population_size': len(population),
                'best_gain': record['max'][0],
                'average_gain': record['avg'][0],
                'best_real_penalty': history_row['Best Real Impedance Penalty (Ohm)'],
                'best_imag_penalty': history_row['Best Imaginary Impedance Penalty (Ohm)'],
                'clearance_m': minimum_clearance,
            })


    # --- Save results to CSV ---
    if not any(ind.fitness.values != INVALID_FITNESS for ind in population):
        raise RuntimeError(
            f"No individual met the VSWR limit of {maximum_vswr:.2f}:1. "
            "Increase the allowed element-length range or relax the VSWR threshold."
        )

    header = (
        [f"Length{i+1}" for i in range(num_elements)]
        + [f"Distance{i+1}" for i in range(max(0, num_elements - 1))]
        + [
            "Antenna Feed Impedance Real (Ohm)", "Antenna Feed Impedance Imaginary (Ohm)",
            "Radio Input Impedance Real (Ohm)", "Radio Input Impedance Imaginary (Ohm)",
            "VSWR at Radio", "Maximum Sweep VSWR", "Coax Loss (dB)",
            "Pattern Frequency (MHz)", "Pattern Elevation (deg)",
            "Power Gain (dBi)", "Realized Gain (dBi)",
            "Real Impedance Penalty", "Imaginary Impedance Penalty", "Radiation Pattern JSON",
        ]
    )
    with open(CSV_OUTPUT_PATH, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for ind in population:
            lengths = ind[:num_elements]
            distances = ind[num_elements:]
            fitness = ind.fitness.values
            writer.writerow(
                list(lengths) + list(distances) + [
                    getattr(ind, 'antenna_impedance_real', float('nan')),
                    getattr(ind, 'antenna_impedance_imag', float('nan')),
                    getattr(ind, 'radio_impedance_real', float('nan')),
                    getattr(ind, 'radio_impedance_imag', float('nan')),
                    getattr(ind, 'vswr', float('nan')),
                    getattr(ind, 'maximum_sweep_vswr', getattr(ind, 'vswr', float('nan'))),
                    getattr(ind, 'coax_loss_db', 0.0),
                    getattr(ind, 'pattern_frequency_mhz', float('nan')),
                    pattern_elevation_deg,
                    getattr(ind, 'power_gain_db', INVALID_FITNESS[0]),
                    fitness[0], fitness[1], fitness[2],
                    json.dumps(getattr(ind, 'radiation_pattern', []), separators=(',', ':')),
                ]
            )

    history_fields = [
        'Generation', 'Best Realized Gain (dBi)', 'Average Realized Gain (dBi)',
        'Average Power Gain (dBi)',
        'Best VSWR',
        'Best Real Impedance Penalty (Ohm)', 'Average Real Impedance Penalty (Ohm)',
        'Best Imaginary Impedance Penalty (Ohm)', 'Average Imaginary Impedance Penalty (Ohm)',
        'Evaluated Individuals', 'Repaired Genes', 'Feasible Individuals',
        'Best Lengths (m)', 'Best Spacings (m)',
    ]
    with open(HISTORY_OUTPUT_PATH, 'w', newline='') as history_file:
        writer = csv.DictWriter(history_file, fieldnames=history_fields)
        writer.writeheader()
        writer.writerows(history_rows)

    print("✅ Optimization finished. Results saved to:", CSV_OUTPUT_PATH)
    print("Generation history saved to:", HISTORY_OUTPUT_PATH)
    return population, logbook, hall_of_fame

