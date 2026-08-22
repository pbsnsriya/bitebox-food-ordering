import os
import re
import secrets
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)
from werkzeug.utils import secure_filename

from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


app = Flask(__name__)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///"
    + os.path.join(
        BASE_DIR,
        "food_ordering.db"
    )
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY"
) or secrets.token_hex(32)

app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
    hours=12
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = (
    5 * 1024 * 1024
)

db = SQLAlchemy(app)

jwt = JWTManager(app)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)


class User(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(160),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="customer"
    )


class MenuItem(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    description = db.Column(
        db.Text,
        default=""
    )

    category = db.Column(
        db.String(80),
        nullable=False
    )

    price = db.Column(
        db.Float,
        nullable=False
    )

    tags = db.Column(
        db.String(255),
        default=""
    )

    available = db.Column(
        db.Boolean,
        default=True
    )

    image = db.Column(
        db.String(500),
        default=""
    )


class Order(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="Placed"
    )

    total = db.Column(
        db.Float,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan"
    )


class OrderItem(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("order.id"),
        nullable=False
    )

    menu_item_id = db.Column(
        db.Integer,
        nullable=False
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    price = db.Column(
        db.Float,
        nullable=False
    )


lemmatizer = WordNetLemmatizer()

synonyms = {
    "veg": "vegetarian",
    "veggie": "vegetarian",
    "plantbased": "vegetarian",
    "hot": "spicy",
    "fiery": "spicy",
    "chilli": "spicy",
    "chili": "spicy",
    "light": "healthy",
    "diet": "healthy",
    "lowcal": "healthy",
    "crispy": "fried",
    "deepfried": "fried",
    "meal": "lunch"
}

negations = {
    "not",
    "without",
    "avoid",
    "no",
    "dont",
    "don't"
}


def normalise(text):
    words = re.findall(
        r"[a-zA-Z]+",
        str(text).lower()
    )

    result = []

    for word in words:
        word = synonyms.get(
            word,
            word
        )

        try:
            word = lemmatizer.lemmatize(
                word
            )
        except LookupError:
            pass

        result.append(word)

    return result


def menu_text(item):
    return " ".join([
        item.name,
        item.description,
        item.category,
        item.tags.replace(",", " ")
    ])


def serialise_menu_item(item):
    tags = []

    if item.tags:
        tags = [
            tag.strip()
            for tag in item.tags.split(",")
            if tag.strip()
        ]

    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price": item.price,
        "tags": tags,
        "available": item.available,
        "image": item.image
    }


def serialise_order(order):
    return {
        "id": order.id,
        "status": order.status,
        "total": round(
            order.total,
            2
        ),
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "id": item.menu_item_id,
                "name": item.name,
                "quantity": item.quantity,
                "price": item.price
            }
            for item in order.items
        ]
    }


def get_current_user():
    identity = get_jwt_identity()

    if identity is None:
        return None

    try:
        user_id = int(identity)
    except (
        TypeError,
        ValueError
    ):
        return None

    return db.session.get(
        User,
        user_id
    )


def admin_required():
    user = get_current_user()

    if not user:
        return None

    if user.role != "admin":
        return None

    return user


def allowed_image(filename):
    extensions = {
        "png",
        "jpg",
        "jpeg",
        "webp"
    }

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    return extension in extensions


def save_image(file):
    if not file:
        return ""

    if not file.filename:
        return ""

    if not allowed_image(
        file.filename
    ):
        return None

    filename = secure_filename(
        file.filename
    )

    base, extension = os.path.splitext(
        filename
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    filename = (
        base
        + "_"
        + timestamp
        + extension
    )

    file.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    return (
        "/uploads/"
        + filename
    )


def search_menu(query):
    items = MenuItem.query.filter_by(
        available=True
    ).all()

    if not items:
        return []

    query_words = normalise(
        query
    )

    query_text = " ".join(
        query_words
    )

    if not query_text:
        return [
            serialise_menu_item(item)
            for item in items
        ]

    documents = [
        " ".join(
            normalise(
                menu_text(item)
            )
        )
        for item in items
    ]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True
    )

    matrix = vectorizer.fit_transform(
        documents + [query_text]
    )

    scores = cosine_similarity(
        matrix[-1],
        matrix[:-1]
    ).flatten()

    budget_match = re.search(
        r"(?:under|below|less than|upto|up to)"
        r"\s*(?:rs\.?|₹)?\s*(\d+)",
        str(query).lower()
    )

    budget = None

    if budget_match:
        budget = float(
            budget_match.group(1)
        )

    negative_words = set()

    for index, word in enumerate(
        query_words
    ):
        if (
            word in negations
            and index + 1 < len(query_words)
        ):
            next_word = synonyms.get(
                query_words[index + 1],
                query_words[index + 1]
            )

            negative_words.add(
                next_word
            )

    results = []

    for item, score in zip(
        items,
        scores
    ):
        final_score = float(
            score
        )

        item_words = set(
            normalise(
                menu_text(item)
            )
        )

        if budget is not None:
            if item.price <= budget:
                final_score += 0.25
            else:
                final_score -= 0.35

        for word in negative_words:
            if word in item_words:
                final_score -= 0.60

        item_tags = set(
            normalise(
                item.tags
            )
        )

        for word in query_words:
            if word in item_tags:
                final_score += 0.12

        results.append(
            (
                final_score,
                item
            )
        )

    results.sort(
        key=lambda value: value[0],
        reverse=True
    )

    response = []

    for score, item in results:
        if score <= 0.02:
            continue

        data = serialise_menu_item(
            item
        )

        data["match_score"] = round(
            max(
                0,
                score
            ),
            3
        )

        response.append(
            data
        )

    return response


