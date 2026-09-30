import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-before-deploy")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(ROOT, "shop.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    def set_password(self, value): self.password_hash = generate_password_hash(value)
    def check_password(self, value): return check_password_hash(self.password_hash, value)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Integer, nullable=False) # amount in INR
    category = db.Column(db.String(80), default="General")
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="Placed")
    shipping_name = db.Column(db.String(100), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="orders")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", backref=db.backref("items", cascade="all, delete-orphan"))
    product = db.relationship("Product")

def user_now():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not user_now():
            flash("Please sign in first.", "error")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return inner

def admin_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not user_now() or user_now().role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return inner

@app.context_processor
def inject_user():
    return {"current_user": user_now(), "cart_count": sum(session.get("cart", {}).values())}

@app.route("/")
def index():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("shop.html", products=products)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<8: flash("Enter your name, email and password (8+ characters).","error")
        elif User.query.filter_by(email=email).first(): flash("Email already registered.","error")
        else:
            u=User(name=name,email=email); u.set_password(pw); db.session.add(u); db.session.commit()
            session["user_id"]=u.id; return redirect(url_for("index"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if u and u.check_password(request.form.get("password","")):
            session.clear(); session["user_id"]=u.id
            return redirect(request.args.get("next") or url_for("index"))
        flash("Email or password is incorrect.","error")
    return render_template("auth.html", mode="login")

@app.post("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.post("/cart/add/<int:product_id>")
def add_cart(product_id):
    product=Product.query.get_or_404(product_id)
    cart=session.get("cart",{}); key=str(product_id)
    if product.stock < 1: flash("This item is out of stock.","error")
    else:
        cart[key]=min(cart.get(key,0)+1, product.stock); session["cart"]=cart; flash("Added to your cart.","success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart")
def cart():
    cart_data=[]; total=0; cart_map=session.get("cart",{})
    for key, qty in cart_map.items():
        p=db.session.get(Product,int(key))
        if p and qty>0:
            line=p.price*qty; total+=line; cart_data.append({"product":p,"qty":qty,"line":line})
    return render_template("cart.html", cart_items=cart_data, total=total)

@app.post("/cart/update")
def update_cart():
    cart=session.get("cart",{})
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid=key[4:]; p=db.session.get(Product,int(pid))
            try: qty=max(0,min(int(value),p.stock if p else 0))
            except ValueError: qty=0
            if qty: cart[pid]=qty
            else: cart.pop(pid,None)
    session["cart"]=cart
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET","POST"])
@login_required
def checkout():
    cart_map=session.get("cart",{}); lines=[]; total=0
    for key,qty in cart_map.items():
        p=db.session.get(Product,int(key))
        if p and qty>0: lines.append((p,qty)); total+=p.price*qty
    if not lines: flash("Your cart is empty.","error"); return redirect(url_for("index"))
    if request.method=="POST":
        name=request.form.get("shipping_name","").strip(); address=request.form.get("shipping_address","").strip()
        if not name or not address: flash("Please complete shipping details.","error")
        elif any(p.stock<qty for p,qty in lines): flash("Stock changed. Please review your cart.","error")
        else:
            order=Order(user_id=user_now().id,total=total,shipping_name=name,shipping_address=address)
            db.session.add(order); db.session.flush()
            for p,qty in lines:
                p.stock-=qty; db.session.add(OrderItem(order_id=order.id,product_id=p.id,product_name=p.name,quantity=qty,unit_price=p.price))
            db.session.commit(); session["cart"]={}; flash(f"Order #{order.id} placed successfully (demo checkout).","success")
            return redirect(url_for("orders"))
    return render_template("checkout.html", lines=lines,total=total)

@app.route("/orders")
@login_required
def orders():
    rows=Order.query.filter_by(user_id=user_now().id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=rows)

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", products=Product.query.order_by(Product.id.desc()).all(), orders=Order.query.order_by(Order.created_at.desc()).all())

@app.post("/admin/products")
@admin_required
def create_product():
    try:
        price=int(request.form.get("price","0")); stock=int(request.form.get("stock","0"))
    except ValueError: price=-1; stock=-1
    name=request.form.get("name","").strip()
    if not name or price<0 or stock<0: flash("Provide a product name and valid non-negative price/stock.","error")
    else:
        db.session.add(Product(name=name,description=request.form.get("description","").strip(),price=price,stock=stock,
                               category=request.form.get("category","General").strip() or "General",
                               image_url=request.form.get("image_url","").strip()))
        db.session.commit(); flash("Product added.","success")
    return redirect(url_for("admin"))

@app.post("/admin/products/<int:pid>/delete")
@admin_required
def delete_product(pid):
    p=Product.query.get_or_404(pid)
    if OrderItem.query.filter_by(product_id=p.id).first(): flash("Cannot delete a product already included in an order.","error")
    else: db.session.delete(p); db.session.commit(); flash("Product deleted.","success")
    return redirect(url_for("admin"))

@app.post("/admin/orders/<int:oid>/status")
@admin_required
def update_order_status(oid):
    order=Order.query.get_or_404(oid); status=request.form.get("status")
    if status in ("Placed","Processing","Shipped","Delivered","Cancelled"):
        order.status=status; db.session.commit(); flash("Order status updated.","success")
    return redirect(url_for("admin"))

@app.get("/api/products")
def api_products():
    return jsonify([{"id":p.id,"name":p.name,"description":p.description,"price":p.price,"category":p.category,"stock":p.stock} for p in Product.query.all()])

@app.get("/api/orders")
@login_required
def api_orders():
    return jsonify([{"id":o.id,"total":o.total,"status":o.status,"created_at":o.created_at.isoformat()} for o in Order.query.filter_by(user_id=user_now().id).all()])

@app.get("/api/health")
def health(): return jsonify({"status":"ok","app":"ShopLite"})

def seed():
    if not User.query.filter_by(email="admin@shoplite.local").first():
        admin=User(name="Store Admin",email="admin@shoplite.local",role="admin"); admin.set_password("Admin123!")
        db.session.add(admin)
    if Product.query.count()==0:
        db.session.add_all([
            Product(name="Everyday Backpack",description="A durable everyday carry with a clean minimal profile.",price=2499,category="Accessories",stock=18,image_url="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=80"),
            Product(name="Studio Headphones",description="Comfortable over-ear headphones for focus and downtime.",price=3999,category="Electronics",stock=12,image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80"),
            Product(name="Ceramic Coffee Set",description="A simple ceramic set for your daily coffee ritual.",price=1299,category="Home",stock=24,image_url="https://images.unsplash.com/photo-1510707577719-ae7c14805e3a?auto=format&fit=crop&w=900&q=80"),
            Product(name="Desk Organizer",description="Keep your work surface tidy and essentials close.",price=899,category="Workspace",stock=30,image_url="https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=900&q=80")
        ])
    db.session.commit()

with app.app_context():
    db.create_all()
    seed()

if __name__=="__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG","false").lower()=="true")
