import subprocess
import re
import os
import configparser

# === CONFIG ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
CONFIG_PATH = os.path.abspath(CONFIG_PATH)

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

EXE_DIR = os.path.join(BASE_DIR, config['Paths']['exe_dir'])
OUT_DIR = os.path.join(BASE_DIR, config['Paths']['output_dir'])
INP_DIR = os.path.join(BASE_DIR, config['Paths']['input_dir'])
EXE_FILE = config['Paths']['exe_file']
TMP_FILE = config['Paths']['tmp_file']
frequency = float(config['Simulation']['frequency'])



def run_nec2dxs1k5():
    tmp_path = os.path.abspath(os.path.join(BASE_DIR, TMP_FILE))
    command = f"Set-Location '{EXE_DIR}'; Get-Content '{tmp_path}' | & .\\{EXE_FILE}"
    process = subprocess.run(
        ["powershell", "-Command", command],
        capture_output=True,
        text=True
    )

    return process.stdout, process.stderr


def read_nec_output(output_file):
    with open(output_file, "r") as file:
        lines = file.readlines()

    real_impedance = None
    imag_impedance = None
    max_gain_db = -999.99

    inside_impedance_section = False
    inside_radiation_section = False

    for line in lines:
        if "IMPEDANCE (OHMS)" in line:
            inside_impedance_section = True
            continue

        if "- - - RADIATION PATTERNS - - -" in line:
            inside_radiation_section = True
            continue

        if inside_impedance_section:
            if re.match(r'^\s*\d+\s+\d+', line):
                separated_values = re.findall(r'[-+]?\d*\.\d+E[-+]?\d+|[-+]?\d+\.\d+|[-+]?\d+', line)
                if len(separated_values) >= 8:
                    try:
                        real_impedance = float(separated_values[6])
                        imag_impedance = float(separated_values[7])
                    except ValueError:
                        print("Errore nel parsing dei valori di impedenza.")
                inside_impedance_section = False

        if inside_radiation_section:
            match = re.search(r"\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+([-+]?\d+\.\d+)\s+[-+]?\d+\.\d+", line)
            if match:
                total_gain = float(match.group(1))
                if total_gain > max_gain_db:
                    max_gain_db = total_gain

    return real_impedance, imag_impedance, max_gain_db

def write_tmp_file(tmp_path, nec_input_path, nec_output_path):
    with open(tmp_path, 'w') as file:
        file.write(f"{nec_input_path} \n")
        file.write(f"{nec_output_path}\n")

def convert_to_nec(individuo):
    lunghezze = individuo['lunghezze']
    distanze = individuo['distanze']

    nec_content = []
    nec_content.append("CM")
    nec_content.append("CE")

    x_position = 0

    for i in range(len(lunghezze)):
        half_length = lunghezze[i] / 2
        y1 = -half_length
        y2 = half_length

        nec_content.append(f"GW\t{i + 1}\t9\t{x_position:.3f}\t{y1:.3f}\t0\t{x_position:.3f}\t{y2:.3f}\t0\t0.006")

        if i < len(distanze):
            x_position += distanze[i]

    nec_content.append("GE\t0")
    nec_content.append(f"LD\t{len(lunghezze)}\t2\t0\t0\t37700000")
    nec_content.append("GN\t-1")
    nec_content.append("EK")
    nec_content.append("EX\t0\t2\t5\t0\t1\t0\t0\t'Voltage source (1+j0) at wire 1 segment")
    nec_content.append(f"FR\t0\t0\t0\t0\t{frequency}\t0")
    nec_content.append("EN")

    output_file = os.path.join(OUT_DIR, "output.nec")
    with open(output_file, "w") as file:
        for line in nec_content:
            file.write(line + "\n")

def convert_nec_to_inp(nec_file, inp_file, k_value):
    with open(nec_file, 'r') as nec, open(inp_file, 'w') as inp:
        for line in nec:
            if "SY k=" in line or "EN" in line:
                continue

            if 'GW' in line:
                line = re.sub(r'([+-]?\d*\.\d+|\d+)\+k', lambda match: f'{float(match.group(1)) + k_value:.2f}', line)
                line = re.sub(r'([+-]?\d*\.\d+|\d+)-k', lambda match: f'{float(match.group(1)) - k_value:.2f}', line)

            inp.write(line)

        inp.write("RP 0 19 73 1003 -90 0 5 5\n")

