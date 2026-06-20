import os
import requests
import io
import re
import csv
from flask import Flask, render_template, request, jsonify, send_file, make_response
from config import Config
from models import db, Location, AnalysisRecord, AnalysisEvidence
from services.evidence_engine import generate_evidence

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Ensure tables are created
with app.app_context():
    db.create_all()

# Setup Gemini API client if key is present
HAS_GEMINI = False
gemini_client = None
if app.config['GEMINI_API_KEY']:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=app.config['GEMINI_API_KEY'])
        HAS_GEMINI = True
    except Exception as e:
        app.logger.warning(f"Failed to configure Gemini API client: {e}")

@app.route('/')
def dashboard():
    """Render the dashboard main page."""
    return render_template('dashboard.html')

@app.route('/api/search', methods=['GET'])
def search_location():
    """
    Proxy search requests to OpenStreetMap's Nominatim API.
    Prevents mixed content (HTTP/HTTPS) issues on the frontend
    and supplies the required User-Agent header.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # 1. Attempt Nominatim Search with standard browser headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'http://localhost:5000/',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    params = {
        'q': query,
        'format': 'json',
        'limit': 10,
        'addressdetails': 1,
        'email': 'rohit.geowatch@outlook.com' # Helps prevent blocks
    }
    
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        results = response.json()
        
        formatted = []
        for item in results:
            formatted.append({
                'display_name': item.get('display_name'),
                'lat': float(item.get('lat', 0)),
                'lon': float(item.get('lon', 0)),
                'type': item.get('type'),
                'category': item.get('class')
            })
        return jsonify(formatted)
        
    except Exception as nominatim_error:
        app.logger.warning(f"Nominatim search failed ({nominatim_error}), attempting Photon fallback...")
        
        # 2. Fallback to Photon (Komoot API) - free geocoder with no strict rate-limiting
        try:
            photon_params = {
                'q': query,
                'limit': 10
            }
            photon_response = requests.get(
                'https://photon.komoot.io/api/',
                params=photon_params,
                timeout=5
            )
            photon_response.raise_for_status()
            photon_data = photon_response.json()
            features = photon_data.get('features', [])
            
            formatted = []
            for feat in features:
                props = feat.get('properties', {})
                geom = feat.get('geometry', {})
                coords = geom.get('coordinates', [0, 0]) # Photon returns [lon, lat]
                
                # Construct display name from address properties
                parts = []
                for field in ['name', 'street', 'city', 'state', 'country']:
                    val = props.get(field)
                    if val:
                        parts.append(str(val))
                display_name = ', '.join(parts) if parts else props.get('name', 'Unknown Location')
                
                formatted.append({
                    'display_name': display_name,
                    'lat': float(coords[1]),
                    'lon': float(coords[0]),
                    'type': props.get('osm_value'),
                    'category': props.get('osm_key')
                })
            return jsonify(formatted)
            
        except Exception as photon_error:
            app.logger.error(f"Both Nominatim and Photon geocoding failed: {photon_error}")
            return jsonify({'error': 'Geocoding services are currently unavailable.'}), 500

@app.route('/api/locations', methods=['GET'])
def get_locations():
    """Retrieve all saved locations, sorted by newest first."""
    try:
        locations = Location.query.order_by(Location.created_at.desc()).all()
        return jsonify([loc.to_dict() for loc in locations])
    except Exception as e:
        app.logger.error(f"Database error while fetching locations: {e}")
        return jsonify({'error': 'Failed to retrieve saved locations.'}), 500

@app.route('/api/locations', methods=['POST'])
def save_location():
    """Save a new location to the database."""
    data = request.get_json() or {}
    name = data.get('location_name', '').strip()
    lat = data.get('latitude')
    lon = data.get('longitude')

    if not name or lat is None or lon is None:
        return jsonify({'error': 'Missing required fields: location_name, latitude, longitude.'}), 400

    try:
        # Convert lat/lon to float to validate coordinates
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid latitude or longitude coordinates.'}), 400
    except ValueError:
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    try:
        new_loc = Location(location_name=name, latitude=lat, longitude=lon)
        db.session.add(new_loc)
        db.session.commit()
        return jsonify(new_loc.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error while saving location: {e}")
        return jsonify({'error': 'Failed to save location to the database.'}), 500

@app.route('/api/locations/<int:loc_id>', methods=['DELETE'])
def delete_location(loc_id):
    """Delete a saved location by its ID."""
    try:
        location = Location.query.get(loc_id)
        if not location:
            return jsonify({'error': 'Location not found.'}), 440
        
        db.session.delete(location)
        db.session.commit()
        return jsonify({'message': 'Location deleted successfully.', 'id': loc_id})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error while deleting location: {e}")
        return jsonify({'error': 'Failed to delete location.'}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_change():
    """
    Perform satellite imagery change detection analysis.
    Uses Gemini API if configured, otherwise falls back to a detailed
    mock generator.
    """
    data = request.get_json() or {}
    lat = data.get('latitude')
    lon = data.get('longitude')
    name = data.get('location_name', f"Coords ({lat:.4f}, {lon:.4f})").strip()

    if lat is None or lon is None:
        return jsonify({'error': 'Latitude and longitude are required for analysis.'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    if HAS_GEMINI and gemini_client:
        try:
            prompt = (
                f"You are GeoWatch AI, an advanced orbital remote sensing analyst.\n"
                f"Perform a detailed satellite imagery change detection analysis for the location: '{name}' "
                f"at coordinates Latitude: {lat:.6f}, Longitude: {lon:.6f}.\n\n"
                f"Generate a comprehensive, professional report highlighting change patterns observed "
                f"over the past decade (2016-2026). Include the following sections using clean Markdown formatting:\n"
                f"1. **Orbital Observation Summary** (Overview of geographic region, climate profile, and image quality)\n"
                f"2. **Urban Development & Encroachment** (Infrastructure growth, roads, building expansions)\n"
                f"3. **Vegetation & Canopy Dynamics** (Deforestation, agricultural changes, or reforestation efforts)\n"
                f"4. **Hydrological & Climate Risks** (Water body shrinkage/growth, surface runoffs, flooding risks)\n"
                f"5. **Orbital Predictive Risk Alert** (AI projection of key changes and vulnerabilities over the next 5 years)\n\n"
                f"Be specific, write in a premium, scientific yet accessible style. Do not use generic placeholders. "
                f"Ensure the report has a highly realistic and technical analysis based on these specific coordinates."
            )
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return jsonify({
                'analysis': response.text,
                'source': 'Gemini 2.5 Orbital Engine',
                'location': {'name': name, 'lat': lat, 'lon': lon}
            })
        except Exception as e:
            app.logger.warning(f"Gemini API request failed, falling back to mock generator. Error: {e}")
            # Fall back to mock on failure
            pass

    # High-fidelity Mock Generator (runs if GEMINI_API_KEY is not set or failed)
    mock_report = generate_mock_report(name, lat, lon)
    return jsonify({
        'analysis': mock_report,
        'source': 'GeoWatch AI Local Analysis Engine (API Sandbox Mode)',
        'location': {'name': name, 'lat': lat, 'lon': lon}
    })

@app.route('/api/analyze-change', methods=['POST'])
def analyze_temporal_change():
    """
    Perform deep satellite temporal change analysis between two dates.
    Uses public data connectors and the evidence engine to gather real telemetry
    and calls Gemini to explain the implications.
    Stores the output in the AnalysisRecord and AnalysisEvidence tables.
    """
    data = request.get_json() or {}
    lat = data.get('latitude')
    lon = data.get('longitude')
    name = data.get('location_name', f"Hotspot ({lat:.4f}, {lon:.4f})").strip()
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if lat is None or lon is None or not start_date or not end_date:
        return jsonify({'error': 'latitude, longitude, start_date, and end_date are required.'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    # 1. Run live evidence engine pipelines
    try:
        evidence_data = generate_evidence(lat, lon, start_date, end_date)
        metrics = evidence_data['metrics']
        confidence_score = evidence_data['confidence_score']
        confidence_level = evidence_data['confidence_level']
        evidence = evidence_data['evidence']
    except Exception as e:
        app.logger.error(f"Evidence generation failed: {e}")
        return jsonify({'error': 'Geospatial evidence engine failed.'}), 500

    # 2. AI report generation using prompt summarizing metrics (implications only)
    report_text = ""
    evidence_bullets = "\n".join([
        f"- **{ev['metric']}**: {ev['value']} (Source: {ev['source']}, Confidence: {ev['confidence']}%, Method: {ev['calculation']})"
        for ev in evidence
    ])
    
    if HAS_GEMINI and gemini_client:
        try:
            prompt = (
                f"You are GeoWatch AI, an advanced orbital remote sensing analyst.\n"
                f"Generate a comprehensive 'GeoWatch Change Report' for: '{name}' "
                f"at coordinates Latitude: {lat:.6f}, Longitude: {lon:.6f} comparing two dates:\n"
                f"Start Date: {start_date} and End Date: {end_date}.\n\n"
                f"Here is the verified evidence collected by our geospatial sensors and data connectors:\n"
                f"{evidence_bullets}\n\n"
                f"Data quality confidence rating: {confidence_score}% ({confidence_level} Confidence).\n\n"
                f"Your task is to write a detailed, professional, structured report in Markdown. "
                f"You must strictly summarize and explain the implications of these provided metrics. "
                f"Do not fabricate values. Do not invent environmental claims or create unsupported percentages. "
                f"Ensure that all metrics discussed in the report are directly traceable to the evidence above.\n\n"
                f"Include exactly the following sections with headings:\n"
                f"1. **Summary** (High-level narrative of planetary changes at these coordinates)\n"
                f"2. **Environmental Changes** (Analysis of vegetation/canopy shifts and moisture dynamics)\n"
                f"3. **Infrastructure Changes** (Analysis of road networks, industrial growth, and building expansion)\n"
                f"4. **Risk Assessment** (Detailed breakdown of current ecological and structural threat parameters)\n"
                f"5. **Recommendations** (Actionable mitigation strategies for regional planners)\n\n"
                f"Write in a scientific, authoritative, yet engaging tone. Avoid generic filler."
            )
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            report_text = response.text
        except Exception as e:
            app.logger.warning(f"Gemini API change report failed: {e}. Falling back to local mock report.")
            pass

    if not report_text:
        # Generate high-fidelity mock change report
        report_text = generate_mock_change_report(name, lat, lon, start_date, end_date, metrics, confidence_score, confidence_level, evidence_bullets)

    # 3. Store record & associated evidence in database
    try:
        new_record = AnalysisRecord(
            location_name=name,
            latitude=lat,
            longitude=lon,
            start_date=start_date,
            end_date=end_date,
            vegetation_change=metrics['vegetation_change'],
            road_growth=metrics['road_growth'],
            water_change=metrics['water_change'],
            urban_growth=metrics['urban_growth'],
            risk_score=metrics['risk_score'],
            report=report_text
        )
        db.session.add(new_record)
        db.session.commit() # Save first to generate new_record.id

        # Insert audit trail evidence records
        for ev in evidence:
            new_ev = AnalysisEvidence(
                analysis_id=new_record.id,
                metric_name=ev['metric'],
                metric_value=ev['value'],
                source_name=ev['source'],
                confidence=ev['confidence'],
                calculation_method=ev['calculation']
            )
            db.session.add(new_ev)
        db.session.commit()

        return jsonify({
            'id': new_record.id,
            'metrics': metrics,
            'report': report_text,
            'record': new_record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error while saving analysis: {e}")
        return jsonify({'error': 'Failed to save analysis record.'}), 500

@app.route('/api/analysis-records', methods=['GET'])
def get_analysis_records():
    """Retrieve all archived analysis reports, sorted by newest first."""
    try:
        records = AnalysisRecord.query.order_by(AnalysisRecord.created_at.desc()).all()
        return jsonify([rec.to_dict() for rec in records])
    except Exception as e:
        app.logger.error(f"Database error while fetching analysis history: {e}")
        return jsonify({'error': 'Failed to retrieve analysis history.'}), 500

@app.route('/api/analysis-records/<int:rec_id>', methods=['GET'])
def get_analysis_record(rec_id):
    """Retrieve a single archived analysis report by its ID."""
    try:
        record = AnalysisRecord.query.get(rec_id)
        if not record:
            return jsonify({'error': 'Analysis record not found.'}), 404
        return jsonify(record.to_dict())
    except Exception as e:
        app.logger.error(f"Database error while fetching analysis record: {e}")
        return jsonify({'error': 'Failed to retrieve analysis record.'}), 500

@app.route('/api/analysis-records/<int:rec_id>', methods=['DELETE'])
def delete_analysis_record(rec_id):
    """Delete an archived analysis report by its ID."""
    try:
        record = AnalysisRecord.query.get(rec_id)
        if not record:
            return jsonify({'error': 'Analysis record not found.'}), 404
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Analysis record deleted successfully.', 'id': rec_id})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error while deleting analysis record: {e}")
        return jsonify({'error': 'Failed to delete analysis record.'}), 500

@app.route('/api/analysis-records/<int:rec_id>/export/json', methods=['GET'])
def export_json_report(rec_id):
    """Export a saved analysis report as JSON."""
    try:
        record = AnalysisRecord.query.get(rec_id)
        if not record:
            return jsonify({'error': 'Record not found.'}), 404
        return jsonify(record.to_dict())
    except Exception as e:
        app.logger.error(f"Export JSON error: {e}")
        return jsonify({'error': 'Failed to export JSON.'}), 500

@app.route('/api/analysis-records/<int:rec_id>/export/csv', methods=['GET'])
def export_csv_report(rec_id):
    """Export a saved analysis report as CSV."""
    try:
        record = AnalysisRecord.query.get(rec_id)
        if not record:
            return jsonify({'error': 'Record not found.'}), 404
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write metadata
        writer.writerow(['GEOWATCH GEOREPORT AUDIT TRAIL'])
        writer.writerow([])
        writer.writerow(['Location', record.location_name])
        writer.writerow(['Latitude', record.latitude])
        writer.writerow(['Longitude', record.longitude])
        writer.writerow(['Start Date', record.start_date])
        writer.writerow(['End Date', record.end_date])
        writer.writerow(['Created At', record.created_at.isoformat()])
        writer.writerow([])
        
        # Write Evidence Table
        writer.writerow(['EVIDENCE LOGS'])
        writer.writerow(['Metric Name', 'Metric Value', 'Data Source', 'Confidence Score (%)', 'Calculation Method'])
        for ev in record.evidences:
            writer.writerow([ev.metric_name, ev.metric_value, ev.source_name, ev.confidence, ev.calculation_method])
        writer.writerow([])
        
        # Write Report Text
        writer.writerow(['AI ANALYSIS REPORT'])
        writer.writerow([record.report])
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=geowatch-report-{rec_id}.csv"
        response.headers["Content-type"] = "text/csv"
        return response
    except Exception as e:
        app.logger.error(f"Export CSV error: {e}")
        return jsonify({'error': 'Failed to export CSV.'}), 500

@app.route('/api/analysis-records/<int:rec_id>/export/pdf', methods=['GET'])
def export_pdf_report(rec_id):
    """Export a saved analysis report as PDF using reportlab."""
    try:
        record = AnalysisRecord.query.get(rec_id)
        if not record:
            return jsonify({'error': 'Record not found.'}), 404
            
        pdf_buffer = generate_pdf_report(record)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"geowatch-report-{rec_id}.pdf"
        )
    except Exception as e:
        app.logger.error(f"Export PDF error: {e}")
        return jsonify({'error': f'Failed to export PDF: {str(e)}'}), 500

def generate_pdf_report(record):
    """Compiles a print-friendly document using ReportLab layout flows."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=18
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=14,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10
    )
    
    # Document Header
    story.append(Paragraph("GeoWatch AI - Geospatial Change Report", title_style))
    meta_text = (
        f"<b>Target Region:</b> {record.location_name}<br/>"
        f"<b>Coordinates:</b> Lat: {record.latitude:.6f}, Lng: {record.longitude:.6f}<br/>"
        f"<b>Observation Timeline:</b> {record.start_date} to {record.end_date}<br/>"
        f"<b>Generated Timestamp (UTC):</b> {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(Spacer(1, 10))
    
    # Evidence Table
    story.append(Paragraph("Geospatial Telemetry & Evidence Logs", h2_style))
    
    table_data = [[
        Paragraph("<b>Metric</b>", body_style),
        Paragraph("<b>Value</b>", body_style),
        Paragraph("<b>Source</b>", body_style),
        Paragraph("<b>Confidence</b>", body_style),
        Paragraph("<b>Calculation / Method</b>", body_style)
    ]]
    
    for ev in record.evidences:
        table_data.append([
            Paragraph(ev.metric_name, body_style),
            Paragraph(ev.metric_value, body_style),
            Paragraph(ev.source_name, body_style),
            Paragraph(f"{ev.confidence}%", body_style),
            Paragraph(ev.calculation_method, body_style)
        ])
        
    t = Table(table_data, colWidths=[95, 75, 105, 60, 195])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    # AI Report content
    story.append(Paragraph("AI Change Impact Report", h2_style))
    
    # Simple formatting of markdown to paragraphs
    report_lines = record.report.split('\n')
    for line in report_lines:
        line = line.strip()
        if not line:
            continue
        
        # Heading translation
        if line.startswith('### '):
            story.append(Paragraph(line.replace('### ', ''), h2_style))
        elif line.startswith('#### '):
            story.append(Paragraph(line.replace('#### ', ''), h2_style))
        elif line.startswith('* ') or line.startswith('- '):
            bullet_text = line[2:]
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            story.append(Paragraph(f"• {bullet_text}", body_style))
        else:
            line_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(line_text, body_style))
            
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_mock_change_report(name, lat, lon, start_date, end_date, metrics, confidence_score, confidence_level, evidence_bullets):
    """Generates a highly realistic mock change detection report based on calculated metrics."""
    return f"""### 🛰️ GeoWatch Temporal Change Detection Report
**Target Location**: {name}  
**Coordinates**: {lat:.6f}° N/S, {lon:.6f}° E/W  
**Timeframe**: `{start_date}` to `{end_date}`  
**Operational Satellites**: Landsat-8/9, Sentinel-2 (Inter-temporal Synthesis)
**Data Confidence**: `{confidence_score}% ({confidence_level} Confidence)`

---

#### 1. Summary
Multi-temporal satellite imagery analysis indicates substantial surface changes at these coordinates between {start_date} and {end_date}. The analysis reveals significant trends in urban development and corresponding alterations in local environmental parameters.

#### 2. Environmental Changes
* **Vegetation/NDVI Index**: {metrics['vegetation_change']}
* **Hydrological Dynamics (NDWI)**: {metrics['water_change']}

#### 3. Infrastructure Changes
* **Road Density Networks**: {metrics['road_growth']}
* **Built-up Sprawl**: {metrics['urban_growth']}

#### 4. Risk Assessment
* **Overall threat level has been computed as {metrics['risk_score']}**.
* Environmental buffer degradation is active. Surface impermeability factors indicate a moderate increase in flash flooding potential and local temperature variations (urban heat island effect).

#### 5. Recommendations
1. **Zoning Restrictions**: Enforce ecological containment belts around regions showing extreme vegetation clearing.
2. **Hydrological Protection**: Establish green buffers along waterways to prevent siltation and manage runoff.
3. **Periodic Telemetry**: Schedule quarterly orbital sensing sweeps to monitor encroachment velocity.
"""

