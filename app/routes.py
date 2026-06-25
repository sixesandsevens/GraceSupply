from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Item, InventoryTransaction

bp = Blueprint("main", __name__)

CATEGORIES = [
    "Cleaning",
    "Paper Goods",
    "Hygiene",
    "Resident Supplies",
    "Laundry",
    "Kitchen",
    "Office",
    "Maintenance Consumables",
    "Other",
]


@bp.route("/")
def index():
    return redirect(url_for("main.items"))


@bp.route("/items")
def items():
    all_items = Item.query.filter_by(active=True).order_by(Item.category, Item.name).all()
    return render_template("items.html", items=all_items)


@bp.route("/items/new", methods=["GET", "POST"])
def new_item():
    if request.method == "POST":
        item = Item(
            name=request.form["name"].strip(),
            category=request.form.get("category", "Other"),
            unit=request.form.get("unit", "each").strip(),
            current_quantity=int(request.form.get("current_quantity", 0)),
            minimum_quantity=int(request.form.get("minimum_quantity", 0)),
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )

        db.session.add(item)
        db.session.commit()

        if item.current_quantity:
            txn = InventoryTransaction(
                item_id=item.id,
                change_amount=item.current_quantity,
                transaction_type="initial_count",
                note="Initial quantity entered",
            )
            db.session.add(txn)
            db.session.commit()

        flash("Item added.")
        return redirect(url_for("main.items"))

    return render_template("new_item.html", categories=CATEGORIES)


@bp.route("/items/<int:item_id>")
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    transactions = (
        InventoryTransaction.query
        .filter_by(item_id=item.id)
        .order_by(InventoryTransaction.created_at.desc())
        .all()
    )
    return render_template("item_detail.html", item=item, transactions=transactions)


@bp.route("/items/<int:item_id>/adjust", methods=["POST"])
def adjust_item(item_id):
    item = Item.query.get_or_404(item_id)

    change_amount = int(request.form["change_amount"])
    note = request.form.get("note", "").strip()
    created_by = request.form.get("created_by", "").strip()

    item.current_quantity += change_amount

    txn = InventoryTransaction(
        item_id=item.id,
        change_amount=change_amount,
        transaction_type="adjustment",
        note=note,
        created_by=created_by,
    )

    db.session.add(txn)
    db.session.commit()

    flash("Inventory adjusted.")
    return redirect(url_for("main.item_detail", item_id=item.id))


@bp.route("/low-stock")
def low_stock():
    items = (
        Item.query
        .filter(Item.active == True)
        .filter(Item.current_quantity <= Item.minimum_quantity)
        .order_by(Item.category, Item.name)
        .all()
    )
    return render_template("low_stock.html", items=items)