@app.get("/api/health")
def health():
    return jsonify({
        "message": "Food Ordering API is running"
    })


@app.post("/api/auth/signup")
def signup():
    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    email = str(
        data.get(
            "email",
            ""
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            ""
        )
    )

    if not name:
        return jsonify({
            "error": "Name is required."
        }), 400

    if not email:
        return jsonify({
            "error": "Email is required."
        }), 400

    if len(password) < 6:
        return jsonify({
            "error": "Password must contain at least 6 characters."
        }), 400

    existing = User.query.filter_by(
        email=email
    ).first()

    if existing:
        return jsonify({
            "error": "An account with this email already exists."
        }), 409

    user = User(
        name=name,
        email=email,
        password=generate_password_hash(
            password
        ),
        role="customer"
    )

    db.session.add(user)
    db.session.commit()

    token = create_access_token(
        identity=str(
            user.id
        )
    )

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(
        silent=True
    ) or {}

    email = str(
        data.get(
            "email",
            ""
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            ""
        )
    )

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:
        return jsonify({
            "error": "Invalid email or password."
        }), 401

    if not check_password_hash(
        user.password,
        password
    ):
        return jsonify({
            "error": "Invalid email or password."
        }), 401

    token = create_access_token(
        identity=str(
            user.id
        )
    )

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    })


@app.get("/api/menu")
def get_menu():
    category = request.args.get(
        "category"
    )

    query = MenuItem.query.filter_by(
        available=True
    )

    if category and category != "All":
        query = query.filter_by(
            category=category
        )

    items = query.order_by(
        MenuItem.id.desc()
    ).all()

    return jsonify([
        serialise_menu_item(item)
        for item in items
    ])


@app.get("/api/menu/search")
def menu_search():
    query = request.args.get(
        "q",
        ""
    )

    return jsonify({
        "query": query,
        "results": search_menu(
            query
        )
    })


