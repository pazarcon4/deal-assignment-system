import os
from datetime import date, datetime
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_connection, init_db
from notifications import send_email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "instance"))
SECRET_KEY_PATH = os.path.join(DATA_DIR, "secret_key")

APP_NAME = "IBM Consulting PH Deal Registration Application"
APP_VERSION = "v1.0"

STAGE_LABELS = {
    "unassigned": "Unassigned",
    "pending_acceptance": "Pending acceptance",
    "accepted": "Accepted",
    "in_progress": "In progress",
    "submitted": "Submitted",
}

STAGE_ORDER = {
    "unassigned": 0,
    "pending_acceptance": 1,
    "accepted": 2,
    "in_progress": 3,
    "submitted": 4,
}

ACTIVE_STAGES = ("pending_acceptance", "accepted", "in_progress")


def get_secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    if not os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "w") as f:
            f.write(os.urandom(32).hex())
    with open(SECRET_KEY_PATH) as f:
        return f.read().strip()


app = Flask(__name__)
app.secret_key = get_secret_key()
init_db()


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        conn = get_connection()
        g.user = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def days_until(target_date_str):
    if not target_date_str:
        return None
    try:
        target = date.fromisoformat(target_date_str)
    except ValueError:
        return None
    return (target - date.today()).days


def urgency_class(days):
    if days is None:
        return "unknown"
    if days < 0:
        return "overdue"
    if days <= 3:
        return "soon"
    return "ok"


def format_dt(dt):
    if dt is None:
        return ""
    return dt.strftime("%b %-d, %Y %-I:%M %p")


def format_tcv(value):
    if value is None:
        return ""
    return "${:,.0f}".format(value)


def get_user_by_id(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


app.jinja_env.globals.update(
    STAGE_LABELS=STAGE_LABELS,
    STAGE_ORDER=STAGE_ORDER,
    days_until=days_until,
    urgency_class=urgency_class,
    format_dt=format_dt,
    format_tcv=format_tcv,
    APP_NAME=APP_NAME,
    APP_VERSION=APP_VERSION,
)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE lower(email) = %s", (email,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    conn = get_connection()

    ops_users = conn.execute(
        "SELECT * FROM users WHERE role = 'sales_ops' ORDER BY name"
    ).fetchall()

    workload = []
    for ops in ops_users:
        deals = conn.execute(
            """
            SELECT deals.*, sellers.name AS seller_name
            FROM deals
            JOIN users AS sellers ON sellers.id = deals.seller_id
            WHERE deals.assigned_to = %s AND deals.stage IN ('pending_acceptance', 'accepted', 'in_progress')
            ORDER BY (deals.target_submission_date IS NULL), deals.target_submission_date ASC
            """,
            (ops["id"],),
        ).fetchall()
        workload.append({"user": ops, "deals": deals})

    my_deals = None
    needs_action = None
    all_deals = None

    if g.user["role"] == "seller":
        my_deals = conn.execute(
            """
            SELECT deals.*, ops.name AS assignee_name
            FROM deals
            LEFT JOIN users AS ops ON ops.id = deals.assigned_to
            WHERE deals.seller_id = %s
            ORDER BY deals.created_at DESC
            """,
            (g.user["id"],),
        ).fetchall()
    elif g.user["role"] == "sales_ops":
        needs_action = conn.execute(
            """
            SELECT deals.*, sellers.name AS seller_name
            FROM deals
            JOIN users AS sellers ON sellers.id = deals.seller_id
            WHERE deals.assigned_to = %s AND deals.stage != 'submitted'
            ORDER BY (deals.stage = 'pending_acceptance') DESC,
                     (deals.target_submission_date IS NULL), deals.target_submission_date ASC
            """,
            (g.user["id"],),
        ).fetchall()
    elif g.user["role"] == "admin":
        all_deals = conn.execute(
            """
            SELECT deals.*, sellers.name AS seller_name, ops.name AS assignee_name
            FROM deals
            JOIN users AS sellers ON sellers.id = deals.seller_id
            LEFT JOIN users AS ops ON ops.id = deals.assigned_to
            ORDER BY deals.created_at DESC
            """
        ).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        workload=workload,
        my_deals=my_deals,
        needs_action=needs_action,
        all_deals=all_deals,
    )


