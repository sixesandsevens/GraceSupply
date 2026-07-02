from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.active


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
