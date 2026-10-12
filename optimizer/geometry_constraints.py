import math


WIRE_RADIUS_M = 0.006


def minimum_center_spacing(clearance_m, wire_radius_m=WIRE_RADIUS_M):
    if clearance_m < 0 or wire_radius_m <= 0:
        raise ValueError("Clearance must be non-negative and wire radius positive.")
    return clearance_m + 2 * wire_radius_m


def repair_individual(
    individual,
    num_elements,
    min_length,
    max_length,
    min_spacing,
    max_spacing,
):
    expected_genes = num_elements + max(0, num_elements - 1)
    if len(individual) != expected_genes:
        raise ValueError(f"Expected {expected_genes} genes, got {len(individual)}.")
    if min_spacing > max_spacing:
        raise ValueError("Maximum element spacing is below the required minimum.")

    repaired = 0
    for index in range(num_elements):
        original = individual[index]
        if not math.isfinite(original):
            raise ValueError("Individual contains a non-finite element length.")
        individual[index] = min(max(original, min_length), max_length)
        repaired += individual[index] != original

    for index in range(num_elements, expected_genes):
        original = individual[index]
        if not math.isfinite(original):
            raise ValueError("Individual contains a non-finite element spacing.")
        individual[index] = min(max(original, min_spacing), max_spacing)
        repaired += individual[index] != original

    return repaired


def validate_individual(individual, num_elements, min_spacing):
    expected_genes = num_elements + max(0, num_elements - 1)
    if len(individual) != expected_genes:
        raise ValueError(f"Expected {expected_genes} genes, got {len(individual)}.")
    if any(not math.isfinite(value) for value in individual):
        raise ValueError("Individual contains a non-finite gene.")
    if any(spacing < min_spacing for spacing in individual[num_elements:]):
        raise ValueError("Adjacent antenna elements violate the minimum clearance.")