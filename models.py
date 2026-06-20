from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Location(db.Model):
    """Database model for storing saved locations."""
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Serializes the location model to a dictionary."""
        return {
            'id': self.id,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat()
        }

class AnalysisRecord(db.Model):
    """Database model for storing historical GeoWatch change analyses."""
    __tablename__ = 'analysis_records'

    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.String(10), nullable=False) # YYYY-MM-DD
    end_date = db.Column(db.String(10), nullable=False)   # YYYY-MM-DD
    vegetation_change = db.Column(db.Text, nullable=False)
    road_growth = db.Column(db.Text, nullable=False)
    water_change = db.Column(db.Text, nullable=False)
    urban_growth = db.Column(db.Text, nullable=False)
    risk_score = db.Column(db.String(50), nullable=False)
    report = db.Column(db.Text, nullable=False)
    
    # New V4 Visual Exploration Columns
    biography = db.Column(db.Text, nullable=True)
    story_json = db.Column(db.Text, nullable=True)
    future_outlook = db.Column(db.Text, nullable=True)
    timeline_json = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to evidences with cascade delete
    evidences = db.relationship('AnalysisEvidence', backref='analysis_record', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        """Serializes the analysis record to a dictionary."""
        import json
        def safe_json_load(field_val):
            if not field_val:
                return None
            try:
                return json.loads(field_val)
            except Exception:
                return field_val

        return {
            'id': self.id,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'metrics': {
                'vegetation_change': self.vegetation_change,
                'road_growth': self.road_growth,
                'water_change': self.water_change,
                'urban_growth': self.urban_growth,
                'risk_score': self.risk_score
            },
            'report': self.report,
            'biography': self.biography,
            'story_json': safe_json_load(self.story_json),
            'future_outlook': self.future_outlook,
            'timeline_json': safe_json_load(self.timeline_json),
            'created_at': self.created_at.isoformat(),
            'evidences': [ev.to_dict() for ev in self.evidences]
        }

class AnalysisEvidence(db.Model):
    """Database model for storing supporting evidence parameters for each metric."""
    __tablename__ = 'analysis_evidences'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis_records.id', ondelete='CASCADE'), nullable=False)
    metric_name = db.Column(db.String(255), nullable=False)
    metric_value = db.Column(db.String(255), nullable=False)
    source_name = db.Column(db.String(255), nullable=False)
    confidence = db.Column(db.Integer, nullable=False)
    calculation_method = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Serializes the evidence record to a dictionary."""
        return {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'source_name': self.source_name,
            'confidence': self.confidence,
            'calculation_method': self.calculation_method,
            'created_at': self.created_at.isoformat()
        }
