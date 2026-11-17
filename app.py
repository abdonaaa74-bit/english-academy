
import os
import sqlite3
from functools import wraps
from flask import Flask, request, redirect, session, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DB = "academy.db"

def connect():
    return sqlite3.connect(DB)

def setup():
    con = connect()
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE, password TEXT,
        points INTEGER DEFAULT 0, admin INTEGER DEFAULT 0
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS progress (
        user_id INTEGER, stage INTEGER,
        UNIQUE(user_id, stage)
    )""")
    admin = con.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@english.com",)
    ).fetchone()
    if not admin:
        con.execute(
            "INSERT INTO users(name,email,password,admin) VALUES(?,?,?,1)",
            ("Admin", "admin@english.com",
             generate_password_hash("Admin12345"))
        )
    con.commit()
    con.close()

setup()

STYLE = """
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#f1f5f9;margin:0;color:#172554}
header{background:#123b70;color:white;padding:18px;text-align:center}
main{max-width:650px;margin:25px auto;padding:20px}
.card{background:white;padding:22px;border-radius:15px;margin:15px 0;box-shadow:0 2px 8px #ddd}
input,button{width:100%;padding:13px;margin:8px 0;box-sizing:border-box;border-radius:8px;border:1px solid #ccc}
button{background:#1769aa;color:white;border:0;font-weight:bold}
a{color:#1769aa}
</style>
"""

def page(content):
    return render_template_string(
        STYLE + '<header><h2>أكاديمية الإنجليزية</h2></header><main>' +
        content + '</main>'
    )

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return page("""
    <div class="card">
    <h2>تعلم الإنجليزية من الصفر</h2>
    <p>تعلم، اختبر نفسك، واجمع النقاط!</p>
    <a href="/register">إنشاء حساب</a><br><br>
    <a href="/login">تسجيل الدخول</a>
    </div>
    """)

@app.route("/register", methods=["GET","POST"])
def register():
    msg = ""
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        try:
            con = connect()
            con.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name,email,generate_password_hash(password))
            )
            con.commit()
            con.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            msg = "البريد الإلكتروني مستخدم من قبل"
    return page("""
    <div class="card"><h2>إنشاء حساب جديد</h2>
    <p style="color:red">""" + msg + """</p>
    <form method="post">
    <input name="name" placeholder="اسمك" required>
    <input name="email" type="email" placeholder="البريد الإلكتروني" required>
    <input name="password" type="password" placeholder="كلمة المرور" required>
    <button>إنشاء الحساب</button></form>
    <a href="/login">لديك حساب؟ سجل الدخول</a></div>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        con = connect()
        user = con.execute(
            "SELECT id,password FROM users WHERE email=?", (email,)
        ).fetchone()
        con.close()
        if user and check_password_hash(user[1], password):
            session["user"] = user[0]
            return redirect("/dashboard")
        msg = "البريد الإلكتروني أو كلمة المرور غير صحيحة"
    return page("""
    <div class="card"><h2>تسجيل الدخول</h2>
    <p style="color:red">""" + msg + """</p>
    <form method="post">
    <input name="email" type="email" placeholder="البريد الإلكتروني" required>
    <input name="password" type="password" placeholder="كلمة المرور" required>
    <button>دخول</button></form>
    <a href="/register">إنشاء حساب جديد</a></div>
    """)

@app.route("/dashboard")
@login_required
def dashboard():
    con = connect()
    user = con.execute(
        "SELECT name,points FROM users WHERE id=?",
        (session["user"],)
    ).fetchone()
    done = [x[0] for x in con.execute(
        "SELECT stage FROM progress WHERE user_id=?",
        (session["user"],)
    ).fetchall()]
    con.close()
    stages = ""
    for i in range(1,6):
        status = "تم اجتيازها" if i in done else "ابدأ الدرس"
        stages += f'<div class="card"><h3>المرحلة {i}</h3><a href="/stage/{i}">{status}</a></div>'
    return page(
        f'<div class="card"><h2>أهلاً {user[0]}</h2>'
        f'<h3>نقاطك: {user[1]}</h3></div>' +
        stages + '<a href="/logout">تسجيل الخروج</a>'
    )

QUESTIONS = [
    ("ما معنى Apple؟", ["تفاحة","كتاب","قلم"], 0),
    ("ما معنى Book؟", ["باب","كتاب","ماء"], 1),
    ("ما معنى Cat؟", ["كلب","قطة","بيت"], 1),
    ("ما معنى Water؟", ["ماء","طعام","سيارة"], 0),
    ("ما معنى Thank you؟", ["صباح الخير","شكراً","وداعاً"], 1)
]

@app.route("/stage/<int:number>", methods=["GET","POST"])
@login_required
def stage(number):
    if number < 1 or number > 5:
        return redirect("/dashboard")
    q = QUESTIONS[number-1]
    msg = ""
    if request.method == "POST":
        answer = request.form.get("answer", "")
        if answer == str(q[2]):
            con = connect()
            con.execute(
                "INSERT OR IGNORE INTO progress(user_id,stage) VALUES(?,?)",
                (session["user"], number)
            )
            if con.total_changes:
                con.execute(
                    "UPDATE users SET points=points+10 WHERE id=?",
                    (session["user"],)
                )
            con.commit()
            con.close()
            return page(
                '<div class="card"><h2>إجابة صحيحة! 🎉</h2>'
                '<p>حصلت على 10 نقاط إذا كانت هذه أول مرة تجتاز فيها المرحلة.</p>'
                '<a href="/dashboard">العودة للمراحل</a></div>'
            )
        msg = "إجابة غير صحيحة، حاول مرة أخرى."
    options = ""
    for i, option in enumerate(q[1]):
        options += f'<p><label><input style="width:auto" type="radio" name="answer" value="{i}" required> {option}</label></p>'
    return page(
        f'<div class="card"><h2>المرحلة {number}</h2>'
        f'<h3>{q[0]}</h3><p style="color:red">{msg}</p>'
        f'<form method="post">{options}<button>تحقق من الإجابة</button></form>'
        '<a href="/dashboard">رجوع</a></div>'
    )

@app.route("/admin")
@login_required
def admin():
    con = connect()
    user = con.execute(
        "SELECT admin FROM users WHERE id=?", (session["user"],)
    ).fetchone()
    if not user or not user[0]:
        con.close()
        return "غير مسموح لك بالدخول"
    users = con.execute(
        "SELECT name,email,points FROM users WHERE admin=0"
    ).fetchall()
    con.close()
    rows = "".join(
        f"<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td></tr>"
        for u in users
    )
    return page(
        '<div class="card"><h2>لوحة الأدمن</h2>'
        '<table border="1" cellpadding="8"><tr><th>الاسم</th>'
        '<th>البريد</th><th>النقاط</th></tr>' + rows +
        '</table><br><a href="/dashboard">الرئيسية</a></div>'
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
      
