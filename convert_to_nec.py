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

# Esempio di utilizzo
individuo = {
    'lunghezze': [0.343, 0.323, 0.304, 0.3, 0.296, 0.292, 0.289],
    'distanze': [0.082, 0.101, 0.136, 0.140, 0.094, 0.140],
    'guadagno': 9.44,
    'impedenza_reale': 50.6343,
    'penalita_imaginary': 0.178254
}

convert_to_nec(individuo)
