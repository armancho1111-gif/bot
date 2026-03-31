import sqlite3

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Таблица пользователей
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    requests INTEGER DEFAULT 0,
    paid INTEGER DEFAULT 0
)
""")

# Таблица истории
cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task TEXT,
    answer TEXT,
    mode TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Таблица кэша ответов
cursor.execute("""
CREATE TABLE IF NOT EXISTS cache (
    task TEXT PRIMARY KEY,
    answer TEXT,
    mode TEXT
)
""")
conn.commit()

# Пользователи
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def increment_requests(user_id):
    cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id=?", (user_id,))
    conn.commit()

def get_requests(user_id):
    cursor.execute("SELECT requests FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

def set_paid(user_id):
    cursor.execute("UPDATE users SET paid = 1 WHERE user_id=?", (user_id,))
    conn.commit()

def is_paid(user_id):
    cursor.execute("SELECT paid FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

# История
def add_history(user_id, task, answer, mode):
    cursor.execute(
        "INSERT INTO history (user_id, task, answer, mode) VALUES (?, ?, ?, ?)",
        (user_id, task, answer, mode)
    )
    conn.commit()

def get_history(user_id, limit=5):
    cursor.execute(
        "SELECT task, answer, mode, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    return cursor.fetchall()

# Кэш
def get_cached_answer(task, mode):
    cursor.execute("SELECT answer FROM cache WHERE task=? AND mode=?", (task, mode))
    result = cursor.fetchone()
    return result[0] if result else None

def set_cache(task, answer, mode):
    cursor.execute(
        "INSERT OR REPLACE INTO cache (task, answer, mode) VALUES (?, ?, ?)",
        (task, answer, mode)
    )
    conn.commit()