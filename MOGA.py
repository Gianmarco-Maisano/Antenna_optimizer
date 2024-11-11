import random
import subprocess
import re
from deap import base, creator, tools, algorithms
import csv

# Funzione per eseguire NEC2 tramite il percorso specificato
def run_nec2dxs1k5():
    exe_directory = r"D:\4nec2\exe"  # Directory dell'eseguibile
    exe_file = r"nec2dxs1K5.exe"  # Nome del file eseguibile
    input_file = r"nec2dopt.tmp"  # Nome del file di input
    
    # Comando PowerShell per spostarsi nella directory ed eseguire il comando
    command = f"Set-Location '{exe_directory}'; Get-Content '{input_file}' | & .\\{exe_file}"

    # Esegui il comando in PowerShell
    process = subprocess.run(
        ["powershell", "-Command", command],
        capture_output=True,  # Cattura stdout e stderr
        text=True  # Decodifica l'output in formato testo
    )

    # Ritorna l'output e l'errore
    return process.stdout, process.stderr

def read_nec_output(output_file):
    # Apri il file di output
    with open(output_file, "r") as file:
        lines = file.readlines()

    # Variabili per salvare i dati di interesse
    real_impedance = None
    imag_impedance = None
    max_gain_db = -999.99  # Inizializziamo il guadagno a un valore molto basso

    inside_impedance_section = False
    inside_radiation_section = False

    for line in lines:
        # Cerca la sezione dell'impedenza
        if "IMPEDANCE (OHMS)" in line:
            inside_impedance_section = True
            continue

        # Cerca la sezione dei radiation patterns per il guadagno
        if "- - - RADIATION PATTERNS - - -" in line:
            inside_radiation_section = True
            continue

        # Estrai l'impedenza
        if inside_impedance_section:
            if re.match(r'^\s*\d+\s+\d+', line):  # Assicura che la riga inizi con numeri
                separated_values = re.findall(r'[-+]?\d*\.\d+E[-+]?\d+|[-+]?\d+\.\d+|[-+]?\d+', line)
                if len(separated_values) >= 8:  # Assicura che ci siano abbastanza valori
                    try:
                        real_impedance = float(separated_values[6])  # Settimo elemento (parte reale)
                        imag_impedance = float(separated_values[7])  # Ottavo elemento (parte immaginaria)
                    except ValueError:
                        print("Errore nel parsing dei valori di impedenza.")
                inside_impedance_section = False  # Uscire dalla sezione

        # Estrai il guadagno massimo
        if inside_radiation_section:
            match = re.search(r"\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+([-+]?\d+\.\d+)\s+[-+]?\d+\.\d+", line)
            if match:
                total_gain = float(match.group(1))  # Estrai il guadagno totale
                if total_gain > max_gain_db:
                    max_gain_db = total_gain  # Aggiorna il guadagno massimo

    # Restituisce l'impedenza e il guadagno massimo
    return real_impedance, imag_impedance, max_gain_db

# Funzione per creare un file di input NEC2 basato sui parametri
def create_nec_input(lengths, distances, input_file):
    with open(input_file, "w") as file:
        file.write("CM\n")
        file.write("CM forw: 90, 0 ; back:-90, 0\n")
        file.write("CE\n")
        
        x_position = 0  # La posizione iniziale lungo l'asse X
        
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
        file.write("FR  0  0  0  0  433  0\n")
        file.write("XQ\n")
        file.write("RP  0  73 1  1000 -180 0  5\n")
        file.write("EN\n")

# Funzione di mutazione modificata
def custom_mutate(individual):
    if not lock_lengths:
        for i in range(num_elements):
            if random.random() < 0.2:  # Probabilità di mutazione
                individual[i] = random.uniform(min_length, max_length)

    if not lock_distances:
        for i in range(num_elements - 1):
            if random.random() < 0.2:  # Probabilità di mutazione
                individual[num_elements + i] = random.uniform(0.1, total_distance / num_elements)

    return individual,  # Restituisci l'individuo mutato come una tupla

# Funzione di fitness
def fitness_function(individual, target_real_impedance=50, impedance_tolerance=5):
    lengths = individual[:num_elements]
    distances = individual[num_elements:]
    
    create_nec_input(lengths, distances, r"D:\\4nec2\\out\\Example1.nec")
    output, error = run_nec2dxs1k5()
    
    if error:
        print(f"Errore durante l'esecuzione di NEC2: {error}")
        return 1000, 1000, 1000  # Penalità massima in caso di errore
    
    output_file = r"D:\\4nec2\\out\\Example1.out"
    real_impedance, imag_impedance, max_gain_db = read_nec_output(output_file)
    
    if real_impedance is None or max_gain_db is None:
        return 1000, 1000, 1000  # Penalità massima se non c'è output
    
    real_impedance_penalty = abs(real_impedance - target_real_impedance)
    imag_impedance_penalty = abs(imag_impedance)
    
    return max_gain_db, real_impedance_penalty, imag_impedance_penalty