@app.route("/deals/new", methods=["GET", "POST"])
@role_required("seller", "admin")
def new_deal():
    conn = get_connection()
    ops_users = conn.execute(
        "SELECT * FROM users WHERE role = 'sales_ops' ORDER BY name"
    ).fetchall()

    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        salesforce_ref = request.form.get("salesforce_ref", "").strip()
        target_submission_date = request.form.get("target_submission_date", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()
        tcv_raw = request.form.get("tcv_usd", "").strip()

        errors = []
        if not client_name:
            errors.append("Client / deal name is required.")
        if not target_submission_date:
            errors.append("Target submission date is required.")
        else:
            try:
                date.fromisoformat(target_submission_date)
            except ValueError:
                errors.append("Target submission date must be a valid date.")

        tcv_usd = None
        if not tcv_raw:
            errors.append("TCV is required.")
        else:
            try:
                tcv_usd = float(tcv_raw)
                if tcv_usd < 0:
                    errors.append("TCV must be a positive number.")
            except ValueError:
                errors.append("TCV must be a valid number.")

        assigned_to_id = None
        stage = "unassigned"
        if assigned_to:
            assignee = conn.execute(
                "SELECT * FROM users WHERE id = %s AND role = 'sales_ops'", (assigned_to,)
            ).fetchone()
            if assignee is None:
                errors.append("Selected sales ops assignee is invalid.")
            else:
                assigned_to_id = assignee["id"]
                stage = "pending_acceptance"

        if errors:
            for error in errors:
                flash(error, "error")
            conn.close()
            return render_template(
                "new_deal.html",
                ops_users=ops_users,
                form=request.form,
            )

        conn.execute(
            """
            INSERT INTO deals (client_name, salesforce_ref, seller_id, assigned_to, stage,
                                target_submission_date, notes, tcv_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                client_name,
                salesforce_ref or None,
                g.user["id"],
                assigned_to_id,
                stage,
                target_submission_date,
                notes or None,
                tcv_usd,
            ),
        )
        conn.commit()
        conn.close()

        if assigned_to_id:
            send_email(
                assignee["email"],
                f"New deal assigned: {client_name}",
                f"{g.user['name']} assigned you a new deal: {client_name}\n"
                f"TCV: {format_tcv(tcv_usd)}\n"
                f"Target submission date: {target_submission_date}\n\n"
                f"View it: {url_for('dashboard', _external=True)}",
            )

        flash("Deal created.", "success")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("new_deal.html", ops_users=ops_users, form={})


def get_deal_or_404(conn, deal_id):
    deal = conn.execute("SELECT * FROM deals WHERE id = %s", (deal_id,)).fetchone()
    if deal is None:
        abort(404)
    return deal


@app.route("/deals/<int:deal_id>/edit", methods=["GET", "POST"])
@role_required("seller", "admin")
def edit_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if g.user["role"] == "seller" and deal["seller_id"] != g.user["id"]:
        conn.close()
        abort(403)

    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        salesforce_ref = request.form.get("salesforce_ref", "").strip()
        target_submission_date = request.form.get("target_submission_date", "").strip()
        notes = request.form.get("notes", "").strip()
        tcv_raw = request.form.get("tcv_usd", "").strip()

        errors = []
        if not client_name:
            errors.append("Client / deal name is required.")
        if not target_submission_date:
            errors.append("Target submission date is required.")
        else:
            try:
                date.fromisoformat(target_submission_date)
            except ValueError:
                errors.append("Target submission date must be a valid date.")

        tcv_usd = None
        if not tcv_raw:
            errors.append("TCV is required.")
        else:
            try:
                tcv_usd = float(tcv_raw)
                if tcv_usd < 0:
                    errors.append("TCV must be a positive number.")
            except ValueError:
                errors.append("TCV must be a valid number.")

        if errors:
            for error in errors:
                flash(error, "error")
            conn.close()
            return render_template("edit_deal.html", deal=deal, form=request.form)

        conn.execute(
            """
            UPDATE deals
            SET client_name = %s, salesforce_ref = %s, target_submission_date = %s,
                notes = %s, tcv_usd = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (client_name, salesforce_ref or None, target_submission_date, notes or None, tcv_usd, deal_id),
        )
        conn.commit()
        conn.close()
        flash("Deal updated.", "success")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit_deal.html", deal=deal, form=None)


@app.route("/deals/<int:deal_id>/delete", methods=["POST"])
@role_required("seller", "admin")
def delete_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if g.user["role"] == "seller" and deal["seller_id"] != g.user["id"]:
        conn.close()
        abort(403)

    conn.execute("DELETE FROM deals WHERE id = %s", (deal_id,))
    conn.commit()
    conn.close()
    flash(f"Deal \"{deal['client_name']}\" deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/deals/<int:deal_id>/accept", methods=["POST"])
@role_required("sales_ops")
def accept_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if deal["assigned_to"] != g.user["id"] or deal["stage"] != "pending_acceptance":
        conn.close()
        abort(403)

    conn.execute(
        "UPDATE deals SET stage = 'accepted', updated_at = NOW() WHERE id = %s",
        (deal_id,),
    )
    conn.commit()
    seller = get_user_by_id(conn, deal["seller_id"])
    conn.close()

    send_email(
        seller["email"],
        f"Deal accepted: {deal['client_name']}",
        f"{g.user['name']} accepted your deal: {deal['client_name']}\n\n"
        f"View it: {url_for('dashboard', _external=True)}",
    )

    flash("Deal accepted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/deals/<int:deal_id>/decline", methods=["POST"])
@role_required("sales_ops")
def decline_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if deal["assigned_to"] != g.user["id"] or deal["stage"] != "pending_acceptance":
        conn.close()
        abort(403)

    conn.execute(
        """
        UPDATE deals
        SET stage = 'unassigned', assigned_to = NULL, updated_at = NOW()
        WHERE id = %s
        """,
        (deal_id,),
    )
    conn.commit()
    seller = get_user_by_id(conn, deal["seller_id"])
    conn.close()

    send_email(
        seller["email"],
        f"Deal declined: {deal['client_name']}",
        f"{g.user['name']} declined your deal: {deal['client_name']}. "
        f"It's back in the unassigned pool for reassignment.\n\n"
        f"View it: {url_for('dashboard', _external=True)}",
    )

    flash("Deal declined and returned to the unassigned pool.", "success")
    return redirect(url_for("dashboard"))


@app.route("/deals/<int:deal_id>/update", methods=["POST"])
@role_required("sales_ops")
def update_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if deal["assigned_to"] != g.user["id"] or deal["stage"] not in ("accepted", "in_progress"):
        conn.close()
        abort(403)

    stage = request.form.get("stage", "")
    target_submission_date = request.form.get("target_submission_date", "").strip()
    actual_submission_date = request.form.get("actual_submission_date", "").strip()
    notes = request.form.get("notes", "").strip()

    allowed_next_stages = {"accepted": ("accepted", "in_progress"), "in_progress": ("in_progress", "submitted")}
    if stage not in allowed_next_stages.get(deal["stage"], ()):
        conn.close()
        abort(400)

    errors = []
    if target_submission_date:
        try:
            date.fromisoformat(target_submission_date)
        except ValueError:
            errors.append("Target submission date must be a valid date.")

    if stage == "submitted":
        if not actual_submission_date:
            actual_submission_date = date.today().isoformat()
        else:
            try:
                date.fromisoformat(actual_submission_date)
            except ValueError:
                errors.append("Actual submission date must be a valid date.")
    else:
        actual_submission_date = None

    if errors:
        for error in errors:
            flash(error, "error")
        conn.close()
        return redirect(url_for("dashboard"))

    conn.execute(
        """
        UPDATE deals
        SET stage = %s, target_submission_date = %s, actual_submission_date = %s,
            notes = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (
            stage,
            target_submission_date or deal["target_submission_date"],
            actual_submission_date,
            notes or None,
            deal_id,
        ),
    )
    conn.commit()
    seller = get_user_by_id(conn, deal["seller_id"])
    conn.close()

    send_email(
        seller["email"],
        f"Deal update: {deal['client_name']} -> {STAGE_LABELS[stage]}",
        f"{g.user['name']} updated your deal: {deal['client_name']}\n"
        f"New stage: {STAGE_LABELS[stage]}\n\n"
        f"View it: {url_for('dashboard', _external=True)}",
    )

    flash("Deal updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/deals/<int:deal_id>/reassign", methods=["POST"])
@role_required("seller", "admin")
def reassign_deal(deal_id):
    conn = get_connection()
    deal = get_deal_or_404(conn, deal_id)
    if deal["stage"] != "unassigned":
        conn.close()
        abort(403)
    if g.user["role"] == "seller" and deal["seller_id"] != g.user["id"]:
        conn.close()
        abort(403)

    assigned_to = request.form.get("assigned_to", "").strip()
    assignee = conn.execute(
        "SELECT * FROM users WHERE id = %s AND role = 'sales_ops'", (assigned_to,)
    ).fetchone()
    if assignee is None:
        conn.close()
        flash("Selected sales ops assignee is invalid.", "error")
        return redirect(url_for("dashboard"))

    conn.execute(
        """
        UPDATE deals SET assigned_to = %s, stage = 'pending_acceptance', updated_at = NOW()
        WHERE id = %s
        """,
        (assignee["id"], deal_id),
    )
    conn.commit()
    conn.close()

    send_email(
        assignee["email"],
        f"New deal assigned: {deal['client_name']}",
        f"You've been assigned a deal: {deal['client_name']}\n"
        f"TCV: {format_tcv(deal['tcv_usd'])}\n\n"
        f"View it: {url_for('dashboard', _external=True)}",
    )

    flash("Deal reassigned.", "success")
    return redirect(url_for("dashboard"))


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(g.user["password_hash"], current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("New password and confirmation do not match.", "error")
        else:
            conn = get_connection()
            conn.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (generate_password_hash(new_password, method="pbkdf2:sha256"), g.user["id"]),
            )
            conn.commit()
            conn.close()
            flash("Password updated.", "success")
            return redirect(url_for("dashboard"))

    return render_template("change_password.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