@app.get("/uploads/<path:filename>")
def uploaded_image(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


@app.get("/api/admin/menu")
@jwt_required()
def admin_get_menu():
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    items = MenuItem.query.order_by(
        MenuItem.id.desc()
    ).all()

    return jsonify([
        serialise_menu_item(item)
        for item in items
    ])


@app.post("/api/admin/menu")
@jwt_required()
def admin_add_menu():
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    name = request.form.get(
        "name",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    tags = request.form.get(
        "tags",
        ""
    ).strip()

    image_url = request.form.get(
        "image",
        ""
    ).strip()

    price_value = request.form.get(
        "price",
        "0"
    )

    available_value = request.form.get(
        "available",
        "true"
    ).lower()

    try:
        price = float(
            price_value
        )
    except (
        TypeError,
        ValueError
    ):
        return jsonify({
            "error": "Invalid price."
        }), 400

    if not name:
        return jsonify({
            "error": "Food name is required."
        }), 400

    if not category:
        return jsonify({
            "error": "Category is required."
        }), 400

    if price <= 0:
        return jsonify({
            "error": "Price must be greater than zero."
        }), 400

    image = image_url

    if "image" in request.files:
        uploaded = save_image(
            request.files["image"]
        )

        if uploaded is None:
            return jsonify({
                "error": "Only PNG, JPG, JPEG and WEBP images are allowed."
            }), 400

        if uploaded:
            image = uploaded

    available = available_value in {
        "true",
        "1",
        "yes",
        "on"
    }

    item = MenuItem(
        name=name,
        description=description,
        category=category,
        price=price,
        tags=tags,
        available=available,
        image=image
    )

    db.session.add(item)
    db.session.commit()

    return jsonify(
        serialise_menu_item(item)
    ), 201


@app.put("/api/admin/menu/<int:item_id>")
@jwt_required()
def admin_update_menu(item_id):
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    item = db.session.get(
        MenuItem,
        item_id
    )

    if not item:
        return jsonify({
            "error": "Menu item not found."
        }), 404

    name = request.form.get(
        "name"
    )

    description = request.form.get(
        "description"
    )

    category = request.form.get(
        "category"
    )

    tags = request.form.get(
        "tags"
    )

    price_value = request.form.get(
        "price"
    )

    available_value = request.form.get(
        "available"
    )

    if name is not None:
        item.name = name.strip()

    if description is not None:
        item.description = description.strip()

    if category is not None:
        item.category = category.strip()

    if tags is not None:
        item.tags = tags.strip()

    if price_value is not None:
        try:
            item.price = float(
                price_value
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "error": "Invalid price."
            }), 400

    if available_value is not None:
        item.available = (
            available_value.lower()
            in {
                "true",
                "1",
                "yes",
                "on"
            }
        )

    if "image" in request.files:
        uploaded = save_image(
            request.files["image"]
        )

        if uploaded is None:
            return jsonify({
                "error": "Only PNG, JPG, JPEG and WEBP images are allowed."
            }), 400

        if uploaded:
            item.image = uploaded

    db.session.commit()

    return jsonify(
        serialise_menu_item(item)
    )


@app.delete("/api/admin/menu/<int:item_id>")
@jwt_required()
def admin_delete_menu(item_id):
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    item = db.session.get(
        MenuItem,
        item_id
    )

    if not item:
        return jsonify({
            "error": "Menu item not found."
        }), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({
        "message": "Menu item removed successfully."
    })


@app.patch("/api/admin/menu/<int:item_id>/availability")
@jwt_required()
def update_availability(item_id):
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    item = db.session.get(
        MenuItem,
        item_id
    )

    if not item:
        return jsonify({
            "error": "Menu item not found."
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    if "available" not in data:
        return jsonify({
            "error": "Availability value is required."
        }), 400

    item.available = bool(
        data["available"]
    )

    db.session.commit()

    return jsonify(
        serialise_menu_item(item)
    )


@app.post("/api/orders")
@jwt_required()
def create_order():
    user = get_current_user()

    if not user:
        return jsonify({
            "error": "Your login session is invalid."
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    cart = data.get(
        "items",
        []
    )

    if not isinstance(
        cart,
        list
    ):
        return jsonify({
            "error": "Order items must be a list."
        }), 400

    if not cart:
        return jsonify({
            "error": "Your cart is empty."
        }), 400

    order_items = []
    total = 0

    for entry in cart:
        item_id = entry.get(
            "menu_item_id",
            entry.get("id")
        )

        try:
            item_id = int(
                item_id
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "error": "Invalid menu item ID."
            }), 400

        try:
            quantity = int(
                entry.get(
                    "quantity",
                    0
                )
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "error": "Invalid quantity."
            }), 400

        if quantity <= 0:
            return jsonify({
                "error": "Quantity must be greater than zero."
            }), 400

        item = db.session.get(
            MenuItem,
            item_id
        )

        if not item:
            return jsonify({
                "error": "Menu item not found."
            }), 404

        if not item.available:
            return jsonify({
                "error": item.name
                + " is currently unavailable."
            }), 400

        total += (
            item.price * quantity
        )

        order_items.append(
            (
                item,
                quantity
            )
        )

    order = Order(
        user_id=user.id,
        status="Placed",
        total=total
    )

    db.session.add(order)

    db.session.flush()

    for item, quantity in order_items:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            name=item.name,
            quantity=quantity,
            price=item.price
        )

        db.session.add(
            order_item
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to place the order."
        }), 500

    return jsonify(
        serialise_order(order)
    ), 201


@app.get("/api/orders/my")
@jwt_required()
def my_orders():
    user = get_current_user()

    if not user:
        return jsonify({
            "error": "Invalid login session."
        }), 401

    orders = Order.query.filter_by(
        user_id=user.id
    ).order_by(
        Order.created_at.desc()
    ).all()

    return jsonify([
        serialise_order(order)
        for order in orders
    ])


@app.get("/api/admin/orders")
@jwt_required()
def admin_orders():
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()

    return jsonify([
        serialise_order(order)
        for order in orders
    ])


@app.patch("/api/admin/orders/<int:order_id>")
@jwt_required()
def update_order(order_id):
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    order = db.session.get(
        Order,
        order_id
    )

    if not order:
        return jsonify({
            "error": "Order not found."
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    status = data.get(
        "status"
    )

    statuses = [
        "Placed",
        "Confirmed",
        "Preparing",
        "Ready",
        "Picked Up"
    ]

    if status not in statuses:
        return jsonify({
            "error": "Invalid order status."
        }), 400

    order.status = status

    db.session.commit()

    return jsonify(
        serialise_order(order)
    )


@app.get("/api/admin/dashboard")
@jwt_required()
def admin_dashboard():
    if not admin_required():
        return jsonify({
            "error": "Admin access required."
        }), 403

    today = datetime.utcnow().date()

    start = datetime.combine(
        today,
        datetime.min.time()
    )

    orders = Order.query.filter(
        Order.created_at >= start
    ).all()

    statuses = [
        "Placed",
        "Confirmed",
        "Preparing",
        "Ready",
        "Picked Up"
    ]

    orders_by_status = {
        status: 0
        for status in statuses
    }

    popular_items = {}
    revenue = 0

    for order in orders:
        revenue += order.total

        if order.status not in orders_by_status:
            orders_by_status[
                order.status
            ] = 0

        orders_by_status[
            order.status
        ] += 1

        for item in order.items:
            popular_items[item.name] = (
                popular_items.get(
                    item.name,
                    0
                )
                + item.quantity
            )

    popular = [
        {
            "name": name,
            "quantity": quantity
        }
        for name, quantity
        in popular_items.items()
    ]

    popular.sort(
        key=lambda item: item["quantity"],
        reverse=True
    )

    return jsonify({
        "orders_by_status": orders_by_status,
        "popular_items": popular[:5],
        "revenue": round(
            revenue,
            2
        )
    })


def seed_menu():
    items = [
        {
            "name": "Masala Dosa",
            "description": "Crispy dosa filled with potato masala served with chutney and sambar",
            "category": "South Indian",
            "price": 120,
            "tags": "vegetarian,spicy",
            "image": "https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=900&q=85"
        },
        {
            "name": "Chicken Biryani",
            "description": "Fragrant basmati rice cooked with chicken and traditional spices",
            "category": "Rice",
            "price": 220,
            "tags": "non-vegetarian,spicy",
            "image": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=900&q=85"
        },
        {
            "name": "Paneer Tikka Bowl",
            "description": "Grilled paneer with rice, fresh vegetables and mint chutney",
            "category": "Main Course",
            "price": 180,
            "tags": "vegetarian,spicy,healthy",
            "image": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=85"
        },
        {
            "name": "Veggie Burger",
            "description": "Vegetable patty with lettuce, tomato and burger sauce",
            "category": "Burgers",
            "price": 160,
            "tags": "vegetarian,fried",
            "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=85"
        },
        {
            "name": "Grilled Chicken Salad",
            "description": "Grilled chicken with fresh greens, cucumber and lemon dressing",
            "category": "Salads",
            "price": 190,
            "tags": "non-vegetarian,healthy,light",
            "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85"
        },
        {
            "name": "Tomato Pasta",
            "description": "Penne pasta cooked in tomato sauce with herbs",
            "category": "Pasta",
            "price": 170,
            "tags": "vegetarian,light",
            "image": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=900&q=85"
        }
    ]

    for data in items:
        existing = MenuItem.query.filter_by(
            name=data["name"]
        ).first()

        if existing:
            existing.description = data[
                "description"
            ]

            existing.category = data[
                "category"
            ]

            existing.price = data[
                "price"
            ]

            existing.tags = data[
                "tags"
            ]

            existing.image = data[
                "image"
            ]

        else:
            item = MenuItem(
                name=data["name"],
                description=data[
                    "description"
                ],
                category=data[
                    "category"
                ],
                price=data[
                    "price"
                ],
                tags=data[
                    "tags"
                ],
                available=True,
                image=data[
                    "image"
                ]
            )

            db.session.add(
                item
            )

    db.session.commit()


with app.app_context():
    db.create_all()

    seed_menu()

    admin = User.query.filter_by(
        email="admin@bitebox.local"
    ).first()

    if not admin:
        admin = User(
            name="Admin",
            email="admin@bitebox.local",
            password=generate_password_hash(
                "admin123"
            ),
            role="admin"
        )

        db.session.add(
            admin
        )

        db.session.commit()


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )