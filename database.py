import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create Submissions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_email TEXT NOT NULL,
            target_role TEXT,
            cv_text TEXT NOT NULL,
            analysis_result TEXT,
            score INTEGER,
            interview_completed BOOLEAN DEFAULT 0,
            interview_transcript TEXT,
            interview_score INTEGER,
            cheating_flags TEXT,
            video_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safely try to alter table if the columns don't exist (SQLite doesn't support IF NOT EXISTS in ALTER TABLE)
    try:
        c.execute("ALTER TABLE submissions ADD COLUMN interview_completed BOOLEAN DEFAULT 0")
        c.execute("ALTER TABLE submissions ADD COLUMN interview_transcript TEXT")
        c.execute("ALTER TABLE submissions ADD COLUMN interview_score INTEGER")
        c.execute("ALTER TABLE submissions ADD COLUMN cheating_flags TEXT")
        c.execute("ALTER TABLE submissions ADD COLUMN video_path TEXT")
    except sqlite3.OperationalError:
        try:
            # In case the table was partially altered before
            c.execute("ALTER TABLE submissions ADD COLUMN video_path TEXT")
        except sqlite3.OperationalError:
            pass # Everything exists

    conn.commit()
    conn.close()

def save_submission(email, role, cv_text, analysis, score):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO submissions (candidate_email, target_role, cv_text, analysis_result, score)
        VALUES (?, ?, ?, ?, ?)
    ''', (email, role, cv_text, analysis, score))
    submission_id = c.lastrowid
    conn.commit()
    conn.close()
    return submission_id

def update_interview(submission_id, transcript, score, cheating_flags, video_path=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE submissions 
        SET interview_completed = 1, interview_transcript = ?, interview_score = ?, cheating_flags = ?, video_path = ?
        WHERE id = ?
    ''', (transcript, score, cheating_flags, video_path, submission_id))
    conn.commit()
    conn.close()

def get_submission_by_id(submission_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM submissions WHERE id = ?', (submission_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_submissions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM submissions ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == '__main__':
    init_db()
