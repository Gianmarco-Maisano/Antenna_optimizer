import cmath
import math


def vswr_from_impedance(antenna_resistance_ohm, antenna_reactance_ohm, source_resistance_ohm=50.0):
    if source_resistance_ohm <= 0:
        raise ValueError("Source resistance must be positive.")
    if antenna_resistance_ohm <= 0:
        return math.inf

    denominator = math.hypot(source_resistance_ohm + antenna_resistance_ohm, antenna_reactance_ohm)
    if denominator == 0:
        return math.inf
    reflection = math.hypot(source_resistance_ohm - antenna_resistance_ohm, antenna_reactance_ohm) / denominator
    if reflection >= 1:
        return math.inf
    return (1 + reflection) / (1 - reflection)


def realized_gain_db(power_gain_db, antenna_resistance_ohm, antenna_reactance_ohm, source_resistance_ohm=50.0):
    """Return gain including mismatch loss into a real source resistance."""
    if source_resistance_ohm <= 0:
        raise ValueError("Source resistance must be positive.")
    if antenna_resistance_ohm <= 0 or power_gain_db <= -999.0:
        return -999.99

    denominator = (
        (source_resistance_ohm + antenna_resistance_ohm) ** 2
        + antenna_reactance_ohm**2
    )
    mismatch_efficiency = 4 * source_resistance_ohm * antenna_resistance_ohm / denominator
    if mismatch_efficiency <= 0 or not math.isfinite(mismatch_efficiency):
        return -999.99

    return power_gain_db + 10 * math.log10(min(mismatch_efficiency, 1.0))


def transform_feed_impedance(
    antenna_resistance_ohm,
    antenna_reactance_ohm,
    frequency_mhz,
    coax_length_m=0.0,
    coax_impedance_ohm=50.0,
    velocity_factor=0.66,
    loss_db_per_100m=0.0,
    balun_impedance_ratio=1.0,
):
    """Transform feed impedance through lossy coax and an ideal balun.

    ``balun_impedance_ratio`` is Z_at_antenna_side / Z_at_radio_side.
    """
    if coax_length_m < 0 or coax_impedance_ohm <= 0 or velocity_factor <= 0:
        raise ValueError("Coax length, impedance, and velocity factor must be valid.")
    if loss_db_per_100m < 0 or balun_impedance_ratio <= 0:
        raise ValueError("Coax loss must be non-negative and balun ratio positive.")

    antenna_impedance = complex(antenna_resistance_ohm, antenna_reactance_ohm) / balun_impedance_ratio
    if coax_length_m == 0:
        impedance_after_coax = antenna_impedance
    else:
        speed_of_light = 299_792_458.0
        frequency_hz = frequency_mhz * 1_000_000
        attenuation_nepers_per_m = loss_db_per_100m / 100 / 8.685889638
        phase_per_m = 2 * math.pi * frequency_hz / (speed_of_light * velocity_factor)
        propagation = complex(attenuation_nepers_per_m, phase_per_m) * coax_length_m
        tanh_propagation = cmath.tanh(propagation)
        z0 = coax_impedance_ohm
        impedance_after_coax = z0 * (
            antenna_impedance + z0 * tanh_propagation
        ) / (
            z0 + antenna_impedance * tanh_propagation
        )

    radio_impedance = impedance_after_coax
    coax_loss_db = loss_db_per_100m * coax_length_m / 100
    return radio_impedance.real, radio_impedance.imag, coax_loss_db