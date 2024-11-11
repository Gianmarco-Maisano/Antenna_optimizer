
import subprocess
import re


# Funzione per eseguire NEC2 tramite il percorso specificato
def run_nec2dxs1k5():
    exe_directory = r"C:\Users\maisa\Documents\GitHub\Antenna_optimizer\exe"  # Directory dell'eseguibile
    exe_file = r"nec2dxs1K5.exe"  # Nome del file eseguibile
    input_file = r"nec2dSopt.tmp"  # Nome del file di input
    
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


def convert_to_nec(individuo):
    lunghezze = individuo['lunghezze']
    distanze = individuo['distanze']
    guadagno = individuo['guadagno']
    impedenza_reale = individuo['impedenza_reale']
    penalita_impedenza_imaginaria = individuo['penalita_imaginary']

    # Inizio del file NEC
    nec_content = []
    nec_content.append("CM")
    nec_content.append("CE")

    # Posizione iniziale lungo l'asse X
    x_position = 0

    # Ciclo sui segmenti di filo definiti dalle lunghezze
    for i in range(len(lunghezze)):
        half_length = lunghezze[i] / 2  # Dividiamo la lunghezza per ottenere la simmetria lungo Y
        y1 = -half_length  # Coordinate Y negative per la parte inferiore
        y2 = half_length  # Coordinate Y positive per la parte superiore
        
        # Aggiungi la riga per il wire segment
        nec_content.append(f"GW\t{i + 1}\t9\t{x_position:.3f}\t{y1:.3f}\t0\t{x_position:.3f}\t{y2:.3f}\t0\t0.006")
        
        # Aggiorna la posizione X per l'elemento successivo
        if i < len(distanze):
            x_position += distanze[i]

    # Fine della geometria e altri parametri necessari per la simulazione
    nec_content.append("GE\t0")
    nec_content.append(f"LD\t{len(lunghezze)}\t2\t0\t0\t37700000")  # 37700000 è un valore comune per LD
    nec_content.append("GN\t-1")
    nec_content.append("EK")
    nec_content.append("EX\t0\t2\t5\t0\t1\t0\t0\t'Voltage source (1+j0) at wire 1 segment")
    nec_content.append("FR\t0\t0\t0\t0\t433\t0")
    nec_content.append("EN")

    # Scrivi il contenuto in un file .nec
    with open("output.nec", "w") as file:
        for line in nec_content:
            file.write(line + "\n")
"""
# Esempio di utilizzo
individuo = {
    'lunghezze': [0.343, 0.323, 0.304, 0.3, 0.296, 0.292, 0.289],
    'distanze': [0.082, 0.101, 0.136, 0.140, 0.094, 0.140],
    'guadagno': 9.44,
    'impedenza_reale': 50.6343,
    'penalita_imaginary': 0.178254
}

convert_to_nec(individuo)
"""

import re

def convert_nec_to_inp(nec_file, inp_file, k_value):
    """
    Converte un file .nec in un file .inp, sostituendo il valore di k e modificando i dati delle linee GW,
    rimuovendo la riga contenente SY k=.
    
    Args:
    nec_file (str): Il percorso del file di input .nec.
    inp_file (str): Il percorso del file di output .inp.
    k_value (float): Il valore di k da sostituire nel file .nec.
    """
    with open(nec_file, 'r') as nec, open(inp_file, 'w') as inp:
        for line in nec:
            # Rimuovi la riga con SY k=
            if "SY k=" in line or "EN" in line:
                continue  # Salta questa riga, non scriverla nel file .inp

            # Modifica le linee GW che contengono "+k" o "-k"
            if 'GW' in line:
                # Sostituire tutte le occorrenze di "+k" o "-k" con il valore effettivo di k
                line = re.sub(r'([+-]?\d*\.\d+|\d+)\+k', lambda match: f'{float(match.group(1)) + k_value:.2f}', line)
                line = re.sub(r'([+-]?\d*\.\d+|\d+)-k', lambda match: f'{float(match.group(1)) - k_value:.2f}', line)
            
            # Scrivi la riga modificata nel file .inp
            inp.write(line)
            
        inp.write("RP 0 19 73 1003 -90 0 5 5\n")