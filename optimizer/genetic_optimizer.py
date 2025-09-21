# genetic_optimizer.py
import random
import os
import csv
import configparser
from functools import partial
from deap import base, creator, tools, algorithms

from optimizer.NEC_tools import run_nec2dxs1k5, read_nec_output, write_tmp_file

def init_individual(num_elements, min_length, max_length, total_distance, lock_lengths, lock_distances):
    """Create a single individual (list of lengths + distances)."""
    lengths = [random.uniform(min_length, max_length) for _ in range(num_elements)] if not lock_lengths else [0.3] * num_elements
    distances = [random.uniform(0.1, total_distance / num_elements) for _ in range(num_elements - 1)] if not lock_distances else [0.15] * (num_elements - 1)
    return creator.Individual(lengths + distances)

def make_custom_mutate(num_elements, min_length, max_length, total_distance, lock_lengths, lock_distances, gene_mut_prob):
    """Return a mutate function that uses the captured GA parameters."""
    def custom_mutate(individual):
        if not lock_lengths:
            for i in range(num_elements):
                if random.random() < gene_mut_prob:
                    individual[i] = random.uniform(min_length, max_length)
        if not lock_distances:
            for i in range(num_elements - 1):
                if random.random() < gene_mut_prob:
                    individual[num_elements + i] = random.uniform(0.1, total_distance / num_elements)
        return individual,
    return custom_mutate

def create_nec_input(lengths, distances, input_file, frequency):
    """Write a NEC input file based on lengths/distances and the chosen frequency."""
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
            file.write(f"GW  {i+1:<2} 9   {x1:.4f} {y1:.4f} 0   {x1:.4f} {y2:.4f} 0   0.006\n")
            if i < len(distances):
                x_position += distances[i]
        file.write("GE  0\n")
        file.write("GN  -1\n")
        file.write("EK\n")
        file.write("EX  0  2  5 0  1 0\n")
        file.write(f"FR  0  0  0  0  {frequency}  0\n")
        file.write("XQ\n")
        file.write("RP  0  73 1  1000 -180 0  5\n")
        file.write("EN\n")

