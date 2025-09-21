from NEC_tools import *
import re
import matplotlib.pyplot as plt
import pandas as pd
import os
import configparser

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'config.ini')
INP_DIR = os.path.join(BASE_DIR, '..', config['Paths']['input_dir'])
OUT_DIR = os.path.join(BASE_DIR, '..', config['Paths']['output_dir'])
main_input_file = config['Paths']['main_input_file']
main_output_file = config['Paths']['main_output_file']

# Params
k_start = float(config['Simulation']['k_start'])
k_stop = float(config['Simulation']['k_stop'])
k_step = float(config['Simulation']['k_step'])

def update_nec_input(k_value):
    input_file_path = os.path.join(INP_DIR, main_input_file)
    
    with open(input_file_path, "r") as file:
        lines = file.readlines()

    with open(input_file_path, "w") as file:
        for line in lines:
            if "k" in line:
                line = re.sub(r'k=([-+]?\d*\.\d+|\d+)', f'k={k_value}', line)
            file.write(line)

def main():
    k_values = [round(k, 2) for k in frange(k_start, k_stop, k_step)]
    results = []

    for k in k_values:
        print(f"Simulating k={k}...")
        update_nec_input(k)

        nec_file_path = os.path.join(INP_DIR, main_input_file)
        inp_file_path = os.path.join(INP_DIR, main_input_file.replace('.nec', '.inp'))
        convert_nec_to_inp(nec_file_path, inp_file_path, k)

        stdout, stderr = run_nec2dxs1k5()

        out_file_path = os.path.join(OUT_DIR, main_output_file)
        real_imp, imag_imp, max_gain = read_nec_output(out_file_path)

        results.append({
            'k': k,
            'real_impedance': real_imp,
            'imag_impedance': imag_imp,
            'max_gain_db': max_gain
        })

    df = pd.DataFrame(results)
    print(df)

    plt.figure()
    plt.plot(df['k'], df['real_impedance'], label='real_impedance')
    plt.plot(df['k'], df['imag_impedance'], label='imag_impedance', color='r', linestyle='--')
    plt.xlabel('k')
    plt.ylabel('Impedance (Ohm)')
    plt.title('Impedance vs k')
    plt.grid(True)
    plt.legend()

    plt.figure()
    plt.plot(df['k'], df['max_gain_db'], label='Max gain (dB)', color='orange')
    plt.xlabel('k')
    plt.ylabel('Max gain (dB)')
    plt.title('Max gain vs k')
    plt.grid(True)
    plt.legend()

    plt.show()

def frange(start, stop, step):
    while start <= stop:
        yield round(start, 2)
        start += step

if __name__ == "__main__":
    main()
