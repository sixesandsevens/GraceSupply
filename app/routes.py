import os
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import Item, InventoryTransaction, InventoryCount

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_item_photo(file, item_id, old_filename=None):
    """Save uploaded photo. Returns new filename, or None if no valid file."""
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        flash("Photo must be a jpg, jpeg, png, or webp file.")
        return None

    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    new_filename = f"item-{item_id}.{ext}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]

    if old_filename and old_filename != new_filename:
        old_path = os.path.join(upload_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    file.save(os.path.join(upload_dir, new_filename))
    return new_filename


def delete_item_photo(filename):
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        os.remove(path)

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


def compute_usage_stats(item):
    """
    Returns avg weekly usage and estimated weeks remaining based on count history.
    Needs at least 2 counts. Returns None if insufficient data.
    """
    counts = (
        InventoryCount.query
        .filter_by(item_id=item.id)
        .order_by(InventoryCount.counted_at.desc())
        .limit(6)
        .all()
    )

    if len(counts) < 2:
        return None

    deltas = []
    for i in range(len(counts) - 1):
        newer = counts[i]
        older = counts[i + 1]
        days = (newer.counted_at - older.counted_at).days
        if days <= 0:
            continue
        usage = older.counted_quantity - newer.counted_quantity
        deltas.append((usage / days) * 7)

    if not deltas:
        return None

    avg_weekly = sum(deltas) / len(deltas)
    weeks_remaining = (item.current_quantity / avg_weekly) if avg_weekly > 0 else None
    suggest_order = None
    if item.target_quantity and avg_weekly > 0:
        suggest_order = max(0, item.target_quantity - item.current_quantity)

    return {
        "avg_weekly_usage": round(avg_weekly, 1),
        "weeks_remaining": round(weeks_remaining, 1) if weeks_remaining is not None else None,
        "suggest_order": suggest_order,
        "spike": avg_weekly > 0 and len(deltas) > 1 and deltas[0] > avg_weekly * 2,
    }


# ── Dashboard ────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    active_q = Item.query.filter_by(active=True)
    total_items = active_q.count()

    low_items = (
        Item.query
        .filter(Item.active == True)
        .filter(Item.minimum_quantity > 0)
        .filter(Item.current_quantity <= Item.minimum_quantity)
        .order_by(Item.category, Item.name)
        .all()
    )
    low_count = len(low_items)
    out_count = sum(1 for i in low_items if i.current_quantity <= 0)

    last_count = (
        InventoryCount.query
        .order_by(InventoryCount.counted_at.desc())
        .first()
    )

    return render_template(
        "dashboard.html",
        total_items=total_items,
        low_count=low_count,
        out_count=out_count,
        low_items=low_items,
        last_count=last_count,
    )


# ── Items ────────────────────────────────────────────────────────────────────

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
        target_raw = request.form.get("target_quantity", "").strip()
        target_quantity = max(parse_int(target_raw), 0) if target_raw else None

        item = Item(
            name=name,
            category=request.form.get("category", "Other"),
            unit=request.form.get("unit", "each").strip() or "each",
            current_quantity=current_quantity,
            minimum_quantity=minimum_quantity,
            target_quantity=target_quantity,
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )

        db.session.add(item)
        db.session.commit()

        photo = request.files.get("photo")
        if photo and photo.filename:
            item.image_filename = save_item_photo(photo, item.id)
            db.session.commit()

        if item.current_quantity:
            ic = InventoryCount(
                item_id=item.id,
                counted_quantity=item.current_quantity,
                counted_at=datetime.utcnow(),
                note="Initial count on item creation",
            )
            db.session.add(ic)
            db.session.commit()

        flash("Item added.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    return render_template("new_item.html", categories=CATEGORIES)


@bp.route("/items/<int:item_id>")
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    recent_counts = (
        InventoryCount.query
        .filter_by(item_id=item.id)
        .order_by(InventoryCount.counted_at.desc())
        .limit(10)
        .all()
    )
    transactions = (
        InventoryTransaction.query
        .filter_by(item_id=item.id)
        .order_by(InventoryTransaction.created_at.desc())
        .all()
    )
    stats = compute_usage_stats(item)
    return render_template(
        "item_detail.html",
        item=item,
        recent_counts=recent_counts,
        transactions=transactions,
        stats=stats,
    )


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Item name is required.")
            return render_template("edit_item.html", item=item, categories=CATEGORIES)

        target_raw = request.form.get("target_quantity", "").strip()
        item.name = name
        item.category = request.form.get("category", "Other")
        item.unit = request.form.get("unit", "each").strip() or "each"
        item.minimum_quantity = max(parse_int(request.form.get("minimum_quantity"), 0), 0)
        item.target_quantity = max(parse_int(target_raw), 0) if target_raw else None
        item.location = request.form.get("location", "").strip()
        item.notes = request.form.get("notes", "").strip()

        photo = request.files.get("photo")
        if photo and photo.filename:
            new_filename = save_item_photo(photo, item.id, item.image_filename)
            if new_filename:
                item.image_filename = new_filename

        if request.form.get("remove_photo") and item.image_filename:
            delete_item_photo(item.image_filename)
            item.image_filename = None

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
        flash("That adjustment would make the quantity negative.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    item.current_quantity = new_quantity
    create_transaction(item, change_amount, "adjustment", note, created_by)
    db.session.commit()

    flash("Adjustment saved.")
    return redirect(url_for("main.item_detail", item_id=item.id))


@bp.route("/items/<int:item_id>/archive", methods=["POST"])
def archive_item(item_id):
    item = Item.query.get_or_404(item_id)
    item.active = False
    delete_item_photo(item.image_filename)
    item.image_filename = None
    create_transaction(item, 0, "archived", "Item archived")
    db.session.commit()
    flash("Item archived.")
    return redirect(url_for("main.items"))


# ── Weekly Count ─────────────────────────────────────────────────────────────

@bp.route("/count", methods=["GET", "POST"])
def count():
    items = Item.query.filter_by(active=True).order_by(Item.category, Item.name).all()

    if request.method == "POST":
        counted_by = request.form.get("counted_by", "").strip()
        note = request.form.get("note", "").strip()
        now = datetime.utcnow()
        saved = 0

        for item in items:
            raw = request.form.get(f"qty_{item.id}", "").strip()
            if raw == "":
                continue
            qty = parse_int(raw, -1)
            if qty < 0:
                continue

            ic = InventoryCount(
                item_id=item.id,
                counted_quantity=qty,
                counted_at=now,
                counted_by=counted_by or None,
                note=note or None,
            )
            db.session.add(ic)
            item.current_quantity = qty
            saved += 1

        db.session.commit()
        flash(f"Count saved — {saved} item{'s' if saved != 1 else ''} updated.")
        return redirect(url_for("main.index"))

    return render_template("count.html", items=items, categories=CATEGORIES)


@bp.route("/count/history")
def count_history():
    counts = (
        InventoryCount.query
        .join(Item)
        .filter(Item.active == True)
        .order_by(InventoryCount.counted_at.desc())
        .limit(300)
        .all()
    )

    sessions = defaultdict(list)
    for c in counts:
        key = (c.counted_at.date(), c.counted_by or "")
        sessions[key].append(c)

    session_list = [
        {"date": k[0], "counted_by": k[1], "counts": v}
        for k, v in sorted(sessions.items(), reverse=True)
    ]

    return render_template("count_history.html", sessions=session_list)


# ── Low Stock ────────────────────────────────────────────────────────────────

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
