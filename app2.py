from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
import json
from calendar import monthrange, month_name
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'static/player_photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PLAYERS_FILE = 'players.json'
MATCHES_FILE = 'matches.json'
ATTENDANCE_FILE = 'attendance.json'
PRACTICE_FILE = 'practice.json'
MIRCROCYCLE_FILE = 'microcycle.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper functions
def load_data(base_filename):
    filepath = get_file_path(base_filename)
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r") as f:
        return json.load(f)

def save_data(base_filename, data):
    filepath = get_file_path(base_filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

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

def get_file_path(base_filename):
    team = session.get('selected_team')
    if not team:
        return os.path.join("data", base_filename)
    filename = base_filename.replace(".json", f"{team}.json")
    return os.path.join("data", filename)

@app.route('/players')
def list_players():
    players_file = get_file_path("players.json")
    players = load_data(PLAYERS_FILE)
    return render_template('players.html', players=players)

@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        players_file = get_file_path("players.json")
        players = load_data(PLAYERS_FILE)
        num = request.form['num']
        photo = request.files.get('photo')
        photo_filename = ''

        if photo:
            filename = secure_filename(num + '_' + photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        players[num] = {
            'name': request.form['name'],
            'height': request.form['height'],
            'weight': request.form['weight'],
            'position': request.form['position'],
            'dob': request.form['dob'],
            'comment': request.form['comment'],
            'photo': photo_filename
        }
        save_data(PLAYERS_FILE, players)
        flash('Player added successfully')
        return redirect(url_for('list_players'))
    return render_template('add_player.html')

@app.route('/edit_player/<string:num>', methods=['GET', 'POST'])
def edit_player(num):
    players_file = get_file_path("players.json")
    players = load_data(PLAYERS_FILE)
    if num not in players:
        return "Player not found", 404

    if request.method == 'POST':
        player = players[num]
        player['name'] = request.form['name']
        player['height'] = request.form['height']
        player['weight'] = request.form['weight']
        player['position'] = request.form['position']
        player['dob'] = request.form['dob']
        player['comment'] = request.form['comment']

        photo = request.files.get('photo')
        if photo and photo.filename:
            filename = secure_filename(num + '_' + photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            player['photo'] = filename

        save_data(PLAYERS_FILE, players)
        flash('Player updated')
        return redirect(url_for('list_players'))

    return render_template('edit_player.html', num=num, player=players[num])

@app.route('/delete_player/<string:num>', methods=['POST'])
def delete_player(num):
    players_file = get_file_path("players.json")
    players = load_data(PLAYERS_FILE)
    if num in players:
        del players[num]
        save_data(PLAYERS_FILE, players)
        flash('Player deleted')
    return redirect(url_for('list_players'))

@app.route('/matches')
def list_matches():
    matches_file = get_file_path("matches.json")
    matches = load_data(MATCHES_FILE)
    return render_template('matches.html', matches=matches)

@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    if request.method == 'POST':
        matches_file = get_file_path("matches.json")
        matches = load_data(MATCHES_FILE)
        match_id = request.form['match_id']
        matches[match_id] = {
            'opponent': request.form['opponent'],
            'date': request.form['date'],
            'time': request.form['time'],
            'venue': request.form['venue'],
            'competition': request.form['competition'],
            'score': 'TBD'
        }
        save_data(MATCHES_FILE, matches)
        flash('Match added successfully')
        return redirect(url_for('list_matches'))
    return render_template('add_match.html')

@app.route('/edit_match/<match_id>', methods=['GET', 'POST'])
def edit_match(match_id):
    matches_file = get_file_path("matches.json")
    matches = load_data(MATCHES_FILE)
    if match_id not in matches:
        return "Match not found", 404

    if request.method == 'POST':
        match = matches[match_id]
        match['opponent'] = request.form['opponent']
        match['date'] = request.form['date']
        match['time'] = request.form['time']
        match['venue'] = request.form['venue']
        match['competition'] = request.form['competition']
        match['score'] = request.form['score']
        save_data(MATCHES_FILE, matches)
        flash('Match updated')
        return redirect(url_for('list_matches'))

    return render_template('edit_match.html', match_id=match_id, match=matches[match_id])

@app.route('/delete_match/<match_id>', methods=['POST'])
def delete_match(match_id):
    matches_file = get_file_path("matches.json")
    matches = load_data(MATCHES_FILE)
    if match_id in matches:
        del matches[match_id]
        save_data(MATCHES_FILE, matches)
        flash('Match deleted')
    return redirect(url_for('list_matches'))

@app.route('/edit_score/<match_id>', methods=['GET', 'POST'])
def edit_score(match_id):
    matches_file = get_file_path("matches.json")
    matches = load_data(MATCHES_FILE)
    if request.method == 'POST':
        new_score = request.form['score']
        matches[match_id]['score'] = new_score
        save_data(MATCHES_FILE, matches)
        flash('Score updated')
        return redirect(url_for('list_matches'))
    match = matches.get(match_id)
    return render_template('edit_score.html', match_id=match_id, match=match)

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    players_file = get_file_path("players.json")
    attendance_file = get_file_path("attendance.json")
    players = load_data(PLAYERS_FILE)
    attendance_data = load_data(ATTENDANCE_FILE)
    available_months = [key.replace("monthly:", "") for key in attendance_data.keys() if key.startswith("monthly:")]
    
    from datetime import datetime
    import calendar

    selected_month = request.values.get("month", "").strip()
    # Default to current month if none
    if not selected_month:
            selected_month = datetime.now().strftime("%B %Y")
    month_key= f"monthly:{selected_month}"
    edit_mode= request.args.get("edit")== "1"
    # Extract number of days in the month
    try:
        month_name, year = selected_month.split()
        month_number = list(calendar.month_name).index(month_name)
        year = int(year)
        days_in_month = calendar.monthrange(year, month_number)[1]
    except:
        days_in_month = 31 # fallback
        edit_mode = request.args.get("edit") == "1"
        saved_attendance = {}
        month_key = f"monthly:{selected_month}"

    if request.method == 'POST' and selected_month:
        new_data = {}
        for num in players:
            for day in range(1, days_in_month + 1):
                key = f"p{num}d{day}"
                val = request.form.get(key)
                if val:
                    new_data.setdefault(num, {})[f"{selected_month}-{day}"] = val
        attendance_data[month_key] = new_data
        save_data(ATTENDANCE_FILE, attendance_data)
        flash("Attendance saved!")
        saved_attendance = new_data
        edit_mode = False
    elif selected_month:
        saved_attendance = attendance_data.get(month_key, {})

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

    return render_template("attendance.html",
                           players=players,
                           selected_month=selected_month,
                           saved_attendance=saved_attendance,
                           edit_mode=edit_mode,
                           stats=stats,
                           days_in_month=days_in_month,
                           month_key=month_key,
                           available_months=available_months)

@app.route('/monthly_attendance', methods=['GET', 'POST'])
def monthly_attendance():
    players_file = get_file_path("players.json")
    players = load_data(PLAYERS_FILE)

    if request.method == 'POST':
        month = request.form.get("month", "unknown")
        attendance_data = {}

        for num in players:
            for day in range(1, days_in_month + 1):
                key = f"p{num}d{day}"
                status = request.form.get(key)
                if status:
                    attendance_data.setdefault(num, {})[f"{month}-{day}"] = status

        existing = load_data(ATTENDANCE_FILE)
        existing[f"monthly:{month}"] = attendance_data
        save_data(ATTENDANCE_FILE, existing)
        flash("Monthly attendance saved!")
        return redirect(url_for('monthly_attendance'))

    return render_template("monthly_attendance.html", players=players)

@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    players_file = get_file_path("players.json")
    players = load_data(PLAYERS_FILE)
    if request.method == 'POST':
        date = request.form['date']
        attendance = load_data(ATTENDANCE_FILE)
        attendance[date] = request.form.getlist('present')
        save_data(ATTENDANCE_FILE, attendance)
        flash('Attendance recorded')
        return redirect(url_for('view_attendance'))
    return render_template('mark_attendance.html', players=players)

@app.route('/edit_attendance/<date>', methods=['GET', 'POST'])
def edit_attendance(date):
    players_file = get_file_path("players.json")
    attendance_file = get_file_path("attendance.json")
    attendance = load_data(ATTENDANCE_FILE)
    players = load_data(PLAYERS_FILE)

    if request.method == 'POST':
        attendance[date] = request.form.getlist('present')
        save_data(ATTENDANCE_FILE, attendance)
        flash('Attendance updated')
        return redirect(url_for('view_attendance'))

    present = attendance.get(date, [])
    return render_template('edit_attendance.html', date=date, players=players, present=present)

@app.route('/delete_attendance/<date>', methods=['POST'])
def delete_attendance(date):
    attendance_file = get_file_path("attendance.json")
    attendance = load_data(ATTENDANCE_FILE)
    if date in attendance:
        del attendance[date]
        save_data(ATTENDANCE_FILE, attendance)
        flash('Attendance deleted')
    return redirect(url_for('view_attendance'))

@app.route('/view_monthly_attendance')
def view_monthly_attendance():
    players_file = get_file_path("players.json")
    attendance_file = get_file_path("attendance.json")
    players = load_data(PLAYERS_FILE)
    attendance = load_data(ATTENDANCE_FILE)

    months = [key for key in attendance if key.startswith('monthly:')]
    selected_month = request.args.get('month', months[0] if months else None)
    data = attendance.get(selected_month, {}) if selected_month else {}

    return render_template('view_monthly_attendance.html',
                           players=players,
                           attendance=data,
                           months=months,
                           selected_month=selected_month)

from dateutil.relativedelta import relativedelta

@app.route("/practice", methods=["GET", "POST"])
def practice():
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
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
    raw_schedule = practice_data.get(selected_month, {})
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

    today = datetime.now().strftime("%Y-%m-%d")
    

    overall_summary = {'GYM': 0, 'VOLLEYBALL': 0, 'FRIENDLY MATCH': 0, 'REST': 0, 'TOURNAMENT': 0}
    for month_data in practice_data.values():
        for entry in month_data.values():
            if isinstance(entry, dict):
                if entry.get("main") in overall_summary:
                    overall_summary[entry["main"]] += 1
                if entry.get("secondary") in overall_summary:
                    overall_summary[entry["secondary"]] += 1

    return render_template("practice.html",
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
                           activity_filter=activity_filter)

@app.route("/practice/save", methods=["POST"])
def save_practice():
    selected_month = request.form.get("month")
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
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

    practice_data[selected_month] = month_schedule
    save_data(PRACTICE_FILE, practice_data)
    flash("Practice schedule saved successfully!")
    return redirect(url_for("practice", month=selected_month))

@app.route("/practice/repeat", methods=["POST"])
def repeat_practice():
    source_month = request.form.get("source_month")
    target_month = request.form.get("target_month")
    if source_month and target_month:
        practice_file = get_file_path("practice.json")
        practice_data = load_data(PRACTICE_FILE)
        if source_month in practice_data:
            practice_data[target_month] = practice_data[source_month]
            save_data(PRACTICE_FILE, practice_data)
            flash(f"Copied schedule from {source_month} to {target_month}")
    return redirect(url_for("practice"))

from flask import make_response
from weasyprint import HTML, CSS
from datetime import datetime

@app.route("/practice/export_pdf/<month>")
def export_practice_pdf(month):
    from calendar import monthrange
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
    schedule = practice_data.get(month, {})

    year, m = map(int, month.split("-"))
    total_days = monthrange(year, m)[1]
    first_day = datetime(year, m, 1)

    # Build calendar grid
    week = [None] * first_day.weekday()  # Fill in leading blanks
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

    summary = {key: 0 for key in['GYM', 'VOLLEYBALL', 'FRIENDLY MATCH', 'REST', 'TOURNAMENT']}
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
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
    month_data = practice_data.get(month, {})
    return json.dumps(month_data, indent=2), 200, {
        'Content-Type': 'application/json',
        'Content-Disposition': f'attachment; filename=practice_{month}.json'
    }


@app.route("/microcycle", methods=["GET"])
def microcycle():
    microcycle_file = get_file_path("microcycle.json")
    all_data = load_data("microcycle.json")
    selected_key = request.args.get("week") or next(iter(all_data), "")

    data = all_data.get(selected_key, {})
    meta = data.get("meta", {"microcycle": "", "from": "", "to": "", "week": "", "period": ""})
    rows = ["Morning", "Afternoon"]
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    table = {row: {day: data.get(row, {}).get(day, "") for day in days} for row in rows}

    return render_template("microcycle.html",
        data=table, days=days, rows=rows, meta=meta,
        all_keys=sorted(all_data.keys(), reverse=True),
        selected_key=selected_key
    )

@app.route("/microcycle/save", methods=["POST"])
def save_microcycle():
    microcycle_file = get_file_path("microcycle.json")
    all_data = load_data("microcycle.json")
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
    new_entry["meta"] = meta

    all_data[from_date] = new_entry
    save_data("microcycle.json", all_data)

    flash(f"Saved microcycle for week starting {from_date}")
    return redirect(url_for("microcycle", week=from_date))

@app.route("/season")
def season():
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
    start_month = datetime(2025, 6, 1)
    end_month = datetime(2026, 5, 1)

    months = []
    month_labels = []

    while start_month <= end_month:
        month_str = start_month.strftime("%Y-%m")
        days_in_month = monthrange(start_month.year, start_month.month)[1]
        month_schedule = []

        for day in range(1, 32):
            if day > days_in_month:
                month_schedule.append("")  # pad empty cells
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

            month_schedule.append(activity)

        months.append(month_schedule)
        month_labels.append(start_month.strftime("%B %Y"))
        start_month += relativedelta(months=1)

    month_data = list(zip(month_labels, months))
    return render_template("season.html", month_data=month_data)

from flask import make_response
from weasyprint import HTML, CSS

@app.route("/season/export_pdf")
def export_season_pdf():
    practice_file = get_file_path("practice.json")
    practice_data = load_data(PRACTICE_FILE)
    start_month = datetime(2025, 6, 1)
    end_month = datetime(2026, 5, 1)

    months = []
    labels = []

    while start_month <= end_month:
        month_str = start_month.strftime("%Y-%m")
        days_in_month = monthrange(start_month.year, start_month.month)[1]
        row = []

        for day in range(1, 32):
            if day > days_in_month:
                row.append("")  # pad blank
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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "ziad" and password == "1971":
            session["logged_in"] = True
            return redirect(url_for("team_dashboard"))  # or whatever your main page is
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")
@app.before_request
def require_login():
    allowed_routes = ["login", "static"]
    if not session.get("logged_in") and request.endpoint not in allowed_routes:
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000))