def generate_mock_report(name, lat, lon):
    """Generates a highly realistic, coordinate-aware satellite analysis report."""
    # Determine general biome/climate based on latitude
    abs_lat = abs(lat)
    if abs_lat < 15:
        biome = "Tropical / Rainforest Zone"
        urban_growth = "Rapid expansion of sub-urban fringes and agricultural encroachment into forested buffer zones."
        forestry = "Evidence of canopy thinning and small-scale timber trails. Loss of ~8.4% primary canopy over 10 years, with fragmented corridors."
        hydro = "Increased surface runoff variance. High sediment load detected in local tributaries during peak rain seasons. Minor riverbanks erosion."
        alert = "High risk of seasonal mudslides and accelerated soil erosion if the buffer canopy is depleted by another 3%."
    elif abs_lat < 35:
        biome = "Arid / Semi-Arid / Subtropical Zone"
        urban_growth = "Substantial industrial sprawl and road networking. Heat-island index has increased by +1.4°C over built-up areas."
        forestry = "Low baseline vegetation. Noticeable xeriscaping shift and loss of seasonal scrub grass due to prolonged dry cycles."
        hydro = "High depletion rate of surface water reservoirs, indicating a surface area decrease of 14.2% since 2016. High groundwater extraction stress."
        alert = "Water stress vulnerability index is critical. Urban growth must incorporate high-efficiency water recycling systems."
    elif abs_lat < 60:
        biome = "Temperate Zone"
        urban_growth = "Steady residential development. Commercial logistics centers expanding along major transport arteries. Greenfield conversions verified."
        forestry = "Stable forest boundary with seasonal deciduous shifts. Reforestation efforts visible in decommissioned agricultural parcels."
        hydro = "Consistent water body volumes, but minor wetland drying detected on southern perimeter. Runoff channels showing increased artificial concrete channeling."
        alert = "Increased urban runoff flooding hazards during extreme precipitation events due to soil impermeability."
    else:
        biome = "Subpolar / Polar Zone"
        urban_growth = "Sparse, localized infrastructural footprint mostly associated with research, energy, or cold-climate transit corridors."
        forestry = "Tundra shift. Minor shrub encroachment noticed in historically glaciated zones, confirming a prolonged growing window."
        hydro = "Glacial/permafrost retreat markers visible. High seasonal meltwater lake formations with rapid drainage cycles."
        alert = "Thermokarst collapse risks and structural instability for concrete foundations laid on permafrost zones."

    report = f"""### 🛰️ GeoWatch Orbital Analysis Report
**Target Location**: {name}  
**Coordinates**: {lat:.6f}° N/S, {lon:.6f}° E/W  
**Primary Biome classification**: `{biome}`  
**Operational Satellites**: Sentinel-2A/B, Landsat-8/9 (Multi-spectral Synthesis)

---

#### 1. Orbital Observation Summary
Analysis of multi-spectral satellite imagery archives from 2016 to 2026 reveals significant modifications in this coordinate grid. Surface reflectance indices indicate shifting albedo due to alterations in surface composition. Cloud-cover correction filters have been applied to compile a high-density chronological timeline.

#### 2. Urban Development & Encroachment
* **Built-up Area Expansion**: {urban_growth}
* **Road Networks**: Structural edge detection shows new access arteries linking peripheral grid cells to local industrial hubs.
* **Albedo Variation**: Dark asphalt and concrete installations have reduced surface albedo, driving a micro-thermal warming pattern.

#### 3. Vegetation & Canopy Dynamics
* **NDVI Index Trends**: Normalized Difference Vegetation Index (NDVI) values have fluctuated, with overall baseline declines.
* **Canopy Health**: {forestry}
* **Agricultural Shift**: Pivot irrigation patterns or crop rotation boundaries show structural shifts in farm boundaries.

#### 4. Hydrological & Climate Risks
* **Surface Water Index (NDWI)**: Normalized Difference Water Index suggests changes in surface moisture.
* **Runoff & Drainage**: {hydro}
* **Erosion Mapping**: Temporal change detection flags active soil movement along topographic slopes.

---

#### 5. ⚠️ Orbital Predictive Risk Alert (Next 5 Years)
* **Immediate Threat Matrix**: {alert}
* **Vulnerability Assessment**: High exposure to climate variance. Recommended mitigation: Implement green infrastructural buffers and enhance hydrological flood protection designs.
"""
    return report

if __name__ == '__main__':
    # Run the local development server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
