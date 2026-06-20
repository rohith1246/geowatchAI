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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Serializes the analysis record to a dictionary."""
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
            'created_at': self.created_at.isoformat()
        }
