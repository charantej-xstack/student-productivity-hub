"""
database.py
-----------
Storage layer for the Student Productivity Hub (SQLite, no GUI code here).

Tables : users, tasks, notes, focus_sessions
Security: passwords are never stored as plain text. Each user gets a random
          salt and the password is hashed with PBKDF2-HMAC-SHA256.
"""

import hashlib
import secrets
import sqlite3
from datetime import date, datetime

DB_FILE = "productivity_hub.db"


class Database:
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                salt          TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL REFERENCES users(id),
                title    TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                due_date TEXT,
                done     INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS notes (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title   TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                day     TEXT NOT NULL,
                minutes INTEGER NOT NULL
            );
        """)
        self.conn.commit()

    # ------------------------------------------------------------------ users
    @staticmethod
    def _hash(password, salt_hex):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   bytes.fromhex(salt_hex), 100_000).hex()

    def register(self, username, password):
        """Create a user. Returns True, or False if the username is taken."""
        salt = secrets.token_hex(16)
        try:
            self.conn.execute(
                "INSERT INTO users (username, salt, password_hash) VALUES (?, ?, ?)",
                (username, salt, self._hash(password, salt)))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, username, password):
        """Returns the user id if the credentials are correct, else None."""
        row = self.conn.execute(
            "SELECT id, salt, password_hash FROM users WHERE username = ?",
            (username,)).fetchone()
        if row and secrets.compare_digest(self._hash(password, row["salt"]),
                                          row["password_hash"]):
            return row["id"]
        return None

    # ------------------------------------------------------------------ tasks
    def add_task(self, uid, title, priority, due):
        cur = self.conn.execute(
            "INSERT INTO tasks (user_id, title, priority, due_date) VALUES (?, ?, ?, ?)",
            (uid, title, priority, due or None))
        self.conn.commit()
        return cur.lastrowid

    def get_tasks(self, uid, status="All"):
        sql = "SELECT * FROM tasks WHERE user_id = ?"
        if status == "Pending":
            sql += " AND done = 0"
        elif status == "Done":
            sql += " AND done = 1"
        return self.conn.execute(sql, (uid,)).fetchall()

    def update_task(self, tid, title, priority, due):
        self.conn.execute(
            "UPDATE tasks SET title = ?, priority = ?, due_date = ? WHERE id = ?",
            (title, priority, due or None, tid))
        self.conn.commit()

    def set_done(self, tid, done):
        self.conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (int(done), tid))
        self.conn.commit()

    def delete_task(self, tid):
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
        self.conn.commit()

    def upcoming(self, uid, limit=5):
        return self.conn.execute(
            "SELECT title, due_date FROM tasks WHERE user_id = ? AND done = 0 "
            "AND due_date IS NOT NULL ORDER BY due_date LIMIT ?",
            (uid, limit)).fetchall()

    # ------------------------------------------------------------------ notes
    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def add_note(self, uid, title, content):
        cur = self.conn.execute(
            "INSERT INTO notes (user_id, title, content, updated) VALUES (?, ?, ?, ?)",
            (uid, title, content, self._now()))
        self.conn.commit()
        return cur.lastrowid

    def get_notes(self, uid, search=""):
        return self.conn.execute(
            "SELECT * FROM notes WHERE user_id = ? AND (title LIKE ? OR content LIKE ?) "
            "ORDER BY updated DESC", (uid, f"%{search}%", f"%{search}%")).fetchall()

    def update_note(self, nid, title, content):
        self.conn.execute(
            "UPDATE notes SET title = ?, content = ?, updated = ? WHERE id = ?",
            (title, content, self._now(), nid))
        self.conn.commit()

    def delete_note(self, nid):
        self.conn.execute("DELETE FROM notes WHERE id = ?", (nid,))
        self.conn.commit()

    # --------------------------------------------------------- focus sessions
    def log_session(self, uid, minutes):
        self.conn.execute(
            "INSERT INTO focus_sessions (user_id, day, minutes) VALUES (?, ?, ?)",
            (uid, date.today().isoformat(), minutes))
        self.conn.commit()

    def stats(self, uid):
        q = self.conn.execute
        total = q("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (uid,)).fetchone()[0]
        done = q("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND done = 1",
                 (uid,)).fetchone()[0]
        mins, count = q("SELECT COALESCE(SUM(minutes), 0), COUNT(*) FROM focus_sessions "
                        "WHERE user_id = ? AND day = ?",
                        (uid, date.today().isoformat())).fetchone()
        return {"total": total, "done": done, "pending": total - done,
                "focus_minutes_today": mins, "pomodoros_today": count}
