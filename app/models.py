from datetime import datetime
from app import db


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Other")
    unit = db.Column(db.String(40), nullable=False, default="each")

    current_quantity = db.Column(db.Integer, nullable=False, default=0)
    minimum_quantity = db.Column(db.Integer, nullable=False, default=0)

    location = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    transactions = db.relationship("InventoryTransaction", backref="item", lazy=True)


class InventoryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(40), nullable=False)

    note = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
