import logging

logger = logging.getLogger(__name__)

def generate_projection(location_name, lat, lon, final_metrics, gemini_client=None):
    """
    Generates a 2030 future projection summary based on current telemetry metrics.
    Strictly framed as a probabilistic estimate.
    """
    metrics_summary = "\n".join([f"- {k}: {v}" for k, v in final_metrics.items()])

    if gemini_client:
        try:
            prompt = (
                f"You are GeoWatch AI, an orbital remote sensing predictive modeling analyst.\n"
                f"Generate a professional, scientific 'AI Future Projection' for the year 2030 for the location "
                f"'{location_name}' (Latitude: {lat:.6f}, Longitude: {lon:.6f}) based on the following current metrics:\n"
                f"{metrics_summary}\n\n"
                f"Your task is to write a single concise paragraph (approx. 80-120 words) detailing the estimated "
                f"ecological and structural changes by 2030 if current trends persist.\n\n"
                f"Rules:\n"
                f"1. You must present all findings as probability-based estimates (e.g., 'likely to continue', "
                f"'may increase', 'unlikely without intervention'). Never claim absolute certainty.\n"
                f"2. Incorporate current metrics directly into the projection logic.\n"
                f"3. Do not invent any historical metrics.\n"
                f"4. The final paragraph must begin with the header: '[AI Projection] '"
            )
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            text = response.text.strip()
            if not text.startswith('[AI Projection]'):
                text = f"[AI Projection] {text}"
            return text
        except Exception as e:
            logger.warning(f"Gemini future projection failed: {e}. Using local fallback.")
            pass

    # High-fidelity Local Fallback Generator
    # Extract values for local generation
    import re
    def extract_float(s):
        try:
            match = re.search(r'([+-]?\d+\.?\d*)', s)
            return float(match.group(1)) if match else 0.0
        except Exception:
            return 0.0

    veg_val = extract_float(final_metrics.get('vegetation_change', '0'))
    water_val = extract_float(final_metrics.get('water_change', '0'))
    urban_val = extract_float(final_metrics.get('urban_growth', '0'))
    
    # Generate predictive statements based on rates
    urban_proj = "Urban footprint expansion is estimated to continue outward, potentially leading to further core consolidation."
    if urban_val > 15.0:
        urban_proj = f"Based on the rapid baseline expansion rate ({final_metrics['urban_growth']}), urban consolidation is highly likely to continue outward, expanding industrial and suburban fringes."
        
    water_proj = "Local hydrological moisture indices are projected to remain relatively stable."
    if water_val < -5.0:
        water_proj = f"With active water surface depletion detected ({final_metrics['water_change']}), regional water stress is likely to increase by 2030, raising agricultural supply vulnerabilities."
        
    veg_proj = "Vegetative canopy cover levels are estimated to stay within historical seasonal parameters."
    if veg_val < -5.0:
        veg_proj = f"Vegetation canopy depletion ({final_metrics['vegetation_change']}) indicates that regional biomass recovery is highly unlikely by 2030 without active conservation interventions."
    elif veg_val > 5.0:
        veg_proj = f"Vegetation regrowth indexes ({final_metrics['vegetation_change']}) point to positive recovery trends, which are projected to persist if regional land use zoning remains stable."

    projection = (
        f"[AI Projection] By the year 2030, {location_name} is projected to experience ongoing environmental modifications. "
        f"{urban_proj} {water_proj} {veg_proj} These models represent probabilistic estimations based on current orbital trends "
        f"and should be utilized as guidance for municipal zoning and climate resilience planning rather than absolute forecasts."
    )
    return projection
