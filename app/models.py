from . import db


class CareerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    target_role = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"<CareerProfile {self.name!r}>"