def run_optimization(mode='single', progress_callback=None):
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
    EXE_FILE = config['Paths']['exe_file']
    EXE_DIR = os.path.dirname(EXE_FILE) if os.path.isabs(EXE_FILE) else os.path.join(BASE_DIR, os.path.dirname(EXE_FILE))
    print(EXE_DIR)
    TMP_FILE = config['Paths']['tmp_file']
    INPUT_FILE = config['Paths']['main_input_file']
    OUTPUT_FILE = config['Paths']['main_output_file']
    CSV_OUTPUT_FILE = config['Output']['csv_output_file']
    CSV_OUTPUT_PATH = CSV_OUTPUT_FILE if os.path.isabs(CSV_OUTPUT_FILE) else os.path.join(BASE_DIR, CSV_OUTPUT_FILE)

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
        partial(init_individual, num_elements, min_length, max_length, total_distance, lock_lengths, lock_distances)
    )
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)

    # custom mutate with captured params
    mutate_func = make_custom_mutate(num_elements, min_length, max_length, total_distance, lock_lengths, lock_distances, gene_mut_prob)
    toolbox.register("mutate", mutate_func)

    toolbox.register("select", tools.selNSGA2)

    # --- define evaluation functions capturing local variables ---
    def evaluate_single(individual):
        lengths = individual[:num_elements]
        distances = individual[num_elements:]

        nec_input_file = os.path.join(INP_DIR, INPUT_FILE)
        create_nec_input(lengths, distances, nec_input_file, frequency)

        output, error = run_nec2dxs1k5()
        if error:
            return 1000.0, 1000.0, 1000.0

        output_file = os.path.join(OUT_DIR, OUTPUT_FILE)
        real_impedance, imag_impedance, max_gain_db = read_nec_output(output_file)

        if real_impedance is None or max_gain_db is None:
            return 1000.0, 1000.0, 1000.0

        real_penalty = abs(real_impedance - target_real_impedance)
        imag_penalty = abs(imag_impedance)

        return float(max_gain_db), float(real_penalty), float(imag_penalty)

    def evaluate_sweep(individual):
        lengths = individual[:num_elements]
        distances = individual[num_elements:]

        total_gain = 0.0
        total_real_penalty = 0.0
        total_imag_penalty = 0.0

        for freq in frequencies:
            nec_input_file = os.path.join(INP_DIR, INPUT_FILE)
            create_nec_input(lengths, distances, nec_input_file, freq)

            output, error = run_nec2dxs1k5()
            if error:
                return 1000.0, 1000.0, 1000.0

            output_file = os.path.join(OUT_DIR, OUTPUT_FILE)
            real_impedance, imag_impedance, max_gain_db = read_nec_output(output_file)
            if real_impedance is None or max_gain_db is None:
                return 1000.0, 1000.0, 1000.0

            total_gain += max_gain_db
            total_real_penalty += abs(real_impedance - target_real_impedance)
            total_imag_penalty += abs(imag_impedance)

        avg_gain = total_gain / len(frequencies)
        avg_real_penalty = total_real_penalty / len(frequencies)
        avg_imag_penalty = total_imag_penalty / len(frequencies)

        return float(avg_gain), float(avg_real_penalty), float(avg_imag_penalty)

    # register chosen fitness/evaluate
    if mode == 'sweep':
        toolbox.register("evaluate", evaluate_sweep)
    else:
        toolbox.register("evaluate", evaluate_single)

    # --- warmup / tmp write (NEC input template) ---
    write_tmp_file(os.path.join(EXE_DIR, TMP_FILE), os.path.join(INP_DIR, INPUT_FILE), os.path.join(OUT_DIR, OUTPUT_FILE))

    print("🚀 Starting optimization (mode = {})".format(mode))
    random.seed(42)
    # --- Initialize population & evaluate initial individuals ---
    population = toolbox.population(n=population_size)

    # Evaluate initial population
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    for ind in invalid_ind:
        ind.fitness.values = toolbox.evaluate(ind)

    # statistics
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda vals: [sum(x)/len(x) for x in zip(*vals)])
    stats.register("min", lambda vals: [min(x) for x in zip(*vals)])
    stats.register("max", lambda vals: [max(x) for x in zip(*vals)])

    hall_of_fame = tools.HallOfFame(5)

    # mu/lambda
    mu = max(1, int(population_size * 0.6))
    lambda_ = max(1, int(population_size * 0.6))

    # --- Evolution loop with NSGA-II selection and progress callback ---
    logbook = tools.Logbook()
    for gen in range(1, num_generations + 1):
        # --- Variation: create offspring ---
        offspring = algorithms.varAnd(population, toolbox, cxpb=crossover_probability, mutpb=mutation_probability)

        # Evaluate offspring
        invalid_off = [ind for ind in offspring if not ind.fitness.valid]
        for ind in invalid_off:
            ind.fitness.values = toolbox.evaluate(ind)

        # --- Next population via NSGA-II selection ---
        population = tools.selNSGA2(population + offspring, mu)

        # Update hall of fame and stats
        hall_of_fame.update(population)
        record = stats.compile(population) if stats is not None else {}
        logbook.record(gen=gen, **record)

        # Progress callback (0..1)
        if progress_callback:
            try:
                progress_callback(gen / float(num_generations))
            except Exception:
                pass


    # --- Save results to CSV ---
    header = [f"Length{i+1}" for i in range(num_elements)] + [f"Distance{i+1}" for i in range(max(0, num_elements - 1))] + ["Max Gain (dB)", "Real Impedance Penalty", "Imaginary Impedance Penalty"]
    with open(CSV_OUTPUT_PATH, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for ind in population:
            lengths = ind[:num_elements]
            distances = ind[num_elements:]
            fitness = ind.fitness.values
            writer.writerow(list(lengths) + list(distances) + [fitness[0], fitness[1], fitness[2]])

    print("✅ Optimization finished. Results saved to:", CSV_OUTPUT_PATH)
    return population, logbook, hall_of_fame

