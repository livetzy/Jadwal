"""
Jadwal Jabez - Personal Scheduler / Daily Planner
==================================================
Aplikasi web untuk mengatur jadwal kegiatan sehari-hari.
Dibangun dengan Flask + SQLite + Vanilla JS.
"""

import sqlite3
import os
import json
import csv
import io
from datetime import datetime, date, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, flash, g, send_file, Response
)
from werkzeug.datastructures import MultiDict

# ── Inisialisasi Flask ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'jadwal-jabez-secret-key-2026'

# Lokasi database
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

# ── Daftar kategori dan prioritas ───────────────────────────────────
CATEGORIES = [
    {'value': 'belajar', 'label': '📚 Belajar', 'color': '#6366f1'},
    {'value': 'kuliah', 'label': '🎓 Kuliah', 'color': '#8b5cf6'},
    {'value': 'coding', 'label': '💻 Coding', 'color': '#06b6d4'},
    {'value': 'olahraga', 'label': '🏃 Olahraga', 'color': '#22c55e'},
    {'value': 'ibadah', 'label': '🙏 Ibadah', 'color': '#f59e0b'},
    {'value': 'organisasi', 'label': '👥 Organisasi', 'color': '#ec4899'},
    {'value': 'pribadi', 'label': '🏠 Pribadi', 'color': '#14b8a6'},
    {'value': 'istirahat', 'label': '🛌 Istirahat', 'color': '#64748b'},
    {'value': 'lainnya', 'label': '📌 Lainnya', 'color': '#f97316'},
]

PRIORITIES = [
    {'value': 'tinggi', 'label': '🔴 Tinggi'},
    {'value': 'sedang', 'label': '🟡 Sedang'},
    {'value': 'rendah', 'label': '🟢 Rendah'},
]

HARI_INDONESIA = {
    'Monday': 'Senin',
    'Tuesday': 'Selasa',
    'Wednesday': 'Rabu',
    'Thursday': 'Kamis',
    'Friday': 'Jumat',
    'Saturday': 'Sabtu',
    'Sunday': 'Minggu',
}

WEEKDAYS = [
    ('monday', 'Senin'),
    ('tuesday', 'Selasa'),
    ('wednesday', 'Rabu'),
    ('thursday', 'Kamis'),
    ('friday', 'Jumat'),
    ('saturday', 'Sabtu'),
    ('sunday', 'Minggu'),
]

BULAN_INDONESIA = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
    5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember',
}


# ══════════════════════════════════════════════════════════════════════
# DATABASE HELPER
# ══════════════════════════════════════════════════════════════════════

def get_db():
    """Mendapatkan koneksi database (satu per request)."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # Agar bisa akses kolom pakai nama
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Menutup koneksi database setelah request selesai."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Membuat tabel schedules jika belum ada."""
    db = sqlite3.connect(DATABASE)
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            description     TEXT    DEFAULT '',
            date            TEXT    NOT NULL,
            start_time      TEXT    NOT NULL,
            end_time        TEXT    NOT NULL,
            category        TEXT    DEFAULT 'lainnya',
            priority        TEXT    DEFAULT 'sedang',
            is_completed    INTEGER DEFAULT 0,
            is_recurring    INTEGER DEFAULT 0,
            recurring_days  TEXT    DEFAULT '',
            sort_order      INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tambahkan kolom sort_order jika belum ada (untuk migrasi)
    try:
        db.execute('SELECT sort_order FROM schedules LIMIT 1')
    except sqlite3.OperationalError:
        db.execute('ALTER TABLE schedules ADD COLUMN sort_order INTEGER DEFAULT 0')

    db.execute('''
        CREATE TABLE IF NOT EXISTS schedule_completions (
            schedule_id     INTEGER NOT NULL,
            occurrence_date TEXT    NOT NULL,
            is_completed    INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (schedule_id, occurrence_date),
            FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
        )
    ''')
    db.commit()
    db.close()


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

