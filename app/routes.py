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


def parse_int(value, default=0):
    """Safely parse an integer from form input."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def create_transaction(item, change_amount, transaction_type, note="", created_by=""):
    txn = InventoryTransaction(
        item_id=item.id,
        change_amount=change_amount,
        transaction_type=transaction_type,
        note=note,
        created_by=created_by,
    )
    db.session.add(txn)
    return txn


@bp.route("/")
def index():
    active_items = Item.query.filter_by(active=True)
    total_items = active_items.count()
    low_count = active_items.filter(Item.current_quantity <= Item.minimum_quantity).count()
    out_count = Item.query.filter_by(active=True).filter(Item.current_quantity <= 0).count()
    recent_transactions = (
        InventoryTransaction.query
        .join(Item)
        .filter(Item.active == True)
        .order_by(InventoryTransaction.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "dashboard.html",
        total_items=total_items,
        low_count=low_count,
        out_count=out_count,
        recent_transactions=recent_transactions,
    )


@bp.route("/items")
def items():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    item_query = Item.query.filter_by(active=True)

    if query:
        search = f"%{query}%"
        item_query = item_query.filter(
            db.or_(
                Item.name.ilike(search),
                Item.location.ilike(search),
                Item.notes.ilike(search),
            )
        )

    if category:
        item_query = item_query.filter(Item.category == category)

    all_items = item_query.order_by(Item.category, Item.name).all()
    return render_template(
        "items.html",
        items=all_items,
        categories=CATEGORIES,
        selected_category=category,
        query=query,
    )


@bp.route("/items/new", methods=["GET", "POST"])
def new_item():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Item name is required.")
            return render_template("new_item.html", categories=CATEGORIES)

        current_quantity = max(parse_int(request.form.get("current_quantity"), 0), 0)
        minimum_quantity = max(parse_int(request.form.get("minimum_quantity"), 0), 0)

        item = Item(
            name=name,
            category=request.form.get("category", "Other"),
            unit=request.form.get("unit", "each").strip() or "each",
            current_quantity=current_quantity,
            minimum_quantity=minimum_quantity,
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )

        db.session.add(item)
        db.session.commit()

        if item.current_quantity:
            create_transaction(
                item,
                item.current_quantity,
                "initial_count",
                "Initial quantity entered",
            )
            db.session.commit()

        flash("Item added.")
        return redirect(url_for("main.item_detail", item_id=item.id))

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


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Item name is required.")
            return render_template("edit_item.html", item=item, categories=CATEGORIES)

        item.name = name
        item.category = request.form.get("category", "Other")
        item.unit = request.form.get("unit", "each").strip() or "each"
        item.minimum_quantity = max(parse_int(request.form.get("minimum_quantity"), 0), 0)
        item.location = request.form.get("location", "").strip()
        item.notes = request.form.get("notes", "").strip()

        db.session.commit()
        flash("Item updated.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    return render_template("edit_item.html", item=item, categories=CATEGORIES)


@bp.route("/items/<int:item_id>/adjust", methods=["POST"])
def adjust_item(item_id):
    item = Item.query.get_or_404(item_id)

    change_amount = parse_int(request.form.get("change_amount"), 0)
    note = request.form.get("note", "").strip()
    created_by = request.form.get("created_by", "").strip()

    if change_amount == 0:
        flash("Quantity change cannot be zero.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    new_quantity = item.current_quantity + change_amount
    if new_quantity < 0:
        flash("That adjustment would make the quantity negative. Inventory goblin denied.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    item.current_quantity = new_quantity
    create_transaction(item, change_amount, "adjustment", note, created_by)

    db.session.commit()

    flash("Inventory adjusted.")
    return redirect(url_for("main.item_detail", item_id=item.id))


@bp.route("/items/<int:item_id>/archive", methods=["POST"])
def archive_item(item_id):
    item = Item.query.get_or_404(item_id)
    item.active = False
    create_transaction(item, 0, "archived", "Item archived")
    db.session.commit()
    flash("Item archived.")
    return redirect(url_for("main.items"))


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
