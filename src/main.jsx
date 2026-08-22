import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { ChefHat, CircleUserRound, Search, ShoppingCart, LogOut, Plus, Minus, X, LayoutDashboard, PackageCheck } from "lucide-react";
import "./styles.css";

const API_URL = "http://localhost:5000/api";

const api = axios.create({ baseURL: API_URL });
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("bitebox_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<ProtectedRoute><Customer /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute adminOnly><Admin /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}

function ProtectedRoute({ children, adminOnly = false }) {
  const user = getUser();
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

function getUser() {
  try { return JSON.parse(localStorage.getItem("bitebox_user")); } catch { return null; }
}

function saveSession(data) {
  localStorage.setItem("bitebox_token", data.token);
  localStorage.setItem("bitebox_user", JSON.stringify(data.user));
}

function Header() {
  const user = getUser();
  const navigate = useNavigate();
  const [cartCount, setCartCount] = useState(getCart().reduce((sum, item) => sum + item.quantity, 0));

  useEffect(() => {
    const refresh = () => setCartCount(getCart().reduce((sum, item) => sum + item.quantity, 0));
    window.addEventListener("cart-updated", refresh);
    return () => window.removeEventListener("cart-updated", refresh);
  }, []);

  function logout() {
    localStorage.removeItem("bitebox_token");
    localStorage.removeItem("bitebox_user");
    navigate("/login");
  }

  return (
    <header className="topbar">
      <Link to="/" className="brand"><span className="brand-mark"><ChefHat size={21} /></span> BiteBox</Link>
      <nav>
        <Link to="/">Menu</Link>
        <Link to="/orders">My Orders</Link>
        {user?.role === "admin" && <Link to="/admin">Admin</Link>}
      </nav>
      <div className="header-right">
        <span className="welcome"><CircleUserRound size={18} /> {user?.name}</span>
        <button className="cart-link" onClick={() => window.dispatchEvent(new Event("open-cart"))} aria-label="Open cart"><ShoppingCart size={19} /> <span>{cartCount}</span></button>
        <button className="icon-button" onClick={logout} title="Logout"><LogOut size={18} /></button>
      </div>
    </header>
  );
}

function Customer() {
  const [menu, setMenu] = useState([]);
  const [results, setResults] = useState(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [cartOpen, setCartOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadMenu();
    const openCart = () => setCartOpen(true);
    window.addEventListener("open-cart", openCart);
    return () => window.removeEventListener("open-cart", openCart);
  }, [category]);

  async function loadMenu() {
    const { data } = await api.get("/menu", { params: { category } });
    setMenu(data);
    setResults(null);
  }

  async function runSearch(event) {
    event.preventDefault();
    if (!query.trim()) return loadMenu();
    setLoading(true);
    try {
      const { data } = await api.get("/menu/search", { params: { q: query } });
      setResults(data.results);
    } finally { setLoading(false); }
  }

  const categories = ["All", ...new Set(menu.map(item => item.category))];
  const shownItems = results ?? menu;

  return (
    <div className="app-shell">
      <Header />
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">GOOD FOOD, WITHOUT THE GUESSWORK</p>
            <h1>Tell us what you're craving.</h1>
            <p className="hero-copy">Try a normal sentence. We'll look at ingredients, categories, tags, price and even words such as “without” or “not”.</p>
            <form className="smart-search" onSubmit={runSearch}>
              <Search size={21} />
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. something spicy and vegetarian under 200" />
              <button>{loading ? "Searching..." : "Find food"}</button>
            </form>
            <div className="search-hints">
              <button onClick={() => setQuery("something spicy and vegetarian under 200")}>Spicy + vegetarian</button>
              <button onClick={() => setQuery("a light lunch that is not fried")}>Light, not fried</button>
              <button onClick={() => setQuery("healthy food under 180")}>Healthy under ₹180</button>
            </div>
          </div>
          <img className="hero-image" src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1100&q=85" alt="A table filled with restaurant food" />
        </section>

        <div className="section-head">
          <div><p className="eyebrow">MENU</p><h2>{results ? "Best matches" : "Today's menu"}</h2></div>
          <button className="cart-button" onClick={() => setCartOpen(true)}><ShoppingCart size={18} /> View cart ({getCart().reduce((sum, item) => sum + item.quantity, 0)})</button>
        </div>

        <div className="categories">
          {categories.map(name => <button key={name} className={category === name ? "active" : ""} onClick={() => { setCategory(name); setQuery(""); }}>{name}</button>)}
        </div>

        {results && <p className="result-note">Showing dishes ranked by relevance to <strong>“{query}”</strong>.</p>}

        <div className="menu-grid">
          {shownItems.map(item => <MenuCard key={item.id} item={item} />)}
        </div>
        {!shownItems.length && <div className="empty-state"><Search size={32} /><h3>Nothing quite matched</h3><p>Try a broader description, or browse the menu by category.</p></div>}
      </main>
      {cartOpen && <CartDrawer close={() => setCartOpen(false)} />}
    </div>
  );
}

function MenuCard({ item }) {
  const [cart, setCart] = useState(getCart());
  const quantity = cart.find(row => row.id === item.id)?.quantity || 0;

  function add() {
    const existing = cart.find(row => row.id === item.id);
    const next = existing
      ? cart.map(row => row.id === item.id ? { ...row, quantity: row.quantity + 1 } : row)
      : [...cart, { ...item, quantity: 1 }];
    setCart(next); saveCart(next);
  }

  return (
    <article className="food-card">
      <div className="food-image-wrap">
        <img src={item.image} alt={item.name} />
        {item.tags?.includes("vegetarian") && <span className="veg-dot">VEG</span>}
      </div>
      <div className="food-content">
        <div className="food-title"><h3>{item.name}</h3><span>₹{item.price}</span></div>
        <p>{item.description}</p>
        <div className="tags">{item.tags?.map(tag => <span key={tag}>{tag}</span>)}</div>
        <button className="add-button" onClick={add}>{quantity ? `${quantity} in cart · Add another` : "Add to cart"} <Plus size={17} /></button>
      </div>
    </article>
  );
}

function CartDrawer({ close }) {
  const [cart, setCart] = useState(getCart());
  const navigate = useNavigate();
  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

  function update(id, change) {
    const next = cart.map(item => item.id === id ? { ...item, quantity: item.quantity + change } : item).filter(item => item.quantity > 0);
    setCart(next); saveCart(next);
  }

  async function placeOrder() {
    try {
      await api.post("/orders", { items: cart.map(item => ({ menu_item_id: item.id, quantity: item.quantity })) });
      saveCart([]); close(); navigate("/orders");
    } catch (error) { alert(error.response?.data?.error || "Could not place the order."); }
  }

  return (
    <div className="drawer-backdrop" onClick={close}>
      <aside className="cart-drawer" onClick={e => e.stopPropagation()}>
        <div className="drawer-head"><div><p className="eyebrow">YOUR ORDER</p><h2>Cart</h2></div><button onClick={close}><X /></button></div>
        {!cart.length ? <div className="empty-state"><ShoppingCart size={32} /><h3>Your cart is empty</h3></div> : <>
          <div className="cart-items">{cart.map(item => <div className="cart-row" key={item.id}><img src={item.image} alt="" /><div><strong>{item.name}</strong><small>₹{item.price} each</small><div className="qty"><button onClick={() => update(item.id, -1)}><Minus size={14} /></button><span>{item.quantity}</span><button onClick={() => update(item.id, 1)}><Plus size={14} /></button></div></div><b>₹{item.price * item.quantity}</b></div>)}</div>
          <div className="cart-total"><span>Total</span><strong>₹{total}</strong></div>
          <button className="checkout" onClick={placeOrder}>Place order</button>
        </>}
      </aside>
    </div>
  );
}

function Orders() {
  const [orders, setOrders] = useState([]);
  useEffect(() => { api.get("/orders/my").then(res => setOrders(res.data)); }, []);
  return <div className="app-shell"><Header /><main className="narrow"><p className="eyebrow">ORDER HISTORY</p><h1>Your orders</h1><div className="orders-list">{orders.map(order => <OrderCard key={order.id} order={order} />)}{!orders.length && <div className="empty-state"><PackageCheck size={32} /><h3>No orders yet</h3><Link to="/">Browse the menu</Link></div>}</div></main></div>;
}

function OrderCard({ order }) {
  const steps = ["Placed", "Confirmed", "Preparing", "Ready", "Picked Up"];
  const current = steps.indexOf(order.status);
  return <article className="order-card"><div className="order-top"><div><strong>Order #{order.id}</strong><p>{new Date(order.created_at).toLocaleString()}</p></div><span className="status-pill">{order.status}</span></div><div className="progress">{steps.map((step, i) => <div className={i <= current ? "done" : ""} key={step}><span></span><small>{step}</small></div>)}</div><div className="order-items">{order.items.map(item => <div key={item.name}><span>{item.quantity} × {item.name}</span><b>₹{item.price * item.quantity}</b></div>)}</div><div className="order-total"><span>Total</span><strong>₹{order.total}</strong></div></article>;
}

function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function submit(e) { e.preventDefault(); setError(""); try { const { data } = await api.post("/auth/login", form); saveSession(data); navigate(data.user.role === "admin" ? "/admin" : "/"); } catch (err) { setError(err.response?.data?.error || "Login failed."); } }
  return <AuthLayout title="Welcome back" subtitle="Sign in and pick up where you left off."><form className="auth-form" onSubmit={submit}><label>Email<input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label><label>Password<input type="password" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label>{error && <p className="error">{error}</p>}<button className="primary-button">Sign in</button><p className="auth-switch">New to BiteBox? <Link to="/signup">Create an account</Link></p></form></AuthLayout>;
}

function Signup() {
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function submit(e) { e.preventDefault(); setError(""); try { const { data } = await api.post("/auth/signup", form); saveSession(data); navigate("/"); } catch (err) { setError(err.response?.data?.error || "Signup failed."); } }
  return <AuthLayout title="Create your account" subtitle="A few details and you're ready to order."><form className="auth-form" onSubmit={submit}><label>Name<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label><label>Email<input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label><label>Password<input type="password" minLength="6" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label>{error && <p className="error">{error}</p>}<button className="primary-button">Create account</button><p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p></form></AuthLayout>;
}

function AuthLayout({ title, subtitle, children }) { return <div className="auth-page"><div className="auth-visual"><img src="https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1200&q=85" alt="Restaurant table" /><div><Link to="/" className="brand light"><span className="brand-mark"><ChefHat size={21} /></span> BiteBox</Link><h1>Food that feels like a good idea.</h1></div></div><section className="auth-panel"><div className="auth-inner"><Link to="/" className="brand"><span className="brand-mark"><ChefHat size={21} /></span> BiteBox</Link><p className="eyebrow">HELLO THERE</p><h2>{title}</h2><p>{subtitle}</p>{children}</div></section></div>; }

function Admin() {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [category, setCategory] = useState("South Indian");
    const [price, setPrice] = useState("");
    const [tags, setTags] = useState("");
    const [available, setAvailable] = useState(true);
    const [imageFile, setImageFile] = useState(null);

    const [dashboard, setDashboard] = useState(null);
    const [orders, setOrders] = useState([]);
    const [menu, setMenu] = useState([]);
    const [tab, setTab] = useState("dashboard");

    useEffect(() => {
        refresh();
    }, []);

    async function refresh() {
        const [d, o, m] = await Promise.all([
            api.get("/admin/dashboard"),
            api.get("/admin/orders"),
            api.get("/admin/menu")
        ]);

        setDashboard(d.data);
        setOrders(o.data);
        setMenu(m.data);
    }

    async function changeStatus(id, status) {
        await api.patch(
            `/admin/orders/${id}`,
            { status }
        );

        await refresh();
    }

    async function addMenuItem(e) {
        e.preventDefault();

        try {
            const formData = new FormData();

            formData.append("name", name);
            formData.append("description", description);
            formData.append("category", category);
            formData.append("price", price);
            formData.append("tags", tags);
            formData.append("available", available);

            if (imageFile) {
                formData.append("image", imageFile);
            }

            await api.post(
                "/admin/menu",
                formData
            );

            setName("");
            setDescription("");
            setCategory("South Indian");
            setPrice("");
            setTags("");
            setAvailable(true);
            setImageFile(null);

            await refresh();

            alert("Food item added successfully");

        } catch (error) {
            console.error(error);

            alert(
                error.response?.data?.error ||
                "Unable to add food item"
            );
        }
    }

    async function deleteMenuItem(id) {
        const confirmDelete = window.confirm(
            "Are you sure you want to remove this food item?"
        );

        if (!confirmDelete) {
            return;
        }

        try {
            await api.delete(
                `/admin/menu/${id}`
            );

            await refresh();

        } catch (error) {
            console.error(error);

            alert(
                error.response?.data?.error ||
                "Unable to delete food item"
            );
        }
    }

    async function changeAvailability(item) {
        try {
            await api.patch(
                `/admin/menu/${item.id}/availability`,
                {
                    available: !item.available
                }
            );

            await refresh();

        } catch (error) {
            console.error(error);

            alert(
                error.response?.data?.error ||
                "Unable to change availability"
            );
        }
    }

    return (
    <div className="app-shell">

        <Header />

        <main>

            <div className="admin-title">

                <div>
                    <p className="eyebrow">CONTROL ROOM</p>
                    <h1>Admin dashboard</h1>
                </div>

                <div className="admin-tabs">

                    <button
                        className={tab === "dashboard" ? "active" : ""}
                        onClick={() => setTab("dashboard")}
                    >
                        Overview
                    </button>

                    <button
                        className={tab === "orders" ? "active" : ""}
                        onClick={() => setTab("orders")}
                    >
                        Orders
                    </button>

                    <button
                        className={tab === "menu" ? "active" : ""}
                        onClick={() => setTab("menu")}
                    >
                        Menu
                    </button>

                </div>

            </div>


            {tab === "dashboard" && dashboard && (

                <>

                    <div className="stat-grid">

                        <Stat
                            title="Today's revenue"
                            value={`₹${dashboard.revenue}`}
                        />

                        <Stat
                            title="Orders today"
                            value={Object.values(
                                dashboard.orders_by_status
                            ).reduce((a, b) => a + b, 0)}
                        />

                        <Stat
                            title="Preparing"
                            value={
                                dashboard.orders_by_status.Preparing || 0
                            }
                        />

                        <Stat
                            title="Ready"
                            value={
                                dashboard.orders_by_status.Ready || 0
                            }
                        />

                    </div>


                    <div className="admin-columns">

                        <section className="admin-panel">

                            <h2>Orders by status</h2>

                            {Object.entries(
                                dashboard.orders_by_status
                            ).map(([name, value]) => (

                                <div
                                    className="bar-row"
                                    key={name}
                                >

                                    <span>{name}</span>

                                    <div>
                                        <i
                                            style={{
                                                width: `${Math.min(
                                                    value * 18,
                                                    100
                                                )}%`
                                            }}
                                        />
                                    </div>

                                    <b>{value}</b>

                                </div>

                            ))}

                        </section>


                        <section className="admin-panel">

                            <h2>Popular items</h2>

                            {dashboard.popular_items.map(
                                (item, index) => (

                                    <div
                                        className="popular-row"
                                        key={item.name}
                                    >

                                        <span>{index + 1}</span>

                                        <strong>
                                            {item.name}
                                        </strong>

                                        <b>
                                            {item.quantity} sold
                                        </b>

                                    </div>

                                )
                            )}

                        </section>

                    </div>

                </>

            )}


            {tab === "orders" && (

                <section className="admin-panel">

                    <h2>Incoming orders</h2>

                    <div className="admin-order-list">

                        {orders.map(order => (

                            <div
                                className="admin-order"
                                key={order.id}
                            >

                                <div>

                                    <strong>
                                        #{order.id}
                                    </strong>

                                    <span>
                                        {order.items
                                            .map(
                                                item =>
                                                    `${item.quantity} × ${item.name}`
                                            )
                                            .join(", ")}
                                    </span>

                                </div>

                                <b>
                                    ₹{order.total}
                                </b>

                                <select
                                    value={order.status}
                                    onChange={(e) =>
                                        changeStatus(
                                            order.id,
                                            e.target.value
                                        )
                                    }
                                >

                                    {[
                                        "Placed",
                                        "Confirmed",
                                        "Preparing",
                                        "Ready",
                                        "Picked Up"
                                    ].map(status => (

                                        <option
                                            key={status}
                                            value={status}
                                        >
                                            {status}
                                        </option>

                                    ))}

                                </select>

                            </div>

                        ))}

                    </div>

                </section>

            )}


            {tab === "menu" && (

                <div>

                    <section className="admin-panel">

                        <div className="panel-heading">

                            <h2>Add Food Item</h2>

                        </div>


                        <form
                            onSubmit={addMenuItem}
                            className="admin-food-form"
                        >

                            <input
                                type="text"
                                placeholder="Food name"
                                value={name}
                                onChange={(e) =>
                                    setName(e.target.value)
                                }
                                required
                            />


                            <textarea
                                placeholder="Description"
                                value={description}
                                onChange={(e) =>
                                    setDescription(e.target.value)
                                }
                                required
                            />


                            <select
                                value={category}
                                onChange={(e) =>
                                    setCategory(e.target.value)
                                }
                            >

                                <option>
                                    South Indian
                                </option>

                                <option>
                                    North Indian
                                </option>

                                <option>
                                    Rice
                                </option>

                                <option>
                                    Burgers
                                </option>

                                <option>
                                    Pasta
                                </option>

                                <option>
                                    Salads
                                </option>

                                <option>
                                    Main Course
                                </option>

                                <option>
                                    Desserts
                                </option>

                                <option>
                                    Drinks
                                </option>

                            </select>


                            <input
                                type="number"
                                placeholder="Price"
                                value={price}
                                onChange={(e) =>
                                    setPrice(e.target.value)
                                }
                                required
                            />


                            <input
                                type="text"
                                placeholder="Tags: vegetarian, spicy"
                                value={tags}
                                onChange={(e) =>
                                    setTags(e.target.value)
                                }
                            />


                            <label>
                                Food Image
                            </label>


                            <input
                                type="file"
                                accept="image/png,image/jpeg,image/webp"
                                onChange={(e) =>
                                    setImageFile(
                                        e.target.files[0]
                                    )
                                }
                            />


                            <label>

                                <input
                                    type="checkbox"
                                    checked={available}
                                    onChange={(e) =>
                                        setAvailable(
                                            e.target.checked
                                        )
                                    }
                                />

                                Available

                            </label>


                            <button type="submit">
                                Add Food
                            </button>

                        </form>

                    </section>


                    <section className="admin-panel">

                        <div className="panel-heading">

                            <h2>Manage Menu</h2>

                            <span>
                                {menu.length} items
                            </span>

                        </div>


                        <div className="admin-menu-list">

                            {menu.map(item => (

                                <div
                                    className="admin-menu-row"
                                    key={item.id}
                                >

                                    <img
                                        src={
                                            item.image?.startsWith("http")
                                                ? item.image
                                                : `http://localhost:5000${item.image}`
                                        }
                                        alt={item.name}
                                    />


                                    <div className="admin-menu-info">

                                        <strong>
                                            {item.name}
                                        </strong>

                                        <small>
                                            {item.category}
                                            {" · "}
                                            ₹{item.price}
                                        </small>

                                        <small>
                                            {item.description}
                                        </small>

                                    </div>


                                    <div className="tags">

                                        {item.tags?.map(tag => (

                                            <em key={tag}>
                                                {tag}
                                            </em>

                                        ))}

                                    </div>


                                    <span
                                        className={
                                            item.available
                                                ? "available"
                                                : "unavailable"
                                        }
                                    >

                                        {item.available
                                            ? "Available"
                                            : "Unavailable"}

                                    </span>


                                    <button
                                        onClick={() =>
                                            changeAvailability(item)
                                        }
                                    >

                                        {item.available
                                            ? "Mark Unavailable"
                                            : "Mark Available"}

                                    </button>


                                    <button
                                        onClick={() =>
                                            deleteMenuItem(item.id)
                                        }
                                    >
                                        Remove
                                    </button>

                                </div>

                            ))}

                        </div>

                    </section>

                </div>

            )}

        </main>

    </div>
);
}
function Stat({ title, value }) {
    return (
        <div className="stat-card">
            <span>{title}</span>
            <strong>{value}</strong>
        </div>
    );
}

function getCart() {
    try {
        return JSON.parse(
            localStorage.getItem("bitebox_cart")
        ) || [];
    } catch {
        return [];
    }
}

function saveCart(cart) {
    localStorage.setItem(
        "bitebox_cart",
        JSON.stringify(cart)
    );

    window.dispatchEvent(
        new Event("cart-updated")
    );
}

createRoot(
    document.getElementById("root")
).render(<App />);