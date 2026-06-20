from datetime import datetime

def calculate_confidence(osm_status, weather_status, lat, lon, start_date_str, end_date_str):
    """
    Evaluates data coverage and completeness to generate a confidence score.
    Returns a dict containing the percentage score and qualitative confidence level.
    """
    score = 100

    # 1. Check data status factors (live API vs fallback model)
    if osm_status == 'fallback':
        score -= 15 # Deduct for fallback estimation
    if weather_status == 'fallback':
        score -= 15 # Deduct for fallback climate data

    # 2. Check Date Coverage factor
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        days = abs((end_date - start_date).days)
        years = days / 365.25
        
        if years < 1.0:
            score -= 10 # Short ranges are sensitive to seasonal noise
        elif years > 20.0:
            score -= 5  # Very long ranges have sensor alignment skew
    except Exception:
        score -= 5 # Deduct if date formats are corrupt

    # 3. Check geographic constraints (missing values / polar cloud cover)
    if abs(lat) > 70.0:
        score -= 10 # High latitudes have lower satellite revisit intervals
        
    # Cap score boundaries
    score = max(min(score, 100), 10)

    # 4. Classify qualitative confidence level
    if score >= 90:
        level = "Very High"
    elif score >= 75:
        level = "High"
    elif score >= 60:
        level = "Medium"
    elif score >= 40:
        level = "Low"
    else:
        level = "Very Low"

    return {
        'confidence': score,
        'level': level
    }
