"""Small separate SQLite store for user preferences; analytics data stays separate."""
from pathlib import Path
import sqlite3, json

def connect(path=None):
    path=Path(path or Path(__file__).parent/"bengaluru_bites_user.sqlite3")
    con=sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS favorites(name TEXT PRIMARY KEY, url TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS searches(id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS comparisons(id INTEGER PRIMARY KEY AUTOINCREMENT, restaurants TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value TEXT)""")
    con.commit()
    return con

def add_favorite(con,name,url):
    con.execute("INSERT OR REPLACE INTO favorites(name,url) VALUES (?,?)",(name,url)); con.commit()

def remove_favorite(con,name):
    con.execute("DELETE FROM favorites WHERE name=?",(name,)); con.commit()

def favorites(con): return con.execute("SELECT name,url,created_at FROM favorites ORDER BY created_at DESC").fetchall()
def add_search(con,q): con.execute("INSERT INTO searches(query) VALUES (?)",(q,)); con.commit()
def searches(con,limit=20): return con.execute("SELECT query,created_at FROM searches ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
def save_comparison(con,names): con.execute("INSERT INTO comparisons(restaurants) VALUES (?)",(json.dumps(list(names)),)); con.commit()
def comparisons(con,limit=20): return con.execute("SELECT restaurants,created_at FROM comparisons ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