# Creazione di una classe multi-obiettivo con DEAP
creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0, -1.0))  # Massimizza guadagno, minimizza impedenza reale e immaginaria
creator.create("Individual", list, fitness=creator.FitnessMulti)

# Parametri di input
num_elements = 7  # Numero di elementi dell'antenna
max_length = 0.35  # Lunghezza massima degli elementi in metri
min_length = 0.25  # Lunghezza minima degli elementi in metri
total_distance = 1.0  # Somma massima delle distanze tra gli elementi in metri

# Variabili per lunghezze e distanze iniziali
lock_lengths = True  # Imposta a True per mantenere costanti le lunghezze
lock_distances = False  # Imposta a True per mantenere costanti le distanze
initial_lengths = [0.343, 0.323, 0.304, 0.3, 0.296, 0.292, 0.289]  # Lunghezze iniziali
initial_distances = [0.2, 0.1, 0.15, 0.15, 0.15, 0.15]  # Distanze iniziali

# Toolbox per l'algoritmo genetico
toolbox = base.Toolbox()

# Inizializzazione degli individui
def init_individual():
    lengths = [initial_lengths[i] if lock_lengths else random.uniform(min_length, max_length) for i in range(num_elements)]
    distances = [initial_distances[i] if lock_distances else random.uniform(0.1, total_distance / num_elements) for i in range(num_elements - 1)]
    return creator.Individual(lengths + distances)

toolbox.register("individual", init_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# Funzioni di crossover, mutazione e selezione
toolbox.register("mate", tools.cxBlend, alpha=0.5)
#toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.1, indpb=0.2)
toolbox.register("mutate", custom_mutate)
toolbox.register("select", tools.selNSGA2)
toolbox.register("evaluate", fitness_function)

# Creazione dell'oggetto per la raccolta delle statistiche
stats = tools.Statistics(lambda ind: ind.fitness.values)
stats.register("avg", lambda values: [sum(x)/len(x) for x in zip(*values)])
stats.register("min", lambda values: [min(x) for x in zip(*values)])
stats.register("max", lambda values: [max(x) for x in zip(*values)])

# Creazione dell'Hall of Fame
hall_of_fame = tools.HallOfFame(5)

# Main loop di ottimizzazione
def main():
    print("Inizio Simulazione")
    random.seed(42)
    
    population = toolbox.population(n=50)
    num_generations = 20

    # Algoritmo genetico NSGA-II con statistiche e Hall of Fame
    population, logbook = algorithms.eaMuPlusLambda(
        population, toolbox, mu=30, lambda_=30, cxpb=0.2, mutpb=0.6, ngen=num_generations,
        stats=stats, halloffame=hall_of_fame, verbose=True
    )
    # Algoritmo genetico NSGA-II con statistiche e Hall of Fame
    # Parametri:
    # population: la popolazione iniziale di individui da evolvere.
    # mu: numero di individui da selezionare per la prossima generazione.
    # lambda_: numero di individui generati (crossover + mutazione) per la nuova generazione.
    # cxpb: probabilità di crossover, ovvero la probabilità che due individui si incrocino per generare nuovi individui.
    # mutpb: probabilità di mutazione, ovvero la probabilità che un individuo subisca una mutazione.
    # ngen: numero totale di generazioni da eseguire durante il processo evolutivo.
    # stats: oggetto per raccogliere statistiche sulla popolazione, come media, minimi e massimi dei fitness.
    # halloffame: oggetto per mantenere una traccia dei migliori individui trovati durante l'evoluzione.
    # verbose: se True, stampa informazioni dettagliate sul progresso dell'evoluzione.

    # Stampa le statistiche della logbook per ogni generazione
    print("\nStatistiche per generazione:")
    for record in logbook:
        print(f"Generazione {record['gen']}: Miglior fitness = {record['max']}, Media = {record['avg']}, Min = {record['min']}")

    # Mostra i migliori individui memorizzati nell'Hall of Fame
    print("\nMigliori individui nell'Hall of Fame:")
    for ind in hall_of_fame:
        print(f"Individuo: {ind}, Fitness: {ind.fitness.values}")

    # Salva i migliori individui
    top_individuals = tools.sortNondominated(population, len(population), True)[0]
    
    # Scrivi i dati in un file CSV
    with open("optimized_individuals.csv", "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Length1", "Length2", "Length3", "Length4", "Length5", "Length6", "Length7", 
                         "Distance1", "Distance2", "Distance3", "Distance4", "Distance5", "Distance6",
                         "Max Gain (dB)", "Real Impedance Penalty", "Imaginary Impedance Penalty"])
        
        for ind in top_individuals:
            lengths = ind[:num_elements]
            distances = ind[num_elements:]
            fitness = ind.fitness.values
            writer.writerow(lengths + distances + [fitness[0], fitness[1], fitness[2]])

    print("Ottimizzazione Terminata")

if __name__ == "__main__":
    main()
