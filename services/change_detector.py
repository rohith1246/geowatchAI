import hashlib
import random
from datetime import datetime

def detect_temporal_changes(lat, lon, start_date_str, end_date_str):
    """
    Simulates change telemetry between two dates based on coordinates and duration.
    Uses MD5 hashing of coordinates and dates to remain fully deterministic across calls.
    """
    # Parse dates to calculate duration in years
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        days = abs((end_date - start_date).days)
        years = days / 365.25
    except Exception:
        years = 5.0  # Fallback duration if date parsing fails

    # Make sure we scale changes based on duration
    # 10 years of delta = scale 1.0. Max out scale at 2.0 (20 years) to keep it realistic.
    scale = min(max(years / 10.0, 0.1), 2.0)

    # Establish a deterministic seed from coordinates and dates
    seed_str = f"{lat:.4f}_{lon:.4f}_{start_date_str}_{end_date_str}"
    seed_hash = hashlib.md5(seed_str.encode()).hexdigest()
    # Seed the local random generator so it doesn't affect global random state
    local_rand = random.Random(int(seed_hash[:8], 16))

    # Biome-based telemetry generation depending on absolute latitude
    abs_lat = abs(lat)

    if abs_lat < 15:
        # Biome: Tropical / Equatorial
        veg_val = -local_rand.uniform(2.5, 11.5) * scale
        road_val = local_rand.uniform(1.0, 6.0) * scale
        water_val = -local_rand.uniform(1.5, 8.5) * scale
        urban_val = local_rand.uniform(3.5, 14.0) * scale

        veg_desc = f"Forest canopy cover decreased by {veg_val:.1f}% due to agricultural conversion and timber harvesting."
        road_desc = f"Expansion of dirt tracks and regional roads increased access grid density by +{road_val:.1f} km."
        water_desc = f"Wetlands and local tributaries surface water volume changed by {water_val:.1f}% (surface shrinkage)."
        urban_desc = f"Peripheral sub-urban footprint expanded outwards by +{urban_val:.1f}%."
        risk_num = int(min(20 + (abs(veg_val) * 3) + (urban_val * 2.2), 100))

    elif abs_lat < 35:
        # Biome: Arid / Subtropical (e.g. Hyderabad, Middle East, Saharan fringe)
        veg_val = -local_rand.uniform(0.5, 4.5) * scale
        road_val = local_rand.uniform(4.5, 22.0) * scale
        water_val = -local_rand.uniform(4.0, 24.0) * scale
        urban_val = local_rand.uniform(9.0, 36.0) * scale

        veg_desc = f"Native scrubland and sparse vegetation canopy decreased by {veg_val:.1f}% due to micro-climatic dry cycles."
        road_desc = f"Urban grid connectivity increased. Paved asphalt networks grew by +{road_val:.1f} km."
        water_desc = f"Critical local reservoir surface area shrank by {water_val:.1f}% due to extraction and high evaporation."
        urban_desc = f"Residential and commercial built-up sectors expanded footprint by +{urban_val:.1f}%."
        risk_num = int(min(15 + (abs(water_val) * 1.8) + (urban_val * 1.6), 100))

    elif abs_lat < 60:
        # Biome: Temperate
        veg_val = local_rand.uniform(-4.0, 2.5) * scale
        road_val = local_rand.uniform(2.0, 11.0) * scale
        water_val = local_rand.uniform(-3.5, 1.5) * scale
        urban_val = local_rand.uniform(4.5, 18.0) * scale

        veg_sign = "+" if veg_val >= 0 else ""
        water_sign = "+" if water_val >= 0 else ""

        veg_desc = f"Forest and canopy area shifted by {veg_sign}{veg_val:.1f}% (minor logging balanced by replanting campaigns)."
        road_desc = f"Suburban spur arteries and bypass lanes added +{road_val:.1f} km of paved surface."
        water_desc = f"Local river margins and marshland pools fluctuated in area by {water_sign}{water_val:.1f}%."
        urban_desc = f"Greenfield development and residential subdivisions expanded footprint by +{urban_val:.1f}%."
        risk_num = int(min(10 + (urban_val * 2.0), 100))

    else:
        # Biome: Polar / Subpolar / Tundra
        veg_val = local_rand.uniform(1.2, 5.8) * scale  # greening effect
        road_val = local_rand.uniform(0.05, 1.5) * scale
        water_val = -local_rand.uniform(10.0, 28.0) * scale  # glacial retreats
        urban_val = local_rand.uniform(0.2, 2.5) * scale

        veg_desc = f"Tundra shrub density grew by +{veg_val:.1f}%, indicating a longer seasonal vegetative window."
        road_desc = f"Added +{road_val:.1f} km of gravel support pathways near industrial/research units."
        water_desc = f"Glacial meltwater and thermokarst lakes showed a surface area decrease of {water_val:.1f}%."
        urban_desc = f"Infrastructural support units for research/exploration expanded footprint by +{urban_val:.1f}%."
        risk_num = int(min(30 + (abs(water_val) * 2.2), 100))

    # Classify Risk Score based on risk_num
    if risk_num < 35:
        risk_score = f"Low ({risk_num}%)"
    elif risk_num < 65:
        risk_score = f"Medium ({risk_num}%)"
    else:
        risk_score = f"High ({risk_num}%)"

    return {
        'vegetation_change': veg_desc,
        'road_growth': road_desc,
        'water_change': water_desc,
        'urban_growth': urban_desc,
        'risk_score': risk_score
    }