def get_greeting():
    """Menentukan sapaan berdasarkan jam saat ini."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Selamat pagi, Jabez 👋"
    elif 12 <= hour < 15:
        return "Selamat siang, Jabez ☀️"
    elif 15 <= hour < 18:
        return "Selamat sore, Jabez 🌅"
    else:
        return "Selamat malam, Jabez 🌙"


def format_tanggal(tanggal_str):
    """Mengubah '2026-10-05' menjadi 'Senin, 5 Oktober 2026'."""
    try:
        d = datetime.strptime(tanggal_str, '%Y-%m-%d')
        hari = HARI_INDONESIA.get(d.strftime('%A'), d.strftime('%A'))
        bulan = BULAN_INDONESIA.get(d.month, '')
        return f"{hari}, {d.day} {bulan} {d.year}"
    except ValueError:
        return tanggal_str


def get_schedules_for_date(target_date):
    """
    Mengambil jadwal untuk tanggal tertentu.
    Termasuk jadwal berulang yang cocok dengan hari tersebut.
    """
    db = get_db()

    # Tentukan nama hari (dalam bahasa Inggris untuk pencocokan)
    d = datetime.strptime(target_date, '%Y-%m-%d')
    day_name = d.strftime('%A').lower()

    # Ambil jadwal non-recurring untuk tanggal ini
    # + jadwal recurring yang hari-nya cocok
    schedules = db.execute('''
        SELECT s.*,
               CASE WHEN s.is_recurring = 1
                    THEN COALESCE(c.is_completed, 0)
                    ELSE s.is_completed
               END AS occurrence_completed
        FROM schedules AS s
        LEFT JOIN schedule_completions AS c
            ON c.schedule_id = s.id AND c.occurrence_date = ?
        WHERE (s.is_recurring = 0 AND s.date = ?)
           OR (s.is_recurring = 1 AND s.recurring_days LIKE ?)
        ORDER BY s.sort_order ASC, s.start_time ASC
    ''', (target_date, target_date, f'%{day_name}%')).fetchall()

    result = []
    for schedule in schedules:
        item = dict(schedule)
        item['is_completed'] = item.pop('occurrence_completed')
        result.append(item)
    return result


def get_week_dates(reference_date=None):
    """Mendapatkan tanggal Senin-Minggu dari minggu yang mengandung reference_date."""
    if reference_date is None:
        reference_date = date.today()
    elif isinstance(reference_date, str):
        reference_date = datetime.strptime(reference_date, '%Y-%m-%d').date()

    # Senin = 0, Minggu = 6
    start_of_week = reference_date - timedelta(days=reference_date.weekday())
    week = []
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        week.append({
            'date': d.strftime('%Y-%m-%d'),
            'day_name': HARI_INDONESIA.get(d.strftime('%A'), d.strftime('%A')),
            'day_num': d.day,
            'is_today': d == date.today(),
        })
    return week


def get_statistics(view_date=None):
    """Menghitung statistik untuk dashboard."""
    db = get_db()
    if view_date is None:
        view_date = date.today().strftime('%Y-%m-%d')

    d = datetime.strptime(view_date, '%Y-%m-%d').date()

    # Statistik hari ini
    today_schedules = get_schedules_for_date(view_date)
    today_total = len(today_schedules)
    today_completed = sum(1 for s in today_schedules if s['is_completed'])

    # Statistik minggu ini
    start_of_week = d - timedelta(days=d.weekday())
    week_total = 0
    week_completed = 0
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_schedules = get_schedules_for_date(day.strftime('%Y-%m-%d'))
        week_total += len(day_schedules)
        week_completed += sum(1 for s in day_schedules if s['is_completed'])

    # Kategori terbanyak minggu ini
    category_counts = {}
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_schedules = get_schedules_for_date(day.strftime('%Y-%m-%d'))
        for s in day_schedules:
            cat = s['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1

    top_category = None
    top_category_label = '-'
    if category_counts:
        top_category = max(category_counts, key=category_counts.get)
        for cat in CATEGORIES:
            if cat['value'] == top_category:
                top_category_label = cat['label']
                break

    # Jadwal mendatang (upcoming)
    upcoming = db.execute('''
        SELECT * FROM schedules
        WHERE is_recurring = 0 AND date >= ? AND is_completed = 0
        ORDER BY date ASC, start_time ASC
        LIMIT 5
    ''', (view_date,)).fetchall()

    # Total semua jadwal
    all_total = db.execute('SELECT COUNT(*) as cnt FROM schedules').fetchone()['cnt']

    return {
        'today_total': today_total,
        'today_completed': today_completed,
        'today_pending': today_total - today_completed,
        'week_total': week_total,
        'week_completed': week_completed,
        'week_pending': week_total - week_completed,
        'top_category': top_category_label,
        'category_counts': category_counts,
        'upcoming': upcoming,
        'all_total': all_total,
    }


# ══════════════════════════════════════════════════════════════════════
# ROUTES — Halaman
# ══════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Halaman dashboard utama."""
    # Tanggal yang sedang dilihat (default: hari ini)
    view_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    schedules = get_schedules_for_date(view_date)

    # Hitung progress
    total = len(schedules)
    completed = sum(1 for s in schedules if s['is_completed'])
    progress = int((completed / total) * 100) if total > 0 else 0

    # Navigasi hari
    d = datetime.strptime(view_date, '%Y-%m-%d').date()
    prev_date = (d - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (d + timedelta(days=1)).strftime('%Y-%m-%d')

    # Statistik
    stats = get_statistics(view_date)

    return render_template('index.html',
        greeting=get_greeting(),
        tanggal_display=format_tanggal(view_date),
        view_date=view_date,
        prev_date=prev_date,
        next_date=next_date,
        is_today=(d == date.today()),
        schedules=schedules,
        total=total,
        completed=completed,
        progress=progress,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        stats=stats,
    )


@app.route('/weekly')
def weekly():
    """Halaman tampilan mingguan."""
    ref_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    week = get_week_dates(ref_date)

    # Ambil jadwal untuk setiap hari dalam minggu
    week_data = []
    for day in week:
        schedules = get_schedules_for_date(day['date'])
        total = len(schedules)
        completed = sum(1 for s in schedules if s['is_completed'])
        week_data.append({
            **day,
            'schedules': schedules,
            'total': total,
            'completed': completed,
        })

    # Navigasi minggu
    d = datetime.strptime(ref_date, '%Y-%m-%d').date()
    prev_week = (d - timedelta(weeks=1)).strftime('%Y-%m-%d')
    next_week = (d + timedelta(weeks=1)).strftime('%Y-%m-%d')

    today_schedules = get_schedules_for_date(ref_date)
    today_total = len(today_schedules)
    today_completed = sum(1 for s in today_schedules if s['is_completed'])
    stats = get_statistics(ref_date)

    return render_template('index.html',
        greeting=get_greeting(),
        tanggal_display=format_tanggal(ref_date),
        view_date=ref_date,
        prev_date=(d - timedelta(days=1)).strftime('%Y-%m-%d'),
        next_date=(d + timedelta(days=1)).strftime('%Y-%m-%d'),
        is_today=(d == date.today()),
        schedules=today_schedules,
        total=today_total,
        completed=today_completed,
        progress=int((today_completed / today_total) * 100) if today_total > 0 else 0,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        view_mode='weekly',
        week_data=week_data,
        prev_week=prev_week,
        next_week=next_week,
        stats=stats,
    )


@app.route('/add', methods=['GET', 'POST'])
def add_schedule():
    """Halaman dan handler untuk menambah jadwal baru."""
    if request.method == 'POST':
        # Ambil data dari form
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        schedule_date = request.form.get('date', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        category = request.form.get('category', 'lainnya')
        priority = request.form.get('priority', 'sedang')
        is_recurring = 1 if request.form.get('is_recurring') else 0
        recurring_days = ','.join(request.form.getlist('recurring_days'))

        # Validasi
        errors = []
        if not title:
            errors.append('Nama kegiatan wajib diisi.')
        if not schedule_date and not is_recurring:
            errors.append('Tanggal wajib diisi untuk jadwal non-berulang.')
        if not start_time:
            errors.append('Waktu mulai wajib diisi.')
        if not end_time:
            errors.append('Waktu selesai wajib diisi.')
        if start_time and end_time and start_time >= end_time:
            errors.append('Waktu selesai harus lebih besar dari waktu mulai.')
        if is_recurring and not recurring_days:
            errors.append('Pilih setidaknya satu hari untuk jadwal berulang.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('add_schedule.html',
                categories=CATEGORIES,
                priorities=PRIORITIES,
                weekdays=WEEKDAYS,
                form_data=request.form,
            )

        # Jika recurring tapi tanggal kosong, gunakan hari ini
        if not schedule_date:
            schedule_date = date.today().strftime('%Y-%m-%d')

        # Determine sort_order (append to end)
        db = get_db()
        max_order = db.execute(
            'SELECT COALESCE(MAX(sort_order), 0) as max_order FROM schedules'
        ).fetchone()['max_order']

        db.execute('''
            INSERT INTO schedules
                (title, description, date, start_time, end_time,
                 category, priority, is_recurring, recurring_days, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, schedule_date, start_time, end_time,
              category, priority, is_recurring, recurring_days, max_order + 1))
        db.commit()

        flash('Jadwal berhasil ditambahkan! 🎉', 'success')
        return redirect(url_for('index', date=schedule_date))

    return render_template('add_schedule.html',
        categories=CATEGORIES,
        priorities=PRIORITIES,
        weekdays=WEEKDAYS,
        form_data=MultiDict(),
    )


@app.route('/edit/<int:schedule_id>', methods=['GET', 'POST'])
def edit_schedule(schedule_id):
    """Halaman dan handler untuk mengedit jadwal."""
    db = get_db()
    existing_schedule = db.execute(
        'SELECT * FROM schedules WHERE id = ?', (schedule_id,)
    ).fetchone()

    if existing_schedule is None:
        flash('Jadwal tidak ditemukan.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        schedule_date = request.form.get('date', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        category = request.form.get('category', 'lainnya')
        priority = request.form.get('priority', 'sedang')
        is_recurring = 1 if request.form.get('is_recurring') else 0
        recurring_days = ','.join(request.form.getlist('recurring_days'))

        # Validasi
        errors = []
        if not title:
            errors.append('Nama kegiatan wajib diisi.')
        if not schedule_date and not is_recurring:
            errors.append('Tanggal wajib diisi untuk jadwal non-berulang.')
        if not start_time:
            errors.append('Waktu mulai wajib diisi.')
        if not end_time:
            errors.append('Waktu selesai wajib diisi.')
        if start_time and end_time and start_time >= end_time:
            errors.append('Waktu selesai harus lebih besar dari waktu mulai.')
        if is_recurring and not recurring_days:
            errors.append('Pilih setidaknya satu hari untuk jadwal berulang.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('edit_schedule.html',
                schedule=existing_schedule,
                categories=CATEGORIES,
                priorities=PRIORITIES,
                weekdays=WEEKDAYS,
                form_data=request.form,
            )

        if not schedule_date:
            schedule_date = date.today().strftime('%Y-%m-%d')

        db.execute('''
            UPDATE schedules SET
                title = ?, description = ?, date = ?,
                start_time = ?, end_time = ?, category = ?,
                priority = ?, is_recurring = ?, recurring_days = ?,
                is_completed = ?
            WHERE id = ?
        ''', (title, description, schedule_date, start_time, end_time,
              category, priority, is_recurring, recurring_days,
              0 if existing_schedule['is_recurring'] or is_recurring
              else existing_schedule['is_completed'],
              schedule_id))
        db.commit()

        flash('Jadwal berhasil diperbarui! ✅', 'success')
        return redirect(url_for('index', date=schedule_date))

    # GET — tampilkan form edit
    return render_template('edit_schedule.html',
        schedule=existing_schedule,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        weekdays=WEEKDAYS,
        form_data=MultiDict(),
    )


# ══════════════════════════════════════════════════════════════════════
# API ROUTES — AJAX (tanpa reload halaman)
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/toggle/<int:schedule_id>', methods=['POST'])
def toggle_schedule(schedule_id):
    """Toggle status selesai/belum selesai (via AJAX)."""
    db = get_db()
    schedule = db.execute(
        'SELECT * FROM schedules WHERE id = ?', (schedule_id,)
    ).fetchone()

    if schedule is None:
        return jsonify({'error': 'Jadwal tidak ditemukan'}), 404

    occurrence_date = request.args.get('date')
    if not occurrence_date:
        occurrence_date = (
            date.today().strftime('%Y-%m-%d')
            if schedule['is_recurring']
            else schedule['date']
        )
    try:
        parsed_date = datetime.strptime(occurrence_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Tanggal kejadian tidak valid'}), 400
    if parsed_date.strftime('%Y-%m-%d') != occurrence_date:
        return jsonify({'error': 'Tanggal kejadian tidak valid'}), 400

    occurrence = next(
        (item for item in get_schedules_for_date(occurrence_date)
         if item['id'] == schedule_id),
        None,
    )
    if occurrence is None:
        return jsonify({'error': 'Jadwal tidak tersedia pada tanggal tersebut'}), 409

    new_status = 0 if occurrence['is_completed'] else 1
    if schedule['is_recurring']:
        db.execute('''
            INSERT INTO schedule_completions (schedule_id, occurrence_date, is_completed)
            VALUES (?, ?, ?)
            ON CONFLICT (schedule_id, occurrence_date)
            DO UPDATE SET is_completed = excluded.is_completed
        ''', (schedule_id, occurrence_date, new_status))
    else:
        db.execute(
            'UPDATE schedules SET is_completed = ? WHERE id = ?',
            (new_status, schedule_id)
        )
    db.commit()

    return jsonify({
        'success': True,
        'is_completed': new_status,
        'id': schedule_id,
        'date': occurrence_date,
    })


@app.route('/api/delete/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Hapus jadwal (via AJAX)."""
    db = get_db()
    schedule = db.execute(
        'SELECT * FROM schedules WHERE id = ?', (schedule_id,)
    ).fetchone()

    if schedule is None:
        return jsonify({'error': 'Jadwal tidak ditemukan'}), 404

    db.execute('DELETE FROM schedules WHERE id = ?', (schedule_id,))
    db.commit()

    return jsonify({'success': True, 'id': schedule_id})


@app.route('/api/schedules')
def api_schedules():
    """Mengambil jadwal untuk tanggal tertentu (JSON)."""
    view_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    search_query = request.args.get('search', '').strip()
    filter_status = request.args.get('status', 'all')
    filter_category = request.args.get('category', 'all')

    schedules = get_schedules_for_date(view_date)

    # Convert ke list of dict agar bisa dimanipulasi
    result = []
    for s in schedules:
        item = dict(s)

        # Filter berdasarkan search
        if search_query and search_query.lower() not in item['title'].lower():
            continue

        # Filter berdasarkan status
        if filter_status == 'completed' and not item['is_completed']:
            continue
        if filter_status == 'pending' and item['is_completed']:
            continue

        # Filter berdasarkan kategori
        if filter_category != 'all' and item['category'] != filter_category:
            continue

        result.append(item)

    total = len(result)
    completed = sum(1 for s in result if s['is_completed'])
    progress = int((completed / total) * 100) if total > 0 else 0

    return jsonify({
        'schedules': result,
        'total': total,
        'completed': completed,
        'progress': progress,
    })


@app.route('/api/reorder', methods=['POST'])
def reorder_schedules():
    """Reorder jadwal via drag-and-drop (menerima list of IDs)."""
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'Data order tidak valid'}), 400

    order = data['order']  # List of schedule IDs in new order
    db = get_db()

    for idx, schedule_id in enumerate(order):
        db.execute(
            'UPDATE schedules SET sort_order = ? WHERE id = ?',
            (idx, int(schedule_id))
        )
    db.commit()

    return jsonify({'success': True})


@app.route('/api/statistics')
def api_statistics():
    """API statistik untuk dashboard."""
    view_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    stats = get_statistics(view_date)

    # Convert upcoming ke serializable format
    upcoming_list = []
    if stats['upcoming']:
        for s in stats['upcoming']:
            upcoming_list.append({
                'id': s['id'],
                'title': s['title'],
                'date': s['date'],
                'start_time': s['start_time'],
                'end_time': s['end_time'],
                'category': s['category'],
                'priority': s['priority'],
                'date_display': format_tanggal(s['date']),
            })

    return jsonify({
        'today_total': stats['today_total'],
        'today_completed': stats['today_completed'],
        'today_pending': stats['today_pending'],
        'week_total': stats['week_total'],
        'week_completed': stats['week_completed'],
        'week_pending': stats['week_pending'],
        'top_category': stats['top_category'],
        'category_counts': stats['category_counts'],
        'all_total': stats['all_total'],
        'upcoming': upcoming_list,
    })


@app.route('/api/reminders')
def api_reminders():
    """Mengambil jadwal yang akan datang dalam N menit ke depan (untuk notifikasi)."""
    minutes = int(request.args.get('minutes', 15))
    view_date = date.today().strftime('%Y-%m-%d')
    now = datetime.now()
    cutoff = now + timedelta(minutes=minutes)

    schedules = get_schedules_for_date(view_date)
    reminders = []

    for s in schedules:
        if s['is_completed']:
            continue
        try:
            start_dt = datetime.strptime(f"{view_date} {s['start_time']}", '%Y-%m-%d %H:%M')
            if now <= start_dt <= cutoff:
                diff = int((start_dt - now).total_seconds() / 60)
                reminders.append({
                    'id': s['id'],
                    'title': s['title'],
                    'start_time': s['start_time'][:5],
                    'end_time': s['end_time'][:5],
                    'category': s['category'],
                    'minutes_left': diff,
                })
        except ValueError:
            continue

    return jsonify({'reminders': reminders})


@app.route('/api/export')
def export_schedules():
    """Export jadwal dalam format JSON atau CSV."""
    fmt = request.args.get('format', 'json')
    export_date = request.args.get('date', '')

    db = get_db()

    if export_date:
        schedules = get_schedules_for_date(export_date)
    else:
        schedules = db.execute(
            'SELECT * FROM schedules ORDER BY date ASC, start_time ASC'
        ).fetchall()

    items = []
    for s in schedules:
        completed_dates = db.execute(
            'SELECT occurrence_date FROM schedule_completions '
            'WHERE schedule_id = ? AND is_completed = 1 ORDER BY occurrence_date',
            (s['id'],),
        ).fetchall()
        items.append({
            'title': s['title'],
            'description': s['description'],
            'date': s['date'],
            'start_time': s['start_time'],
            'end_time': s['end_time'],
            'category': s['category'],
            'priority': s['priority'],
            'is_completed': bool(s['is_completed']),
            'is_recurring': bool(s['is_recurring']),
            'recurring_days': s['recurring_days'],
            'completed_dates': (
                json.dumps([row['occurrence_date'] for row in completed_dates])
                if fmt == 'csv'
                else [row['occurrence_date'] for row in completed_dates]
            ),
        })

    if fmt == 'csv':
        output = io.StringIO()
        if items:
            writer = csv.DictWriter(output, fieldnames=items[0].keys())
            writer.writeheader()
            writer.writerows(items)

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename=jadwal_jabez_{export_date or "all"}.csv'
            }
        )

    # JSON format
    return Response(
        json.dumps({'schedules': items, 'exported_at': datetime.now().isoformat()},
                    indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment;filename=jadwal_jabez_{export_date or "all"}.json'
        }
    )


@app.route('/api/import', methods=['POST'])
def import_schedules():
    """Import jadwal dari file JSON."""
    if 'file' not in request.files:
        return jsonify({'error': 'File tidak ditemukan'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Nama file kosong'}), 400

    try:
        content = file.read().decode('utf-8')

        if file.filename.endswith('.json'):
            data = json.loads(content)
            items = data.get('schedules', [])
        elif file.filename.endswith('.csv'):
            reader = csv.DictReader(io.StringIO(content))
            items = list(reader)
        else:
            return jsonify({'error': 'Format file tidak didukung. Gunakan .json atau .csv'}), 400

        db = get_db()
        imported = 0
        max_order = db.execute(
            'SELECT COALESCE(MAX(sort_order), 0) as max_order FROM schedules'
        ).fetchone()['max_order']

        for item in items:
            title = item.get('title', '').strip()
            if not title:
                continue

            is_recurring = item.get('is_recurring', False)
            if isinstance(is_recurring, str):
                is_recurring = is_recurring.lower() in ('true', '1', 'yes')

            is_completed = item.get('is_completed', False)
            if isinstance(is_completed, str):
                is_completed = is_completed.lower() in ('true', '1', 'yes')

            max_order += 1
            db.execute('''
                INSERT INTO schedules
                    (title, description, date, start_time, end_time,
                     category, priority, is_completed, is_recurring, recurring_days, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                item.get('description', ''),
                item.get('date', date.today().strftime('%Y-%m-%d')),
                item.get('start_time', '08:00'),
                item.get('end_time', '09:00'),
                item.get('category', 'lainnya'),
                item.get('priority', 'sedang'),
                1 if is_completed else 0,
                1 if is_recurring else 0,
                item.get('recurring_days', ''),
                max_order,
            ))
            schedule_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            completed_dates = item.get('completed_dates', [])
            if isinstance(completed_dates, str):
                completed_dates = json.loads(completed_dates) if completed_dates else []
            if not isinstance(completed_dates, list):
                raise ValueError('completed_dates harus berupa daftar tanggal.')
            for completed_date in completed_dates:
                try:
                    parsed_completed_date = datetime.strptime(
                        completed_date, '%Y-%m-%d'
                    ).date()
                except (TypeError, ValueError) as e:
                    raise ValueError('Tanggal pada completed_dates tidak valid.') from e
                if parsed_completed_date.strftime('%Y-%m-%d') != completed_date:
                    raise ValueError('Tanggal pada completed_dates tidak valid.')
                db.execute('''
                    INSERT OR IGNORE INTO schedule_completions
                        (schedule_id, occurrence_date, is_completed)
                    VALUES (?, ?, 1)
                ''', (schedule_id, completed_date))
            imported += 1

        db.commit()
        return jsonify({'success': True, 'imported': imported})

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        return jsonify({'error': f'Gagal membaca file: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE CONTEXT (tersedia di semua template)
# ══════════════════════════════════════════════════════════════════════

@app.context_processor
def inject_global_data():
    """Menyuntikkan data global ke semua template."""
    return {
        'today': date.today().strftime('%Y-%m-%d'),
        'now': datetime.now(),
        'app_name': 'Jadwal Jabez',
        'tagline': 'Atur harimu. Selesaikan satu per satu. 🚀',
    }


# ══════════════════════════════════════════════════════════════════════
# JALANKAN APLIKASI
# ══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Inisialisasi database saat pertama kali dijalankan
    init_db()
    print("\n[*] Jadwal Jabez berjalan di http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
