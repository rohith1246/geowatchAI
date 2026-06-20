import hashlib
import random
from datetime import datetime

def generate_timeline(lat, lon, start_date_str, end_date_str, final_metrics):
    """
    Generates a list of chronological timeline events between start_date and end_date.
    Interpolates metrics smoothly from baseline to final values.
    """
    try:
        start_year = datetime.strptime(start_date_str, "%Y-%m-%d").year
        end_year = datetime.strptime(end_date_str, "%Y-%m-%d").year
    except Exception:
        start_year = 2016
        end_year = 2026

    # Determine logical year steps (5-6 intervals)
    year_diff = end_year - start_year
    if year_diff <= 5:
        years = list(range(start_year, end_year + 1))
    else:
        # Generate 5-6 evenly spaced years including start and end
        step = max(1, year_diff // 5)
        years = []
        curr = start_year
        while curr < end_year:
            years.append(curr)
            curr += step
        if end_year not in years:
            years.append(end_year)

    # Setup deterministic random generator based on coordinates and years
    seed_str = f"{lat:.4f}_{lon:.4f}_{start_date_str}_{end_date_str}_replay"
    seed_hash = hashlib.md5(seed_str.encode()).hexdigest()
    local_rand = random.Random(int(seed_hash[:8], 16))

    # Parse final numeric values from final_metrics strings (e.g., "+14.2% NDVI" -> 14.2)
    def extract_float(s):
        try:
            import re
            match = re.search(r'([+-]?\d+\.?\d*)', s)
            return float(match.group(1)) if match else 0.0
        except Exception:
            return 0.0

    final_veg = extract_float(final_metrics.get('vegetation_change', '0'))
    final_water = extract_float(final_metrics.get('water_change', '0'))
    final_road = extract_float(final_metrics.get('road_growth', '0'))
    final_urban = extract_float(final_metrics.get('urban_growth', '0'))
    
    # Risk score parsing (e.g., "High (93%)" -> 93)
    final_risk = extract_float(final_metrics.get('risk_score', '10'))
    if final_risk == 0:
        final_risk = 15.0

    events = []
    num_steps = len(years)

    # Generate narratives list for descriptions
    urban_descriptions = [
        "Initial baseline conditions recorded.",
        "Initial clearing of outlying brush land and grading operations.",
        "Early road networking connections established. Light residential framing began.",
        "Road systems paving completed. Construction of secondary residential nodes accelerated.",
        "Expansion of local commercial supply facilities and utility corridors.",
        "Substantial built-up densification. Main transport and logistics corridors established."
    ]
    
    # Adjust descriptions length to match steps
    while len(urban_descriptions) < num_steps:
        urban_descriptions.append("Additional built-up sprawl and secondary infrastructure expansion.")

    for i, year in enumerate(years):
        pct = i / (num_steps - 1) if num_steps > 1 else 1.0
        
        # Interpolate values
        curr_veg = final_veg * pct
        curr_water = final_water * pct
        curr_road = final_road * pct
        curr_urban = final_urban * pct
        curr_risk = int(15 + (final_risk - 15) * pct) # Base risk starts at 15
        
        # Format strings to match metric formats
        veg_sign = "+" if curr_veg >= 0 else ""
        water_sign = "+" if curr_water >= 0 else ""
        
        metrics = {
            'vegetation_change': f"{veg_sign}{curr_veg:.1f}% NDVI",
            'water_change': f"{water_sign}{curr_water:.1f}% NDWI",
            'road_growth': f"+{curr_road:.1f} km roads",
            'urban_growth': f"+{curr_urban:.1f}% built area",
            'risk_score': f"{'High' if curr_risk > 65 else 'Medium' if curr_risk > 35 else 'Low'} ({curr_risk}%)"
        }
        
        # Build description
        desc = urban_descriptions[i]
        
        # Inject coordinates specific context dynamically
        if i > 0:
            if abs(curr_road - (final_road * (i-1) / (num_steps - 1))) > 0.5:
                desc += f" Added approx {(curr_road - (final_road * (i-1) / (num_steps - 1))):.1f} km of roadways."
            if curr_veg < 0:
                desc += f" Canopy depletion noted (NDVI dropped to {curr_veg:.1f}%)."
            elif curr_veg > 0:
                desc += f" Minor vegetative regrowth observed (NDVI increased to +{curr_veg:.1f}%)."

        events.append({
            'year': year,
            'description': desc,
            'metrics': metrics
        })

    return events
