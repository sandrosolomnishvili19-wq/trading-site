from functools import wraps
import os
import psycopg2
import psycopg2.extras
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Supabase PostgreSQL ბაზის მისამართი
# როდესაც Render-ზე ატვირთავ, შეგიძლია Environment Variables-ში ჩაწერო DATABASE_URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:Sandrika789@db.rnktcgfknokfdktfxjkb.supabase.co:5432/postgres"
)


# ბაზასთან კავშირის დამხმარე ფუნქცია
def get_db_connection():
    conn = psycopg2.connect(postgresql://postgres:Sandrika789@db.rnktcgfknokfdktfxjkb.supabase.co:5432/postgres, sslmode="require")
    conn.row_factory = psycopg2.extras.DictCursor
    return conn


# ბაზის ინიციალიზაცია (PostgreSQL სინტაქსით)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_paid INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            date TEXT,
            pair TEXT,
            direction TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            emotion TEXT,
            screenshot TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # ვამოწმებთ სვეტებს trades ცხრილში (თუ ძველი სტრუქტურაა)
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades'
    """)
    columns = [row["column_name"] for row in cursor.fetchall()]

    if "emotion" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN emotion TEXT")
    
    if "screenshot" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN screenshot TEXT")

    conn.commit()
    cursor.close()
    conn.close()


init_db()


# --- დეკორატორები ---
def paid_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("username") == "sandrika":
            return f(*args, **kwargs)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_paid FROM users WHERE id = %s", (session["user_id"],)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or user["is_paid"] == 0:
            return redirect(url_for("pending_approval"))

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("username") != "sandrika":
            flash("ამ გვერდზე წვდომა გაქვს მხოლოდ შენ!", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


# --- მარშრუტები ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = %s", (username,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_paid"] = user["is_paid"]

            if username == "sandrika" or user["is_paid"] == 1:
                return redirect(url_for("index"))
            else:
                return redirect(url_for("pending_approval"))
        else:
            flash("არასწორი მომხმარებლის სახელი ან პაროლი", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, is_paid) VALUES (%s, %s, 0)",
                (username, hashed_password),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("რეგისტრაცია წარმატებულია!", "success")
            return redirect(url_for("login"))
        except Exception:
            flash("ეს იუზერნეიმი დაკავებულია.", "error")

    return render_template("register.html")


@app.route("/pending")
def pending_approval():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT is_paid FROM users WHERE id = %s", (session["user_id"],)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if session.get("username") == "sandrika" or (user and user["is_paid"] == 1):
        return redirect(url_for("index"))

    return render_template("pending.html", discord_tag="cs2sacc")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@paid_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    initial_balance = 50000.0
    current_balance = initial_balance
    total_pnl = 0.0
    wins = 0
    dataSource_trades = list(trades)
    total_trades = len(dataSource_trades)

    gross_profit = 0.0
    gross_loss = 0.0

    max_loss_limit = 1000.0
    current_max_loss = max_loss_limit

    chart_data = []
    calendar_data = {}  

    for t in reversed(dataSource_trades):
        pnl = t["pnl"]
        total_pnl += pnl
        current_balance += pnl

        if pnl > 0:
            wins += 1
            gross_profit += pnl
        elif pnl < 0:
            gross_loss += abs(pnl)
            current_max_loss -= abs(pnl)

        chart_data.append({"time": t["date"], "value": current_balance})

    for t in dataSource_trades:
        trade_date = str(t["date"])  
        pnl = t["pnl"]
        if trade_date not in calendar_data:
            calendar_data[trade_date] = 0.0
        calendar_data[trade_date] += pnl

    if current_max_loss < 0:
        current_max_loss = 0.0

    win_rate = (
        round((wins / total_trades * 100), 1) if total_trades > 0 else 0
    )

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = round(gross_profit, 2)
    else:
        profit_factor = 0.0

    target_balance = 53000.0
    progress_pct = (
        round(
            (
                (current_balance - initial_balance)
                / (target_balance - initial_balance)
            )
            * 100,
            1,
        )
        if target_balance > initial_balance
        else 0
    )
    if progress_pct < 0:
        progress_pct = 0
    if progress_pct > 100:
        progress_pct = 100

    return render_template(
        "index.html",
        initial_balance=initial_balance,
        current_balance=current_balance,
        total_pnl=total_pnl,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_loss_limit=current_max_loss,
        target_balance=target_balance,
        progress_pct=progress_pct,
        chart_data=chart_data,
        calendar_data=calendar_data,  
        daily_pnl=calendar_data,  
        trades=trades,
    )


@app.route("/trades")
@paid_required
def trades_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("trades.html", trades=trades)


@app.route("/trade/<int:id>")
@paid_required
def trade_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE id = %s AND user_id = %s",
        (id, session["user_id"]),
    )
    trade = cursor.fetchone()
    cursor.close()
    conn.close()

    if not trade:
        flash("ტრეიდი ვერ მოიძებნა.", "error")
        return redirect(url_for("trades_list"))

    return render_template("trade_detail.html", trade=trade)


@app.route("/add_trade", methods=["GET", "POST"])
@paid_required
def add_trade():
    if request.method == "POST":
        date = request.form.get("date")
        pair = request.form.get("pair")

        raw_direction = str(request.form.get("direction", "")).strip().lower()
        if "short" in raw_direction or "შორთ" in raw_direction or raw_direction == "s":
            direction = "SHORT"
        else:
            direction = "LONG"

        entry_price = float(request.form.get("entry_price", 0) or 0)
        exit_price = float(request.form.get("exit_price", 0) or 0)
        pnl = float(request.form.get("pnl", 0) or 0)
        emotion = request.form.get("emotion", "ნეიტრალური")
        screenshot_base64 = request.form.get("screenshot")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO trades (user_id, date, pair, direction, entry_price, exit_price, pnl, emotion, screenshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                date,
                pair,
                direction,
                entry_price,
                exit_price,
                pnl,
                emotion,
                screenshot_base64,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("ტრეიდი და სურათი წარმატებით დაემატა!", "success")
        return redirect(url_for("index"))

    return render_template("add_trade.html")


@app.route("/delete_trade/<int:id>", methods=["GET", "POST"])
@paid_required
def delete_trade(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE id = %s AND user_id = %s",
        (id, session["user_id"]),
    )
    trade = cursor.fetchone()
    if trade:
        cursor.execute("DELETE FROM trades WHERE id = %s", (id,))
        conn.commit()
        flash("ტრეიდი წაიშალა!", "success")
    cursor.close()
    conn.close()
    return redirect(url_for("trades_list"))


@app.route("/analytics")
@paid_required
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    long_wins = 0
    long_losses = 0
    long_pnl = 0.0

    short_wins = 0
    short_losses = 0
    short_pnl = 0.0

    emotion_stats = {}

    for t in trades:
        pnl = t["pnl"]
        raw_dir = str(t["direction"]).strip().lower() if t["direction"] else ""
        emotion = (
            t["emotion"] if "emotion" in t.keys() and t["emotion"] else "ზოგადი"
        )

        if emotion not in emotion_stats:
            emotion_stats[emotion] = {"count": 0, "pnl": 0.0}
        emotion_stats[emotion]["count"] += 1
        emotion_stats[emotion]["pnl"] += pnl

        is_short = (
            "short" in raw_dir or "შორთ" in raw_dir or raw_dir.startswith("s")
        )
        is_long = "long" in raw_dir or "ლონგ" in raw_dir or raw_dir.startswith("l")

        if is_short:
            if pnl >= 0:
                short_wins += 1
            else:
                short_losses += 1
            short_pnl += pnl
        elif is_long or not raw_dir:
            if pnl >= 0:
                long_wins += 1
            else:
                long_losses += 1
            long_pnl += pnl

    long_count = long_wins + long_losses
    short_count = short_wins + short_losses

    long_stats = {
        "count": long_count,
        "pnl": long_pnl,
        "win_rate": (
            round((long_wins / long_count * 100), 1) if long_count > 0 else 0
        ),
    }

    short_stats = {
        "count": short_count,
        "pnl": short_pnl,
        "win_rate": (
            round((short_wins / short_count * 100), 1) if short_count > 0 else 0
        ),
    }

    return render_template(
        "analytics.html",
        long_stats=long_stats,
        short_stats=short_stats,
        emotion_stats=emotion_stats,
    )


@app.route("/update_settings", methods=["POST"])
@paid_required
def update_settings():
    flash("პარამეტრები განახლდა!", "success")
    return redirect(url_for("index"))


@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, is_paid FROM users WHERE username != 'sandrika'"
    )
    all_users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("admin_users.html", users=all_users)


@app.route("/admin/toggle/<int:user_id>", methods=["POST"])
@admin_required
def toggle_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT is_paid FROM users WHERE id = %s", (user_id,)
    )
    current = cursor.fetchone()
    if current:
        new_status = 0 if current["is_paid"] == 1 else 1
        cursor.execute(
            "UPDATE users SET is_paid = %s WHERE id = %s", (new_status, user_id)
        )
        conn.commit()
    cursor.close()
    conn.close()
    flash("სტატუსი განახლდა!", "success")
    return redirect(url_for("admin_users"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)