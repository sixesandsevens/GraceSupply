import os
from collections import defaultdict
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, session)
from werkzeug.utils import secure_filename
from app import db
from app.models import Item, InventoryTransaction, InventoryCount

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

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_item_photo(file, item_id, old_filename=None):
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        flash("Photo must be jpg, jpeg, png, or webp.")
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


def create_transaction(item, change_amount, transaction_type, note="", created_by=""):
    txn = InventoryTransaction(
        item_id=item.id,
        change_amount=change_amount,
        transaction_type=transaction_type,
        note=note or None,
        created_by=created_by or None,
    )
    db.session.add(txn)
    return txn


def compute_usage_stats(item):
    """
    Avg weekly usage from count history, corrected for received stock between counts.
    Returns None if fewer than 2 counts exist.
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

        received = db.session.query(
            db.func.sum(InventoryTransaction.change_amount)
        ).filter(
            InventoryTransaction.item_id == item.id,
            InventoryTransaction.transaction_type == "received",
            InventoryTransaction.created_at > older.counted_at,
            InventoryTransaction.created_at <= newer.counted_at,
        ).scalar() or 0

        # True usage = what we had + what came in - what remains
        usage = older.counted_quantity + received - newer.counted_quantity
        if usage < 0:
            continue  # skip periods where net stock went up (corrections)
        deltas.append((usage / days) * 7)

    if not deltas:
        return None

    avg_weekly = sum(deltas) / len(deltas)
    weeks_remaining = (item.current_quantity / avg_weekly) if avg_weekly > 0 else None
    suggest_order = (
        max(0, item.target_quantity - item.current_quantity)
        if item.target_quantity is not None
        else None
    )

    return {
        "avg_weekly_usage": round(avg_weekly, 1),
        "weeks_remaining": round(weeks_remaining, 1) if weeks_remaining is not None else None,
        "suggest_order": suggest_order,
        "spike": len(deltas) > 1 and deltas[0] > (avg_weekly * 2),
    }


def build_item_timeline(item):
    """Unified count + transaction history sorted newest-first."""
    counts = (
        InventoryCount.query
        .filter_by(item_id=item.id)
        .order_by(InventoryCount.counted_at.desc())
        .limit(20)
        .all()
    )
    transactions = (
        InventoryTransaction.query
        .filter_by(item_id=item.id)
        .order_by(InventoryTransaction.created_at.desc())
        .all()
    )
    timeline = []
    for c in counts:
        timeline.append({
            "date": c.counted_at,
            "type": "count",
            "label": "Weekly count",
            "qty": c.counted_quantity,
            "change": None,
            "note": c.note,
            "by": c.counted_by,
        })
    for t in transactions:
        label = {
            "received": "Received stock",
            "adjustment": "Adjustment",
            "initial_count": "Initial count",
            "archived": "Archived",
        }.get(t.transaction_type, t.transaction_type)
        timeline.append({
            "date": t.created_at,
            "type": t.transaction_type,
            "label": label,
            "qty": None,
            "change": t.change_amount,
            "note": t.note,
            "by": t.created_by,
        })
    timeline.sort(key=lambda x: x["date"], reverse=True)
    return timeline


# ── Dashboard ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    total_items = Item.query.filter_by(active=True).count()
    low_items = (
        Item.query
        .filter(Item.active == True)
        .filter(Item.minimum_quantity > 0)
        .filter(Item.current_quantity <= Item.minimum_quantity)
        .order_by(Item.category, Item.name)
        .all()
    )
    last_count = (
        InventoryCount.query
        .order_by(InventoryCount.counted_at.desc())
        .first()
    )
    return render_template(
        "dashboard.html",
        total_items=total_items,
        low_count=len(low_items),
        out_count=sum(1 for i in low_items if i.current_quantity <= 0),
        low_items=low_items,
        last_count=last_count,
    )


# ── Items ─────────────────────────────────────────────────────────────────────

@bp.route("/items")
def items():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    item_query = Item.query.filter_by(active=True)
    if query:
        search = f"%{query}%"
        item_query = item_query.filter(db.or_(
            Item.name.ilike(search),
            Item.location.ilike(search),
            Item.notes.ilike(search),
            Item.vendor.ilike(search),
        ))
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
        cost_raw = request.form.get("estimated_unit_cost", "").strip()

        item = Item(
            name=name,
            category=request.form.get("category", "Other"),
            unit=request.form.get("unit", "each").strip() or "each",
            current_quantity=current_quantity,
            minimum_quantity=minimum_quantity,
            target_quantity=max(parse_int(target_raw), 0) if target_raw else None,
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
            vendor=request.form.get("vendor", "").strip() or None,
            sku=request.form.get("sku", "").strip() or None,
            vendor_url=request.form.get("vendor_url", "").strip() or None,
            estimated_unit_cost=float(cost_raw) if cost_raw else None,
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
    stats = compute_usage_stats(item)
    timeline = build_item_timeline(item)
    return render_template("item_detail.html", item=item, stats=stats, timeline=timeline)


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Item name is required.")
            return render_template("edit_item.html", item=item, categories=CATEGORIES)

        target_raw = request.form.get("target_quantity", "").strip()
        cost_raw = request.form.get("estimated_unit_cost", "").strip()

        item.name = name
        item.category = request.form.get("category", "Other")
        item.unit = request.form.get("unit", "each").strip() or "each"
        item.minimum_quantity = max(parse_int(request.form.get("minimum_quantity"), 0), 0)
        item.target_quantity = max(parse_int(target_raw), 0) if target_raw else None
        item.location = request.form.get("location", "").strip()
        item.notes = request.form.get("notes", "").strip()
        item.vendor = request.form.get("vendor", "").strip() or None
        item.sku = request.form.get("sku", "").strip() or None
        item.vendor_url = request.form.get("vendor_url", "").strip() or None
        item.estimated_unit_cost = float(cost_raw) if cost_raw else None

        photo = request.files.get("photo")
        if photo and photo.filename:
            new_fn = save_item_photo(photo, item.id, item.image_filename)
            if new_fn:
                item.image_filename = new_fn
        if request.form.get("remove_photo") and item.image_filename:
            delete_item_photo(item.image_filename)
            item.image_filename = None

        db.session.commit()
        flash("Item updated.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    return render_template("edit_item.html", item=item, categories=CATEGORIES)


@bp.route("/items/<int:item_id>/receive", methods=["POST"])
def receive_item(item_id):
    item = Item.query.get_or_404(item_id)
    quantity = parse_int(request.form.get("received_quantity"), 0)
    note = request.form.get("note", "").strip()
    received_by = request.form.get("received_by", "").strip()

    if quantity <= 0:
        flash("Received quantity must be a positive number.")
        return redirect(url_for("main.item_detail", item_id=item.id))

    item.current_quantity += quantity
    create_transaction(item, quantity, "received", note, received_by)
    db.session.commit()

    flash(f"Received {quantity} {item.unit}. New total: {item.current_quantity}.")
    return redirect(url_for("main.item_detail", item_id=item.id))


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


# ── Weekly Count ──────────────────────────────────────────────────────────────

@bp.route("/count", methods=["GET", "POST"])
def count():
    items = Item.query.filter_by(active=True).order_by(Item.category, Item.name).all()

    if request.method == "POST":
        counted_by = request.form.get("counted_by", "").strip()
        note = request.form.get("note", "").strip()
        now = datetime.utcnow()
        saved = 0
        summary_entries = []

        # Capture previous counts before saving new ones
        prev_counts = {
            item.id: (item.counts[0].counted_quantity if item.counts else None)
            for item in items
        }

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

            prev = prev_counts.get(item.id)
            summary_entries.append({
                "name": item.name,
                "unit": item.unit,
                "qty": qty,
                "prev": prev,
                "drop": max(0, (prev - qty) if prev is not None else 0),
                "low": item.minimum_quantity > 0 and qty <= item.minimum_quantity,
                "out": qty <= 0,
            })

        db.session.commit()

        drops = sorted(
            [e for e in summary_entries if e["drop"] > 0],
            key=lambda x: x["drop"],
            reverse=True,
        )[:6]

        session["count_summary"] = {
            "saved": saved,
            "low": [e for e in summary_entries if e["low"]],
            "out": [e for e in summary_entries if e["out"]],
            "drops": drops,
        }
        return redirect(url_for("main.count_summary_view"))

    return render_template("count.html", items=items, categories=CATEGORIES)


@bp.route("/count/summary")
def count_summary_view():
    summary = session.pop("count_summary", None)
    if not summary:
        return redirect(url_for("main.index"))
    return render_template("count_summary.html", summary=summary)


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


# ── Low Stock / Reorder ───────────────────────────────────────────────────────

@bp.route("/low-stock")
def low_stock():
    items = (
        Item.query
        .filter(Item.active == True)
        .filter(Item.current_quantity <= Item.minimum_quantity)
        .order_by(Item.category, Item.name)
        .all()
    )
    reorder_rows = []
    for item in items:
        suggest = (
            max(0, item.target_quantity - item.current_quantity)
            if item.target_quantity is not None
            else None
        )
        est_cost = (
            round(suggest * item.estimated_unit_cost, 2)
            if suggest and item.estimated_unit_cost
            else None
        )
        reorder_rows.append({
            "item": item,
            "suggest": suggest,
            "est_cost": est_cost,
        })
    return render_template("low_stock.html", reorder_rows=reorder_rows)
