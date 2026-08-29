from functools import wraps
import os
import datetime
import secrets
import psycopg2
import psycopg2.extras
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_mail import Mail, Message
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Flask-Mail კონფიგურაცია (ჩაანაცვლე შენი მონაცემებით)
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "your_email@gmail.com"  # შენი მეილი
app.config["MAIL_PASSWORD"] = "your_app_password"     # აპლიკაციის პაროლი
app.config["MAIL_DEFAULT_SENDER"] = "your_email@gmail.com"

mail = Mail(app)

# Supabase PostgreSQL ბაზის მისამართი
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres.rnktcgfknokfdktfxjkb:Sandrika789%24@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"
)


# ბაზასთან კავშირის დამხმარე ფუნქცია
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn


# ბაზის ინიციალიზაცია (PostgreSQL სინტაქსით)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            is_paid INTEGER DEFAULT 0,
            initial_balance REAL DEFAULT 50000.0,
            max_loss_limit REAL DEFAULT 1000.0,
            target_balance REAL DEFAULT 53000.0,
            reset_token TEXT,
            reset_token_expiration TIMESTAMP
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

    # ვამოწმებთ სვეტებს users ცხრილში
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users'
    """)
    user_columns = [row[0] for row in cursor.fetchall()]

    if "email" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "initial_balance" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN initial_balance REAL DEFAULT 50000.0")
    if "max_loss_limit" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN max_loss_limit REAL DEFAULT 1000.0")
    if "target_balance" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN target_balance REAL DEFAULT 53000.0")
    if "reset_token" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT")
    if "reset_token_expiration" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expiration TIMESTAMP")

    # ვამოწმებთ სვეტებს trades ცხრილში
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades'
    """)
    columns = [row[0] for row in cursor.fetchall()]

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
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
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
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
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
        email = request.form.get("email")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password, is_paid) VALUES (%s, %s, %s, 0)",
                (username, email, hashed_password),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("რეგისტრაცია წარმატებულია!", "success")
            return redirect(url_for("login"))
        except Exception:
            flash("ეს იუზერნეიმი ან მეილი დაკავებულია.", "error")

    return render_template("register.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    session.clear()
    if request.method == "POST":
        email = request.form.get("email")
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            token = secrets.token_urlsafe(32)
            expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            
            cursor.execute(
                "UPDATE users SET reset_token = %s, reset_token_expiration = %s WHERE id = %s",
                (token, expiration, user["id"])
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            reset_url = url_for("reset_password", token=token, _external=True)
            msg = Message("პაროლის აღდგენა - YourStats", recipients=[email])
            msg.body = f"""პაროლის აღსადგენად მიჰყევით ამ ბმულს:
{reset_url}

თუ ეს მოთხოვნა თქვენ არ გეკუთვნით, უბრალოდ უგულებელყავით ეს წერილი. ბმული ძალაშია 1 საათის განმავლობაში."""
            
            try:
                mail.send(msg)
                flash("პაროლის აღდგენის ინსტრუქცია გამოგზავნილია თქვენს მეილზე.", "success")
            except Exception as e:
                print(e)
                flash("მეილის გაგზავნა ვერ მოხერხდა. სცადეთ მოგვიანებით.", "error")
        else:
            cursor.close()
            conn.close()
            flash("მომხმარებელი ამ მეილით ვერ მოიძებნა.", "error")
            
        return redirect(url_for("forgot_password"))
        
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_
