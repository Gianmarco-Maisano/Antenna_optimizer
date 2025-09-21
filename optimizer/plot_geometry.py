import csv
import matplotlib.pyplot as plt
import csv
from configparser import ConfigParser


def read_optimized_data(csv_file, config):
    individuals = []

    num_elements = int(config['GeneticAlgorithm']['num_elements']) 
    num_lengths = num_elements
    num_distances = num_elements - 1

    with open(csv_file, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  

        for row in reader:
            lengths = list(map(float, row[:num_lengths]))
            distances = list(map(float, row[num_lengths:num_lengths + num_distances]))
            
            gain = float(row[num_lengths + num_distances])
            real_impedance = float(row[num_lengths + num_distances + 1]) + 50
            img_impedance_penalty = float(row[num_lengths + num_distances + 2])

            individuals.append((lengths, distances, gain, real_impedance, img_impedance_penalty))

    return individuals

def plot_geometry(lengths, distances, gain, real_impedance,img_impedance_penalty):
    x_position = 0
    x_coords = [x_position] 
    y_coords = []

    for i in range(len(lengths)):
        half_length = lengths[i] / 2
        x_coords.append(x_position)
        y_coords.append(half_length)
        y_coords.append(-half_length)
        
        if i < len(distances):
            x_position += distances[i]
            x_coords.append(x_position)

    fig, ax = plt.subplots()
    
    for i in range(len(lengths)):
        ax.plot([x_coords[i*2], x_coords[i*2+1]], [y_coords[i*2], y_coords[i*2+1]], color='blue', marker='o')

    ax.set_title(f"Antenna Geometry\nMax Gain: {gain:.2f} dB, Real Impedance: {real_impedance:.2f},Img Impedance Penalty: {img_impedance_penalty:.2f}")
    ax.set_xlabel('X Position (m)')
    ax.set_ylabel('Y Position (m)')
    ax.grid(True)
    
    plt.show()

def main():
    config = ConfigParser()
    config.read('config.ini')

    individuals = read_optimized_data("optimized_individuals.csv", config)
    
    for i, (lengths, distances, gain, real_impedance, img_impedance_penalty) in enumerate(individuals[:5]):
        print(f"Individual {i+1}:")
        print(f"  Lengths: {lengths}")
        print(f"  Distances: {distances}")
        print(f"  Gain: {gain} dB")
        print(f"  Real impedance: {real_impedance}")
        print(f"  Imaginary impedance penalty: {img_impedance_penalty}")
        print()
        
        plot_geometry(lengths, distances, gain, real_impedance, img_impedance_penalty)


if __name__ == "__main__":
    main()
