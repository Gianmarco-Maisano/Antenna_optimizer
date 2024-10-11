import csv
import matplotlib.pyplot as plt
import numpy as np

# Funzione per leggere i risultati ottimizzati da un file CSV
def read_optimized_data(csv_file):
    individuals = []
    
    with open(csv_file, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Salta l'intestazione
        for row in reader:
            lengths = list(map(float, row[:7]))
            distances = list(map(float, row[7:13]))
            gain = float(row[13])
            real_impedance= float(row[14])+50
            img_impedance_penalty = float(row[15])
            individuals.append((lengths, distances, gain,real_impedance,img_impedance_penalty))
    
    return individuals

# Funzione per plottare la geometria di un'antenna
def plot_geometry(lengths, distances, gain, real_impedance,img_impedance_penalty):
    x_position = 0
    x_coords = [x_position]  # Posizioni sull'asse X
    y_coords = []

    for i in range(len(lengths)):
        half_length = lengths[i] / 2
        x_coords.append(x_position)
        y_coords.append(half_length)
        y_coords.append(-half_length)
        
        # Aggiorna la posizione X
        if i < len(distances):
            x_position += distances[i]
            x_coords.append(x_position)

    fig, ax = plt.subplots()
    
    # Disegna i segmenti dell'antenna
    for i in range(len(lengths)):
        ax.plot([x_coords[i*2], x_coords[i*2+1]], [y_coords[i*2], y_coords[i*2+1]], color='blue', marker='o')

    ax.set_title(f"Antenna Geometry\nMax Gain: {gain:.2f} dB, Real Impedance: {real_impedance:.2f},Img Impedance Penalty: {img_impedance_penalty:.2f}")
    ax.set_xlabel('X Position (m)')
    ax.set_ylabel('Y Position (m)')
    ax.grid(True)
    
    plt.show()

# Leggi i risultati e visualizza i migliori individui
def main():
    # Leggi i dati dal file CSV
    individuals = read_optimized_data("optimized_individuals.csv")
    
    # Mostra i primi 5 individui
    for i, (lengths, distances, gain, real_impedance,img_impedance_penalty) in enumerate(individuals[:5]):
        print(f"Individuo {i+1}:")
        print(f"  Lunghezze: {lengths}")
        print(f"  Distanze: {distances}")
        print(f"  Guadagno: {gain} dB")
        print(f"  Impedenza reale: {real_impedance}")
        print(f"  Penalità Impedenza immaginaria: {img_impedance_penalty}")
        print()
        
        # Plot della geometria dell'individuo
        plot_geometry(lengths, distances, gain, real_impedance,img_impedance_penalty)

if __name__ == "__main__":
    main()
