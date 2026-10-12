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

OUT_DIR = os.path.join(BASE_DIR, config['Paths']['output_dir'])
INP_DIR = os.path.join(BASE_DIR, config['Paths']['input_dir'])
NECPP_BINARY = os.path.join(BASE_DIR, 'third_party', 'necpp', 'build', 'src', 'nec2++')
BUILD_SCRIPT = os.path.join(BASE_DIR, 'build_necpp.sh')
frequency = float(config['Simulation']['frequency'])


def run_necpp(input_file, output_file):
    if not os.path.isfile(NECPP_BINARY):
        subprocess.run(['sh', BUILD_SCRIPT], check=True, cwd=BASE_DIR)

    process = subprocess.run(
        [NECPP_BINARY, '-i', os.path.abspath(input_file), '-o', os.path.abspath(output_file)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    error = '' if process.returncode == 0 else process.stderr or process.stdout
    return process.stdout, error


def read_nec_output(output_file):
    result = read_nec_results(output_file)
    return result['real_impedance'], result['imag_impedance'], result['max_gain_db']


def read_nec_results(output_file):
    with open(output_file, "r") as file:
        lines = file.readlines()

    real_impedance = None
    imag_impedance = None
    max_gain_db = -999.99

    inside_impedance_section = False
    inside_radiation_section = False
    radiation_pattern = []
    number_pattern = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?')

    for line in lines:
        if "IMPEDANCE (OHMS)" in line or "ANTENNA INPUT PARAMETERS" in line:
            inside_impedance_section = True
            continue

        if "RADIATION PATTERNS" in line:
            inside_radiation_section = True
            continue

        if inside_impedance_section:
            if re.match(r'^\s*\d+\s+\d+', line):
                separated_values = number_pattern.findall(line)
                if len(separated_values) >= 8:
                    try:
                        real_impedance = float(separated_values[6])
                        imag_impedance = float(separated_values[7])
                    except ValueError:
                        print("Errore nel parsing dei valori di impedenza.")
                inside_impedance_section = False

        if inside_radiation_section:
            if line.lstrip().startswith('*****') or 'TOTAL RUN TIME' in line:
                inside_radiation_section = False
                continue
            separated_values = number_pattern.findall(line)
            if len(separated_values) >= 5:
                try:
                    theta = float(separated_values[0])
                    phi = float(separated_values[1])
                    total_gain = float(separated_values[4])
                except ValueError:
                    continue
                radiation_pattern.append({
                    'theta_deg': theta,
                    'phi_deg': phi,
                    'total_gain_dbi': total_gain,
                })
                if 0.0 <= phi <= 180.0 and total_gain > max_gain_db:
                    max_gain_db = total_gain

    return {
        'real_impedance': real_impedance,
        'imag_impedance': imag_impedance,
        'max_gain_db': max_gain_db,
        'radiation_pattern': radiation_pattern,
    }

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

