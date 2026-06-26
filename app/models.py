from datetime import datetime
from app import db


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Other")
    unit = db.Column(db.String(40), nullable=False, default="each")

    current_quantity = db.Column(db.Integer, nullable=False, default=0)
    minimum_quantity = db.Column(db.Integer, nullable=False, default=0)
    target_quantity = db.Column(db.Integer, nullable=True)

    location = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    # Vendor / ordering info
    vendor = db.Column(db.String(120), nullable=True)
    sku = db.Column(db.String(120), nullable=True)
    vendor_url = db.Column(db.String(500), nullable=True)
    estimated_unit_cost = db.Column(db.Float, nullable=True)

    transactions = db.relationship("InventoryTransaction", backref="item", lazy=True)
    counts = db.relationship("InventoryCount", backref="item", lazy=True,
                             order_by="InventoryCount.counted_at.desc()")


class InventoryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(40), nullable=False)

    note = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class InventoryCount(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    counted_quantity = db.Column(db.Integer, nullable=False)
    counted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    counted_by = db.Column(db.String(80), nullable=True)
    note = db.Column(db.Text, nullable=True)
