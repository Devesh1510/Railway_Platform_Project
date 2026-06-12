"""
database.py
-----------
SQLite database for Pune Station Controller.
Stores all trains from MASTER_TIMETABLE with live allocation data.

Table: trains
  - train_number      TEXT PRIMARY KEY
  - name              TEXT
  - type              TEXT   (Through / Terminating / Originating)
  - route             TEXT   (Solapur / Mumbai / Miraj)
  - scheduled_arrival TEXT   (HH:MM from timetable)
  - predicted_delay   INTEGER (minutes, from ML model)
  - platform_assigned INTEGER (1-6, from allocator)
  - departure_time    TEXT   (HH:MM, computed end time)
  - status            TEXT   (ON TIME / DELAYED / CROSSOVER etc.)
  - zone              TEXT   (Miraj / Solapur, derived from platform)
  - last_updated      TEXT   (ISO timestamp of last allocation run)
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'station.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(master_timetable):
    """
    Create the trains table if it doesn't exist and seed it with
    every train from MASTER_TIMETABLE. Existing rows are preserved;
    only missing trains are inserted.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS trains (
            train_number      TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL,
            route             TEXT NOT NULL,
            scheduled_arrival TEXT NOT NULL,
            predicted_delay   INTEGER DEFAULT 0,
            platform_assigned INTEGER DEFAULT NULL,
            departure_time    TEXT DEFAULT NULL,
            status            TEXT DEFAULT 'PENDING',
            zone              TEXT DEFAULT NULL,
            last_updated      TEXT DEFAULT NULL
        )
    ''')

    for t in master_timetable:
        cur.execute('''
            INSERT OR IGNORE INTO trains
                (train_number, name, type, route, scheduled_arrival)
            VALUES (?, ?, ?, ?, ?)
        ''', (t['number'], t['name'], t['type'], t['route'], t['time']))

    conn.commit()
    conn.close()
    print(f"[DB] Initialised — {DB_PATH}")


PLATFORM_ZONE = {1: 'Miraj', 2: 'Miraj', 3: 'Miraj',
                 4: 'Solapur', 5: 'Solapur', 6: 'Solapur'}


def update_train_record(train_no, name, train_type, route, scheduled_arrival,
                        predicted_delay, platform_assigned,
                        departure_time, status):
    """
    Upsert a single train record after allocation runs.
    Called from run_allocation for every train in the active schedule.
    """
    zone = PLATFORM_ZONE.get(platform_assigned)
    now  = datetime.now().isoformat(timespec='seconds')

    conn = get_connection()
    conn.execute('''
        INSERT INTO trains
            (train_number, name, type, route, scheduled_arrival,
             predicted_delay, platform_assigned, departure_time,
             status, zone, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(train_number) DO UPDATE SET
            name              = excluded.name,
            type              = excluded.type,
            route             = excluded.route,
            scheduled_arrival = excluded.scheduled_arrival,
            predicted_delay   = excluded.predicted_delay,
            platform_assigned = excluded.platform_assigned,
            departure_time    = excluded.departure_time,
            status            = excluded.status,
            zone              = excluded.zone,
            last_updated      = excluded.last_updated
    ''', (train_no, name, train_type, route, scheduled_arrival,
          predicted_delay, platform_assigned, departure_time,
          status, zone, now))
    conn.commit()
    conn.close()


def get_all_trains():
    """Return all rows as a list of dicts, ordered by scheduled_arrival."""
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM trains ORDER BY scheduled_arrival'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
