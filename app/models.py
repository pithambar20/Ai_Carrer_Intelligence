import json
from datetime import datetime, timezone
from . import db


class CareerProfile(db.Model):
    __tablename__ = "career_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    target_role = db.Column(db.String(120), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<CareerProfile {self.name!r} - {self.target_role!r}>"


class ResumeAnalysis(db.Model):
    __tablename__ = "resume_analyses"

    id = db.Column(db.Integer, primary_key=True)
    candidate_name = db.Column(
        db.String(150), nullable=True, default="Candidate"
    )
    target_role = db.Column(db.String(150), nullable=False)
    match_score = db.Column(db.Integer, nullable=False, default=0)
    summary = db.Column(db.Text, nullable=True)
    analysis_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def get_analysis_dict(self):
        """Safely deserializes analysis_json into a Python dictionary."""
        try:
            return json.loads(self.analysis_json) if self.analysis_json else {}
        except (ValueError, TypeError):
            return {}

    def set_analysis_dict(self, data):
        """Serializes a Python dictionary to the analysis_json text column."""
        self.analysis_json = json.dumps(data, ensure_ascii=False)

    @property
    def score_badge_class(self):
        """Returns CSS class based on ATS match score."""
        if self.match_score >= 80:
            return "score-high"
        elif self.match_score >= 60:
            return "score-medium"
        return "score-low"

    @property
    def score_label(self):
        """Returns human-readable rating label based on score."""
        if self.match_score >= 80:
            return "Strong Match"
        elif self.match_score >= 60:
            return "Moderate Match"
        return "Needs Improvement"

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_name": self.candidate_name,
            "target_role": self.target_role,
            "match_score": self.match_score,
            "summary": self.summary,
            "analysis": self.get_analysis_dict(),
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M UTC")
                if self.created_at
                else ""
            ),
        }

    def __repr__(self):
        return f"<ResumeAnalysis id={self.id} role={self.target_role!r} score={self.match_score}>"

