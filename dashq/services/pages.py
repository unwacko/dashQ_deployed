"""What the customer pages show: the list (page 2) and the extras (page 3).

Picture uploads are never trusted:
- Pillow must open the file as a real JPEG, PNG or WebP picture.
- Size and pixel count are limited.
- The picture is shrunk and saved again as a new JPEG (this drops hidden data like GPS).
- The file gets a random name.
"""
import io
import os
import secrets

from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = ["JPEG", "PNG", "WEBP"]
MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 1600
MAX_ITEMS = 150
MAX_EXTRAS = 30
EXTRA_KINDS = ["link", "image", "text"]


# ---------- list items (menu / services) ----------

def get_items(db, business_id, only_available=False):
    sql = "SELECT * FROM list_items WHERE business_id = ?"
    if only_available:
        sql += " AND available = 1"
    sql += " ORDER BY category, position, id"
    return db.execute(sql, (business_id,)).fetchall()


def items_by_category(items):
    # [("Coffee", [item, item]), ("Snacks", [item])]
    groups = []
    for item in items:
        category = item["category"] or "Menu"
        if not groups or groups[-1][0] != category:
            groups.append((category, []))
        groups[-1][1].append(item)
    return groups


def add_item(db, business_id, name, description="", category="", price=""):
    name = name.strip()[:60]
    if name == "":
        return "Please give the item a name."
    if len(get_items(db, business_id)) >= MAX_ITEMS:
        return f"You can have up to {MAX_ITEMS} items."
    db.execute(
        "INSERT INTO list_items (business_id, name, description, category, price) VALUES (?, ?, ?, ?, ?)",
        (business_id, name, description.strip()[:140], category.strip()[:30], price.strip()[:15]),
    )
    db.commit()
    return None


def update_item(db, business_id, item_id, form):
    name = form.get("name", "").strip()[:60]
    if name == "":
        return "Please give the item a name."
    db.execute(
        "UPDATE list_items SET name = ?, description = ?, category = ?, price = ?, available = ? "
        "WHERE business_id = ? AND id = ?",
        (name, form.get("description", "").strip()[:140], form.get("category", "").strip()[:30],
         form.get("price", "").strip()[:15], 1 if form.get("available") else 0, business_id, item_id),
    )
    db.commit()
    return None


def delete_item(db, business_id, item_id):
    db.execute("DELETE FROM list_items WHERE business_id = ? AND id = ?", (business_id, item_id))
    db.commit()


def read_choices(db, business_id, form, multi):
    """Turns the submitted list form into [(item_id, name, quantity)].
    Multi mode sends qty_<id> numbers; single mode sends one 'choice'."""
    chosen = []
    for item in get_items(db, business_id, only_available=True):
        if multi:
            try:
                quantity = int(form.get(f"qty_{item['id']}", "0"))
            except ValueError:
                quantity = 0
            quantity = max(0, min(quantity, 20))
        else:
            quantity = 1 if form.get("choice") == str(item["id"]) else 0
        if quantity > 0:
            chosen.append((item["id"], item["name"], quantity))
    return chosen


# ---------- extras (links, pictures, text) ----------

def get_extras(db, business_id):
    return db.execute(
        "SELECT * FROM extras WHERE business_id = ? ORDER BY position, id", (business_id,)
    ).fetchall()


def folder_for(data_dir, business_id):
    path = os.path.join(data_dir, "uploads", str(business_id))
    os.makedirs(path, exist_ok=True)
    return path


def clean_picture(file_bytes):
    """Returns (pillow_image, error)."""
    if len(file_bytes) == 0:
        return None, "Please choose a picture."
    if len(file_bytes) > MAX_BYTES:
        return None, "That picture is too big. The limit is 4 MB."
    try:
        image = Image.open(io.BytesIO(file_bytes))
        if image.format not in ALLOWED_FORMATS:
            return None, "Only JPEG, PNG or WebP pictures are allowed."
        width, height = image.size
        if width * height > MAX_PIXELS:
            return None, "That picture has too many pixels."
        image.verify()                                  # checks the file isn't broken
        image = Image.open(io.BytesIO(file_bytes))      # verify() uses the image up, so open again
        image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return None, "That file isn't a picture we can read."
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return image, None


def add_extra(db, data_dir, business_id, kind, title="", body="", file_bytes=b"", with_token=False):
    if kind not in EXTRA_KINDS:
        return "Pick link, picture or text."
    if len(get_extras(db, business_id)) >= MAX_EXTRAS:
        return f"You can have up to {MAX_EXTRAS} extras."
    title = title.strip()[:80]
    body = body.strip()[:1000]
    filename = None

    if kind == "link":
        if not (body.startswith("https://") or body.startswith("http://") or body.startswith("upi://")):
            return "Links must start with https://, http:// or upi://"
        if title == "":
            title = body
    elif kind == "text":
        if body == "":
            return "Please write some text."
    elif kind == "image":
        image, error = clean_picture(file_bytes)
        if error:
            return error
        filename = secrets.token_hex(16) + ".jpg"
        image.save(os.path.join(folder_for(data_dir, business_id), filename), "JPEG", quality=85)

    count = len(get_extras(db, business_id))
    db.execute(
        "INSERT INTO extras (business_id, kind, title, body, filename, show_with_token, position) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (business_id, kind, title or None, body or None, filename, 1 if with_token else 0, count),
    )
    db.commit()
    return None


def update_extra(db, business_id, extra_id, form):
    db.execute(
        "UPDATE extras SET title = ?, show_on_page = ?, show_with_token = ? WHERE business_id = ? AND id = ?",
        (form.get("title", "").strip()[:80] or None, 1 if form.get("show_on_page") else 0,
         1 if form.get("show_with_token") else 0, business_id, extra_id),
    )
    db.commit()


def delete_extra(db, data_dir, business_id, extra_id):
    row = db.execute("SELECT * FROM extras WHERE business_id = ? AND id = ?", (business_id, extra_id)).fetchone()
    if row is None:
        return
    if row["filename"]:
        path = os.path.join(folder_for(data_dir, business_id), row["filename"])
        if os.path.exists(path):
            os.remove(path)
    db.execute("DELETE FROM extras WHERE business_id = ? AND id = ?", (business_id, extra_id))
    db.commit()


def has_image(db, business_id, filename):
    return db.execute(
        "SELECT 1 FROM extras WHERE business_id = ? AND filename = ?", (business_id, filename)
    ).fetchone() is not None
