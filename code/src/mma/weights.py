"""Quality and geolocation weights, Manuscript Table 2 and equations 1–2."""
import math

DIMENSIONS = ("INRE", "INRY", "LOCY", "INAY")
# Bit positions identify defects; they do not define penalty priority.
PENALTY_PRIORITY = ("INAY", "INRE", "INRY", "LOCY")
QUALITY_MAPPING = "table2-corrected-20261028"
CODES = ("0000", "0010", "0100", "1000", "0110", "1010", "1100", "1110",
         "0001", "0011", "0101", "1001", "0111", "1011", "1101", "1111")
SCENARIOS = ("A0", "A1") + tuple("A2_"+d for d in DIMENSIONS) + tuple("A3_"+d for d in DIMENSIONS) + ("A4_05", "A4_10", "A4_20", "C_FULLFIT")

def quality(code):
    """Return the grade and coefficient for a four-bit defect vector."""
    if not isinstance(code, str) or code not in CODES:
        raise ValueError("Evidence_Code must contain exactly four binary characters")
    grade = CODES.index(code)+1
    return grade, (17-grade)/16

def location(radius_km):
    """Piecewise location coefficient: 1, 0.5, or 0.2."""
    if isinstance(radius_km, bool) or not math.isfinite(radius_km) or radius_km < 0:
        raise ValueError("Location radius must be finite and nonnegative")
    return 1.0 if radius_km <= 0.5 else 0.5 if radius_km <= 5 else 0.2

def altered_code(code, setting, noise_u=None, noise_bit=None):
    quality(code)
    if setting in ("A0", "A1", "C_FULLFIT"):
        return code
    if setting.startswith(("A2_", "A3_")):
        k = DIMENSIONS.index(setting[3:])
        return ''.join((b if (i == k if setting.startswith("A2_") else i != k) else "0") for i,b in enumerate(code))
    probabilities = {"A4_05": 0.05, "A4_10": 0.1, "A4_20": 0.2}
    if setting not in probabilities:
        raise ValueError(f"Unknown setting: {setting}")
    if noise_u is None or not 0 <= noise_u < 1 or noise_bit not in (1,2,3,4):
        raise ValueError("Noise requires u in [0,1) and bit in 1..4")
    if noise_u >= probabilities[setting]:
        return code
    i = noise_bit-1
    return code[:i]+str(1-int(code[i]))+code[i+1:]

def post_weight(code, location_coefficient, setting="A0", noise_u=None,
                noise_bit=None, eta=1.0, kappa=1.0):
    if not math.isfinite(location_coefficient) or not 0 < location_coefficient <= 1:
        raise ValueError("Location coefficient must be in (0,1]")
    changed = altered_code(code, setting, noise_u, noise_bit)
    w = quality(changed)[1]*location_coefficient
    if setting == "A1":
        return 1.0
    if setting == "C_FULLFIT":
        if not math.isfinite(eta) or not math.isfinite(kappa) or eta <= 0 or kappa <= 0:
            raise ValueError("eta and kappa must be finite and positive")
        return eta*min(1.0,max(0.0,w**kappa))
    return w
