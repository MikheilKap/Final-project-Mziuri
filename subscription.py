from app import db

class Subscription(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    service_name = db.Column(db.String(100))

    monthly_cost = db.Column(db.Float)

    renewal_date = db.Column(db.String(50))

    user_id = db.Column(db.Integer)