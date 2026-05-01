from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response 
from werkzeug.utils import secure_filename
import os
import json
import calendar
from calendar import monthrange
from datetime import datetime
from dateutil.relativedelta import relativedelta
from weasyprint import HTML, CSS
from zoneinfo import ZoneInfo

from db import (
    init_db,
    fetch_all_dicts,
    fetch_one_dict,
    execute,
    execute_many,
    json_dumps,
    json_loads,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

USE_DB = bool(os.environ.get("DATABASE_URL"))

UPLOAD_FOLDER = 'static/player_photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Legacy file names kept only so template flow does not break if needed
PLAYERS_FILE = 'players.json'
MATCHES_FILE = 'matches.json'
ATTENDANCE_FILE = 'attendance.json'
PRACTICE_FILE = 'practice.json'
MIRCROCYCLE_FILE = 'microcycle.json'

init_db()

def get_team_display_name(team):
    return {
        "1": "First Team",
        "2": "Second Team"
    }.get(team, team)

def format_date(date_str):
    if not date_str:
        return ""

    try:
        # Handles normal HTML date input format: YYYY-MM-DD
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        return date_str

def format_month(month_str):
    if not month_str:
        return ""

    try:
        year, month = month_str.split('-')
        import calendar
        return f"{calendar.month_name[int(month)]} {year}"
    except:
        return month_str

@app.context_processor
def inject_team_name():
    return dict(
        get_team_display_name=get_team_display_name,
        format_date=format_date,
        format_month=format_month
    )

@app.route('/switch_team')
def switch_team():
    current = session.get('selected_team')
    if current == '1':
        session['selected_team'] = '2'
    elif current == '2':
        session['selected_team'] = '1'
    else:
        session['selected_team'] = '1'
    return redirect(request.referrer or url_for('team_dashboard'))


# ------------------ LEGACY JSON HELPERS (fallback/local only) ------------------

def get_file_path(base_filename):
    team = session.get('selected_team')
    if not team:
        return os.path.join("data", base_filename)
    filename = base_filename.replace(".json", f"{team}.json")
    return os.path.join("data", filename)


def load_data(base_filename):
    filepath = get_file_path(base_filename)
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r") as f:
        return json.load(f)


def save_data(base_filename, data):
    filepath = get_file_path(base_filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# ------------------ DB HELPERS ------------------

def db_select(sql_pg, sql_sqlite, params=()):
    return fetch_all_dicts(sql_pg if USE_DB else sql_sqlite, params)


def db_select_one(sql_pg, sql_sqlite, params=()):
    return fetch_one_dict(sql_pg if USE_DB else sql_sqlite, params)


def db_execute(sql_pg, sql_sqlite, params=()):
    execute(sql_pg if USE_DB else sql_sqlite, params)


def db_execute_many(statements_pg, statements_sqlite=None):
    if USE_DB:
        execute_many(statements_pg)
    else:
        execute_many(statements_sqlite if statements_sqlite is not None else statements_pg)


def get_team():
    return session.get('selected_team')


def require_team_selected():
    if not get_team():
        return redirect(url_for('home'))
    return None


# ------------------ DATA ACCESSORS ------------------

def get_players():
    team = get_team()
    rows = db_select(
        "SELECT * FROM players WHERE team = %s ORDER BY number",
        "SELECT * FROM players WHERE team = ? ORDER BY number",
        (team,)
    )
    return {row["number"]: row for row in rows}


def get_player(num):
    team = get_team()
    return db_select_one(
        "SELECT * FROM players WHERE team = %s AND number = %s",
        "SELECT * FROM players WHERE team = ? AND number = ?",
        (team, num)
    )


def get_matches():
    team = get_team()
    rows = db_select(
        "SELECT * FROM matches WHERE team = %s ORDER BY date, time",
        "SELECT * FROM matches WHERE team = ? ORDER BY date, time",
        (team,)
    )
    return {row["match_id"]: row for row in rows}


def get_match(match_id):
    team = get_team()
    return db_select_one(
        "SELECT * FROM matches WHERE team = %s AND match_id = %s",
        "SELECT * FROM matches WHERE team = ? AND match_id = ?",
        (team, match_id)
    )


def get_daily_attendance(date_str):
    team = get_team()
    rows = db_select(
        "SELECT player_number, present FROM attendance_daily WHERE team = %s AND date = %s",
        "SELECT player_number, present FROM attendance_daily WHERE team = ? AND date = ?",
        (team, date_str)
    )
    return [row["player_number"] for row in rows if int(row["present"]) == 1]


def save_daily_attendance(date_str, present_numbers):
    team = get_team()
    present_set = set(present_numbers)

    # delete existing rows for that day/team, then insert current
    statements_pg = [
        ("DELETE FROM attendance_daily WHERE team = %s AND date = %s", (team, date_str))
    ]
    statements_sqlite = [
        ("DELETE FROM attendance_daily WHERE team = ? AND date = ?", (team, date_str))
    ]

    for num in present_set:
        statements_pg.append((
            "INSERT INTO attendance_daily (team, date, player_number, present) VALUES (%s, %s, %s, %s)",
            (team, date_str, num, 1)
        ))
        statements_sqlite.append((
            "INSERT INTO attendance_daily (team, date, player_number, present) VALUES (?, ?, ?, ?)",
            (team, date_str, num, 1)
        ))

    db_execute_many(statements_pg, statements_sqlite)


def get_monthly_attendance_map(month_label):
    team = get_team()
    rows = db_select(
        "SELECT player_number, day, status FROM attendance_monthly WHERE team = %s AND month_label = %s",
        "SELECT player_number, day, status FROM attendance_monthly WHERE team = ? AND month_label = ?",
        (team, month_label)
    )
    result = {}
    for row in rows:
        num = row["player_number"]
        day = int(row["day"])
        result.setdefault(num, {})[f"{month_label}-{day}"] = row["status"]
    return result


def save_monthly_attendance_map(month_label, new_data):
    team = get_team()

    statements_pg = [
        ("DELETE FROM attendance_monthly WHERE team = %s AND month_label = %s", (team, month_label))
    ]
    statements_sqlite = [
        ("DELETE FROM attendance_monthly WHERE team = ? AND month_label = ?", (team, month_label))
    ]

    for num, records in new_data.items():
        for key, status in records.items():
            try:
                day = int(str(key).split("-")[-1])
            except Exception:
                continue
            statements_pg.append((
                "INSERT INTO attendance_monthly (team, month_label, player_number, day, status) VALUES (%s, %s, %s, %s, %s)",
                (team, month_label, num, day, status)
            ))
            statements_sqlite.append((
                "INSERT INTO attendance_monthly (team, month_label, player_number, day, status) VALUES (?, ?, ?, ?, ?)",
                (team, month_label, num, day, status)
            ))

    db_execute_many(statements_pg, statements_sqlite)


def get_available_month_labels():
    team = get_team()
    rows = db_select(
        "SELECT DISTINCT month_label FROM attendance_monthly WHERE team = %s ORDER BY month_label",
        "SELECT DISTINCT month_label FROM attendance_monthly WHERE team = ? ORDER BY month_label",
        (team,)
    )
    return [row["month_label"] for row in rows]


def get_practice_month(month_str):
    team = get_team()
    rows = db_select(
        """
        SELECT date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end
        FROM practice_schedule
        WHERE team = %s AND date LIKE %s
        ORDER BY date
        """,
        """
        SELECT date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end
        FROM practice_schedule
        WHERE team = ? AND date LIKE ?
        ORDER BY date
        """,
        (team, f"{month_str}%")
    )
    result = {}
    for row in rows:
        result[row["date"]] = {
            "main": row.get("main") or "",
            "secondary": row.get("secondary") or "",
            "note_main_start": row.get("note_main_start") or "",
            "note_main_end": row.get("note_main_end") or "",
            "note_secondary_start": row.get("note_secondary_start") or "",
            "note_secondary_end": row.get("note_secondary_end") or "",
        }
    return result


def save_practice_month(month_str, month_schedule):
    team = get_team()

    statements_pg = [
        ("DELETE FROM practice_schedule WHERE team = %s AND date LIKE %s", (team, f"{month_str}%"))
    ]
    statements_sqlite = [
        ("DELETE FROM practice_schedule WHERE team = ? AND date LIKE ?", (team, f"{month_str}%"))
    ]

    for day, entry in month_schedule.items():
        statements_pg.append((
            """
            INSERT INTO practice_schedule
            (team, date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                team,
                day,
                entry.get("main", ""),
                entry.get("secondary", ""),
                entry.get("note_main_start", ""),
                entry.get("note_main_end", ""),
                entry.get("note_secondary_start", ""),
                entry.get("note_secondary_end", ""),
            )
        ))
        statements_sqlite.append((
            """
            INSERT INTO practice_schedule
            (team, date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team,
                day,
                entry.get("main", ""),
                entry.get("secondary", ""),
                entry.get("note_main_start", ""),
                entry.get("note_main_end", ""),
                entry.get("note_secondary_start", ""),
                entry.get("note_secondary_end", ""),
            )
        ))

    db_execute_many(statements_pg, statements_sqlite)


def copy_practice_month(source_month, target_month):
    source = get_practice_month(source_month)
    transformed = {}
    for date_str, entry in source.items():
        day = date_str.split("-")[-1]
        transformed[f"{target_month}-{day}"] = entry
    save_practice_month(target_month, transformed)


def get_all_practice():
    team = get_team()
    rows = db_select(
        """
        SELECT date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end
        FROM practice_schedule
        WHERE team = %s
        ORDER BY date
        """,
        """
        SELECT date, main, secondary, note_main_start, note_main_end, note_secondary_start, note_secondary_end
        FROM practice_schedule
        WHERE team = ?
        ORDER BY date
        """,
        (team,)
    )
    result = {}
    for row in rows:
        month_str = row["date"][:7]
        result.setdefault(month_str, {})
        result[month_str][row["date"]] = {
            "main": row.get("main") or "",
            "secondary": row.get("secondary") or "",
            "note_main_start": row.get("note_main_start") or "",
            "note_main_end": row.get("note_main_end") or "",
            "note_secondary_start": row.get("note_secondary_start") or "",
            "note_secondary_end": row.get("note_secondary_end") or "",
        }
    return result


def get_microcycle(from_date):
    team = get_team()
    row = db_select_one(
        "SELECT * FROM microcycles WHERE team = %s AND from_date = %s",
        "SELECT * FROM microcycles WHERE team = ? AND from_date = ?",
        (team, from_date)
    )
    if not row:
        return None
    row["content_json"] = json_loads(row["content_json"])
    return row


def get_all_microcycles():
    team = get_team()
    rows = db_select(
        "SELECT * FROM microcycles WHERE team = %s ORDER BY from_date DESC",
        "SELECT * FROM microcycles WHERE team = ? ORDER BY from_date DESC",
        (team,)
    )
    result = {}
    for row in rows:
        result[row["from_date"]] = {
            "meta": {
                "microcycle": row.get("meta_microcycle") or "",
                "from": row.get("meta_from") or "",
                "to": row.get("meta_to") or "",
                "week": row.get("meta_week") or "",
                "period": row.get("meta_period") or "",
            },
            **json_loads(row.get("content_json") or "{}")
        }
    return result


def save_microcycle_entry(from_date, meta, table_data):
    team = get_team()
    content_json = json_dumps(table_data)

    db_execute(
        "DELETE FROM microcycles WHERE team = %s AND from_date = %s",
        "DELETE FROM microcycles WHERE team = ? AND from_date = ?",
        (team, from_date)
    )

    db_execute(
        """
        INSERT INTO microcycles
        (team, from_date, meta_microcycle, meta_from, meta_to, meta_week, meta_period, content_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        """
        INSERT INTO microcycles
        (team, from_date, meta_microcycle, meta_from, meta_to, meta_week, meta_period, content_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            team,
            from_date,
            meta.get("microcycle", ""),
            meta.get("from", ""),
            meta.get("to", ""),
            meta.get("week", ""),
            meta.get("period", ""),
            content_json
        )
    )


# ------------------ AUTH ------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        admin_username = os.environ.get("ADMIN_USERNAME", "ziad")
        admin_password = os.environ.get("ADMIN_PASSWORD", "1971")

        if username == admin_username and password == admin_password:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.before_request
def require_login():
    allowed_routes = {"login", "static"}
    if request.endpoint is None:
        return
    if request.endpoint in allowed_routes:
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------ TEAM ------------------

@app.route('/')
def home():
    return render_template('choose_team.html')


@app.route('/set_team', methods=['POST'])
def set_team():
    team = request.form.get('team')
    if team in ['1', '2']:
        session['selected_team'] = team
        return redirect(url_for('team_dashboard'))
    return redirect(url_for('home'))


@app.route('/team_dashboard')
def team_dashboard():
    if not session.get('selected_team'):
        return redirect(url_for('home'))
    return render_template('index.html', team=session['selected_team'])


# ------------------ PLAYERS ------------------

@app.route('/players')
def list_players():
    no_team = require_team_selected()
    if no_team:
        return no_team
    players = get_players()
    return render_template('players.html', players=players)


@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    no_team = require_team_selected()
    if no_team:
        return no_team

    if request.method == 'POST':
        team = get_team()
        num = request.form['num'].strip()
        photo = request.files.get('photo')
        photo_filename = ''

        if photo and photo.filename:
            filename = secure_filename(num + '_' + photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        db_execute(
            """
            INSERT INTO players (team, number, name, height, weight, position, dob, comment, photo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            """
            INSERT INTO players (team, number, name, height, weight, position, dob, comment, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team,
                num,
                request.form['name'].strip(),
                request.form.get('height', '').strip(),
                request.form.get('weight', '').strip(),
                request.form.get('position', '').strip(),
                request.form.get('dob', '').strip(),
                request.form.get('comment', '').strip(),
                photo_filename
            )
        )

        flash('Player added successfully')
        return redirect(url_for('list_players'))

    return render_template('add_player.html')


@app.route('/edit_player/<string:num>', methods=['GET', 'POST'])
def edit_player(num):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()
    player = get_player(num)

    if not player:
        return "Player not found", 404

    if request.method == 'POST':
        photo = request.files.get('photo')
        photo_filename = player.get("photo", "")

        if photo and photo.filename:
            filename = secure_filename(num + '_' + photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        db_execute(
            """
            UPDATE players
            SET number = %s, name = %s, height = %s, weight = %s, position = %s, dob = %s, comment = %s, photo = %s
            WHERE team = %s AND number = %s
            """,
            """
            UPDATE players
            SET number = %s, name = ?, height = ?, weight = ?, position = ?, dob = ?, comment = ?, photo = ?
            WHERE team = ? AND number = ?
            """,
            (
                request.form.get('num', '').strip(),
                request.form['name'].strip(),
                request.form.get('height', '').strip(),
                request.form.get('weight', '').strip(),
                request.form.get('position', '').strip(),
                request.form.get('dob', '').strip(),
                request.form.get('comment', '').strip(),
                photo_filename,
                team,
                num
            )
        )

        flash('Player updated')
        return redirect(url_for('list_players'))

    return render_template('edit_player.html', num=num, player=player)


@app.route('/delete_player/<string:num>', methods=['POST'])
def delete_player(num):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()
    db_execute(
        "DELETE FROM players WHERE team = %s AND number = %s",
        "DELETE FROM players WHERE team = ? AND number = ?",
        (team, num)
    )
    flash('Player deleted')
    return redirect(url_for('list_players'))

@app.route("/players/export_pdf")
def export_players_pdf():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()

    html = render_template(
        "players_pdf.html",
        players=players,
        team=session.get("selected_team"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 portrait; margin: 10mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=players.pdf'
    return response



# ------------------ MATCHES ------------------

@app.route('/matches')
def list_matches():
    no_team = require_team_selected()
    if no_team:
        return no_team
    matches = get_matches()
    return render_template('matches.html', matches=matches)


@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    no_team = require_team_selected()
    if no_team:
        return no_team

    if request.method == 'POST':
        team = get_team()

        db_execute(
            """
            INSERT INTO matches (team, match_id, opponent, date, time, venue, competition, score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            """
            INSERT INTO matches (team, match_id, opponent, date, time, venue, competition, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team,
                request.form['match_id'].strip(),
                request.form['opponent'].strip(),
                request.form['date'],
                request.form['time'],
                request.form.get('venue', '').strip(),
                request.form.get('competition', '').strip(),
                'TBD'
            )
        )

        flash('Match added successfully')
        return redirect(url_for('list_matches'))

    return render_template('add_match.html')


@app.route('/edit_match/<match_id>', methods=['GET', 'POST'])
def edit_match(match_id):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()
    match = get_match(match_id)

    if not match:
        return "Match not found", 404

    if request.method == 'POST':
        db_execute(
            """
            UPDATE matches
            SET opponent = %s, date = %s, time = %s, venue = %s, competition = %s, score = %s
            WHERE team = %s AND match_id = %s
            """,
            """
            UPDATE matches
            SET opponent = ?, date = ?, time = ?, venue = ?, competition = ?, score = ?
            WHERE team = ? AND match_id = ?
            """,
            (
                request.form['opponent'].strip(),
                request.form['date'],
                request.form['time'],
                request.form.get('venue', '').strip(),
                request.form.get('competition', '').strip(),
                request.form.get('score', '').strip(),
                team,
                match_id
            )
        )

        flash('Match updated')
        return redirect(url_for('list_matches'))

    return render_template('edit_match.html', match_id=match_id, match=match)


@app.route('/delete_match/<match_id>', methods=['POST'])
def delete_match(match_id):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()
    db_execute(
        "DELETE FROM matches WHERE team = %s AND match_id = %s",
        "DELETE FROM matches WHERE team = ? AND match_id = ?",
        (team, match_id)
    )
    flash('Match deleted')
    return redirect(url_for('list_matches'))


@app.route('/edit_score/<match_id>', methods=['GET', 'POST'])
def edit_score(match_id):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()

    if request.method == 'POST':
        new_score = request.form['score']
        db_execute(
            "UPDATE matches SET score = %s WHERE team = %s AND match_id = %s",
            "UPDATE matches SET score = ? WHERE team = ? AND match_id = ?",
            (new_score, team, match_id)
        )
        flash('Score updated')
        return redirect(url_for('list_matches'))

    match = get_match(match_id)
    return render_template('edit_score.html', match_id=match_id, match=match)

@app.route("/matches/export_pdf")
def export_matches_pdf():
    no_team = require_team_selected()
    if no_team:
        return no_team

    matches = get_matches()

    html = render_template(
        "matches_pdf.html",
        matches=matches,
        team=session.get("selected_team"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 portrait; margin: 10mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=matches.pdf'
    return response


# ------------------ ATTENDANCE ------------------

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()
    available_months = get_available_month_labels()

    selected_month = request.values.get("month", "").strip()
    if not selected_month:
        if available_months:
            selected_month = available_months[0] 
        else:
            selected_month = datetime.now(ZoneInfo("Asia/Dubai")).strftime(%B %Y")

    month_key = f"monthly:{selected_month}"
    edit_mode = request.args.get("edit") == "1"

    try:
        month_name_text, year_text = selected_month.split()
        month_number = list(calendar.month_name).index(month_name_text)
        year = int(year_text)
        days_in_month = calendar.monthrange(year, month_number)[1]
    except Exception:
        days_in_month = 31

    if request.method == 'POST' and selected_month:
        new_data = {}
        for num in players:
            for day in range(1, days_in_month + 1):
                key = f"p{num}d{day}"
                values = request.form.getlist(key)
                val = next((v for v in reversed(values) if v in {"P", "A"}), "")
                if val in {"P", "A"}:
                    new_data.setdefault(num, {})[f"{selected_month}-{day}"] = val

        save_monthly_attendance_map(selected_month, new_data)
        flash("Attendance saved!")
        saved_attendance = new_data
        edit_mode = False
    else:
        saved_attendance = get_monthly_attendance_map(selected_month)

    stats = {}
    for num, player in players.items():
        records = saved_attendance.get(num, {})
        total_days = 0
        present = 0
        absent = 0

        for status in records.values():
            if status == 'P':
                present += 1
            elif status == 'A':
                absent += 1
            total_days += 1

        percent = round((present / total_days) * 100, 1) if total_days else 0
        stats[num] = {
            'name': player['name'],
            'present': present,
            'absent': absent,
            'percent': percent
        }

    return render_template(
        "attendance.html",
        players=players,
        selected_month=selected_month,
        saved_attendance=saved_attendance,
        edit_mode=edit_mode,
        stats=stats,
        days_in_month=days_in_month,
        month_key=month_key,
        available_months=available_months
    )


@app.route('/monthly_attendance', methods=['GET', 'POST'])
def monthly_attendance():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()

    if request.method == 'POST':
        month = request.form.get("month", "").strip()
        if not month:
            flash("Month is required.", "danger")
            return redirect(url_for('monthly_attendance'))

        try:
            month_text, year_text = month.split()
            month_number = list(calendar.month_name).index(month_text)
            year = int(year_text)
            days_in_month = monthrange(year, month_number)[1]
        except Exception:
            flash("Use format like June 2025.", "danger")
            return redirect(url_for('monthly_attendance'))

        attendance_data = {}
        for num in players:
            for day in range(1, days_in_month + 1):
                key = f"p{num}d{day}"
                values = request.form.getlist(key)
                status = next((v for v in reversed(values) if v in {"P", "A"}), "")
                if status in {"P", "A"}:
                    attendance_data.setdefault(num, {})[f"{month}-{day}"] = status

        save_monthly_attendance_map(month, attendance_data)
        flash("Monthly attendance saved!")
        return redirect(url_for('monthly_attendance'))

    return render_template("monthly_attendance.html", players=players)


@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()
    if request.method == 'POST':
        date = request.form['date']
        present = request.form.getlist('present')
        save_daily_attendance(date, present)
        flash('Attendance recorded')
        return redirect(url_for('view_attendance'))
    return render_template('mark_attendance.html', players=players)


@app.route('/edit_attendance/<date>', methods=['GET', 'POST'])
def edit_attendance(date):
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()

    if request.method == 'POST':
        present = request.form.getlist('present')
        save_daily_attendance(date, present)
        flash('Attendance updated')
        return redirect(url_for('view_attendance'))

    present = get_daily_attendance(date)
    return render_template('edit_attendance.html', date=date, players=players, present=present)


@app.route('/delete_attendance/<date>', methods=['POST'])
def delete_attendance(date):
    no_team = require_team_selected()
    if no_team:
        return no_team

    team = get_team()
    db_execute(
        "DELETE FROM attendance_daily WHERE team = %s AND date = %s",
        "DELETE FROM attendance_daily WHERE team = ? AND date = ?",
        (team, date)
    )
    flash('Attendance deleted')
    return redirect(url_for('view_attendance'))


@app.route('/view_attendance')
def view_attendance():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()
    team = get_team()
    rows = db_select(
        "SELECT date, player_number, present FROM attendance_daily WHERE team = %s ORDER BY date DESC, player_number",
        "SELECT date, player_number, present FROM attendance_daily WHERE team = ? ORDER BY date DESC, player_number",
        (team,)
    )

    grouped = {}
    for row in rows:
        date = row["date"]
        grouped.setdefault(date, [])
        if int(row["present"]) == 1:
            grouped[date].append(row["player_number"])

    # lightweight page without new template dependency
    return render_template(
        'view_monthly_attendance.html',
        players=players,
        attendance={},
        months=[],
        selected_month=None,
        daily_grouped=grouped,
        show_daily_only=True
    )


@app.route('/view_monthly_attendance')
def view_monthly_attendance():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()
    months_raw = get_available_month_labels()
    months = [f"monthly:{m}" for m in months_raw]
    selected_month = request.args.get('month', months[0] if months else None)
    if selected_month:
        month_label = selected_month.replace('monthly:', '')
        data = get_monthly_attendance_map(month_label)
    else:
        data = {}

    return render_template(
        'view_monthly_attendance.html',
        players=players,
        attendance=data,
        months=months,
        selected_month=selected_month
    )

@app.route("/attendance/export_pdf")
def export_attendance_pdf():
    no_team = require_team_selected()
    if no_team:
        return no_team

    players = get_players()
    selected_month = request.args.get("month", "").strip()
    if not selected_month:
        selected_month = datetime.now().strftime("%B %Y")

    try:
        month_name_text, year_text = selected_month.split()
        month_number = list(calendar.month_name).index(month_name_text)
        year = int(year_text)
        days_in_month = calendar.monthrange(year, month_number)[1]
    except Exception:
        days_in_month = 31

    saved_attendance = get_monthly_attendance_map(selected_month)

    stats = {}
    for num, player in players.items():
        records = saved_attendance.get(num, {})
        total_days = 0
        present = 0
        absent = 0

        for status in records.values():
            if status == "P":
                present += 1
            elif status == "A":
                absent += 1
            total_days += 1

        percent = round((present / total_days) * 100, 1) if total_days else 0
        stats[num] = {
            "name": player["name"],
            "present": present,
            "absent": absent,
            "percent": percent
        }

    html = render_template(
        "attendance_pdf.html",
        players=players,
        selected_month=selected_month,
        saved_attendance=saved_attendance,
        stats=stats,
        days_in_month=days_in_month,
        team=session.get("selected_team"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 landscape; margin: 8mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=attendance_{selected_month}.pdf'
    return response


# ------------------ PRACTICE ------------------

@app.route("/practice", methods=["GET", "POST"])
def practice():
    no_team = require_team_selected()
    if no_team:
        return no_team

    practice_data = get_all_practice()
    selected_month = request.form.get("month") or request.args.get("month") or datetime.now().strftime("%Y-%m")
    edit_mode = request.args.get("edit") == "1"
    year, month = map(int, selected_month.split("-"))
    total_days = monthrange(year, month)[1]

    current_date = datetime(year, month, 1)
    prev_month = (current_date - relativedelta(months=1)).strftime("%Y-%m")
    next_month = (current_date + relativedelta(months=1)).strftime("%Y-%m")

    calendar_grid = []
    week = [None] * datetime(year, month, 1).weekday()

    activity_filter = request.args.get("filter")
    raw_schedule = get_practice_month(selected_month)
    schedule = {}

    if activity_filter:
        for day, entry in raw_schedule.items():
            if entry.get("main") == activity_filter or entry.get("secondary") == activity_filter:
                schedule[day] = entry
    else:
        schedule = raw_schedule

    for day in range(1, total_days + 1):
        full_date = f"{selected_month}-{str(day).zfill(2)}"
        week.append(full_date)
        if len(week) == 7:
            calendar_grid.append(week)
            week = []

    if week:
        while len(week) < 7:
            week.append(None)
        calendar_grid.append(week)

    today = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%Y-%m-%d")

    overall_summary = {'GYM': 0, 'VOLLEYBALL': 0, 'FRIENDLY MATCH': 0, 'REST': 0, 'TOURNAMENT': 0}
    for month_data in practice_data.values():
        for entry in month_data.values():
            if isinstance(entry, dict):
                if entry.get("main") in overall_summary:
                    overall_summary[entry["main"]] += 1
                if entry.get("secondary") in overall_summary:
                    overall_summary[entry["secondary"]] += 1

    return render_template(
        "practice.html",
        selected_month=selected_month,
        schedule=schedule,
        calendar_grid=calendar_grid,
        month_days=total_days,
        week_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        edit_mode=edit_mode,
        today=today,
        prev_month=prev_month,
        next_month=next_month,
        overall_summary=overall_summary,
        activity_filter=activity_filter
    )


@app.route("/practice/save", methods=["POST"])
def save_practice():
    no_team = require_team_selected()
    if no_team:
        return no_team

    selected_month = request.form.get("month")
    month_schedule = {}

    for key in request.form:
        if key.startswith("main_") or key.startswith("secondary_"):
            day = key.split("_", 1)[1]
            main = request.form.get(f"main_{day}", "")
            secondary = request.form.get(f"secondary_{day}", "")
            note_main_start = request.form.get(f"note_main_start_{day}", "")
            note_main_end = request.form.get(f"note_main_end_{day}", "")
            note_secondary_start = request.form.get(f"note_secondary_start_{day}", "")
            note_secondary_end = request.form.get(f"note_secondary_end_{day}", "")
            if main or secondary or note_main_start or note_main_end or note_secondary_start or note_secondary_end:
                month_schedule[day] = {
                    "main": main,
                    "secondary": secondary,
                    "note_main_start": note_main_start,
                    "note_main_end": note_main_end,
                    "note_secondary_start": note_secondary_start,
                    "note_secondary_end": note_secondary_end
                }

    save_practice_month(selected_month, month_schedule)
    flash("Practice schedule saved successfully!")
    return redirect(url_for("practice", month=selected_month))


@app.route("/practice/repeat", methods=["POST"])
def repeat_practice():
    no_team = require_team_selected()
    if no_team:
        return no_team

    source_month = request.form.get("source_month")
    target_month = request.form.get("target_month")
    if source_month and target_month:
        copy_practice_month(source_month, target_month)
        flash(f"Copied schedule from {source_month} to {target_month}")
    return redirect(url_for("practice"))


@app.route("/practice/export_pdf/<month>")
def export_practice_pdf(month):
    no_team = require_team_selected()
    if no_team:
        return no_team

    schedule = get_practice_month(month)

    year, m = map(int, month.split("-"))
    total_days = monthrange(year, m)[1]
    first_day = datetime(year, m, 1)

    week = [None] * first_day.weekday()
    calendar_grid = []
    for day in range(1, total_days + 1):
        date_str = f"{month}-{str(day).zfill(2)}"
        week.append(date_str)
        if len(week) == 7:
            calendar_grid.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(None)
        calendar_grid.append(week)

    summary = {key: 0 for key in ['GYM', 'VOLLEYBALL', 'FRIENDLY MATCH', 'REST', 'TOURNAMENT']}
    for entry in schedule.values():
        main = entry.get("main", [])
        secondary = entry.get("secondary", [])
        main = [main] if isinstance(main, str) else main
        secondary = [secondary] if isinstance(secondary, str) else secondary

        for act in main:
            if act in summary:
                summary[act] += 1
        for act in secondary:
            if act in summary:
                summary[act] += 1

    total = sum(summary.values())

    html = render_template(
        "practice_pdf.html",
        month=month,
        week_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        calendar_grid=calendar_grid,
        schedule=schedule,
        summary=summary,
        total=total,
        datetime=datetime
    )

    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 landscape; margin: 10mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment;filename=practice_{month}.pdf'
    return response


@app.route("/practice/export/<month>")
def export_practice(month):
    no_team = require_team_selected()
    if no_team:
        return no_team
    month_data = get_practice_month(month)
    return json.dumps(month_data, indent=2), 200, {
        'Content-Type': 'application/json',
        'Content-Disposition': f'attachment; filename=practice_{month}.json'
    }


# ------------------ MICROCYCLE ------------------

@app.route("/microcycle", methods=["GET"])
def microcycle():
    no_team = require_team_selected()
    if no_team:
        return no_team

    all_data = get_all_microcycles()
    selected_key = request.args.get("week") or next(iter(all_data), "")

    data = all_data.get(selected_key, {})
    meta = data.get("meta", {"microcycle": "", "from": "", "to": "", "week": "", "period": ""})
    rows = ["Morning", "Afternoon"]
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    table = {row: {day: data.get(row, {}).get(day, "") for day in days} for row in rows}

    return render_template(
        "microcycle.html",
        data=table,
        days=days,
        rows=rows,
        meta=meta,
        all_keys=sorted(all_data.keys(), reverse=True),
        selected_key=selected_key
    )


@app.route("/microcycle/save", methods=["POST"])
def save_microcycle():
    no_team = require_team_selected()
    if no_team:
        return no_team

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    rows = ["Morning", "Afternoon"]

    meta = {
        "microcycle": request.form.get("meta_microcycle", ""),
        "from": request.form.get("meta_from", ""),
        "to": request.form.get("meta_to", ""),
        "week": request.form.get("meta_week", ""),
        "period": request.form.get("meta_period", "")
    }

    from_date = meta["from"]
    if not from_date:
        flash("From date is required to save.")
        return redirect(url_for("microcycle"))

    new_entry = {row: {day: request.form.get(f"{row}_{day}", "") for day in days} for row in rows}
    save_microcycle_entry(from_date, meta, new_entry)

    flash(f"Saved microcycle for week starting {from_date}")
    return redirect(url_for("microcycle", week=from_date))

@app.route("/microcycle/export_pdf")
def export_microcycle_pdf():
    no_team = require_team_selected()
    if no_team:
        return no_team

    selected_key = request.args.get("week", "")
    all_data = get_all_microcycles()

    if not selected_key:
        selected_key = next(iter(all_data), "")

    data = all_data.get(selected_key, {})
    meta = data.get("meta", {"microcycle": "", "from": "", "to": "", "week": "", "period": ""})
    rows = ["Morning", "Afternoon"]
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    table = {row: {day: data.get(row, {}).get(day, "") for day in days} for row in rows}

    html = render_template(
        "microcycle_pdf.html",
        data=table,
        days=days,
        rows=rows,
        meta=meta,
        team=session.get("selected_team"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 landscape; margin: 10mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=microcycle_{selected_key}.pdf'
    return response


# ------------------ SEASON ------------------

@app.route("/season")
def season():
    no_team = require_team_selected()
    if no_team:
        return no_team

    practice_data = get_all_practice()
    start_month = datetime(2026, 4, 1)
    end_month = datetime(2026, 8, 1)

    months = []
    month_labels = []

    while start_month <= end_month:
        month_str = start_month.strftime("%Y-%m")
        days_in_month = monthrange(start_month.year, start_month.month)[1]
        month_schedule = []

        for day in range(1, 32):
            if day > days_in_month:
                month_schedule.append({"activity": "", "date": "", "month": month_str})
                continue

            date_str = f"{month_str}-{day:02d}"
            entry = practice_data.get(month_str, {}).get(date_str, {})
            main = entry.get("main", "")
            secondary = entry.get("secondary", "")
            activity = ""

            if main in ["GYM", "VOLLEYBALL"] or secondary in ["GYM", "VOLLEYBALL"]:
                activity = "practice"
            elif main == "FRIENDLY MATCH" or secondary == "FRIENDLY MATCH":
                activity = "friendly"
            elif main == "REST" or secondary == "REST":
                activity = "rest"
            elif main == "TOURNAMENT" or secondary == "TOURNAMENT":
                activity = "tournament"

            month_schedule.append({
                "activity": activity,
                "date": date_str,
                "month": month_str
            })

        months.append(month_schedule)
        month_labels.append(start_month.strftime("%B %Y"))
        start_month += relativedelta(months=1)

    month_data = list(zip(month_labels, months))
    return render_template("season.html", month_data=month_data)


@app.route("/season/export_pdf")
def export_season_pdf():
    no_team = require_team_selected()
    if no_team:
        return no_team

    practice_data = get_all_practice()
    start_month = datetime(2026, 4, 1)
    end_month = datetime(2026, 8, 1)

    months = []
    labels = []

    while start_month <= end_month:
        month_str = start_month.strftime("%Y-%m")
        days_in_month = monthrange(start_month.year, start_month.month)[1]
        row = []

        for day in range(1, 32):
            if day > days_in_month:
                row.append("")
                continue

            date_str = f"{month_str}-{day:02d}"
            entry = practice_data.get(month_str, {}).get(date_str, {})
            main = entry.get("main", "")
            secondary = entry.get("secondary", "")
            activity = ""

            if main in ["GYM", "VOLLEYBALL"] or secondary in ["GYM", "VOLLEYBALL"]:
                activity = "practice"
            elif main == "FRIENDLY MATCH" or secondary == "FRIENDLY MATCH":
                activity = "friendly"
            elif main == "REST" or secondary == "REST":
                activity = "rest"
            elif main == "TOURNAMENT" or secondary == "TOURNAMENT":
                activity = "tournament"

            row.append(activity)

        labels.append(start_month.strftime("%B %Y"))
        months.append(row)
        start_month += relativedelta(months=1)

    month_data = list(zip(labels, months))

    html = render_template("season_pdf.html", month_data=month_data)
    pdf = HTML(string=html).write_pdf(stylesheets=[
        CSS(string='@page { size: A4 landscape; margin: 10mm; }')
    ])
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=season_overview.pdf'
    return response


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000))
