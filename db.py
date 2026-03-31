import sqlite3
import logging
from contextlib import contextmanager

# Подключение к базе данных с проверкой
def get_db_connection():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация базы данных
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        requests INTEGER DEFAULT 0,
        paid INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
        task TEXT,
        mode TEXT,
        answer TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (task, mode)
    )
    """)
    
    # Индексы для ускорения запросов
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_task_mode ON cache(task, mode)")
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully")

# Инициализируем базу при импорте
init_db()

@contextmanager
def db_transaction():
    """Контекстный менеджер для транзакций"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Пользователи
def get_user(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return cursor.fetchone()

def add_user(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        if cursor.rowcount == 0:
            logging.info(f"User {user_id} already exists")
        else:
            logging.info(f"New user added: {user_id}")

def increment_requests(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id=?", (user_id,))
        logging.info(f"Incremented requests for user {user_id}")

def get_requests(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT requests FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

def set_paid(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET paid = 1 WHERE user_id=?", (user_id,))
        logging.info(f"Set paid status for user {user_id}")

def is_paid(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT paid FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

# История
def add_history(user_id, task, answer, mode):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO history (user_id, task, answer, mode) VALUES (?, ?, ?, ?)",
            (user_id, task, answer, mode)
        )
        logging.info(f"Added history for user {user_id}")

def get_history(user_id, limit=5):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task, answer, mode, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        return cursor.fetchall()

def get_all_history(user_id):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task, answer, mode, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC",
            (user_id,)
        )
        return cursor.fetchall()

# Кэш
def get_cached_answer(task, mode):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT answer FROM cache WHERE task=? AND mode=?", (task, mode))
        result = cursor.fetchone()
        return result[0] if result else None

def set_cache(task, answer, mode):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO cache (task, mode, answer) VALUES (?, ?, ?)",
            (task, mode, answer)
        )
        logging.info(f"Cached answer for task: {task[:50]}...")

def clear_old_cache(days=30):
    """Очистка старого кэша"""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM cache WHERE created_at < datetime('now', '-' || ? || ' days')",
            (days,)
        )
        deleted = cursor.rowcount
        logging.info(f"Cleared {deleted} old cache entries")
        return deleted