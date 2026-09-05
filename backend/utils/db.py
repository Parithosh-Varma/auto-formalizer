from __future__ import annotations
import sqlite3, json, os, threading

_lock = threading.Lock()
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./jobs.db").replace("sqlite:///", "")

def _conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _lock:
        c = _conn()
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, problem TEXT, reference_proof TEXT, context TEXT,
          model TEXT, status TEXT, max_iterations INTEGER, compiled INTEGER,
          final_code TEXT, iterations INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS iterations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, n INTEGER,
          code TEXT, stdout TEXT, stderr TEXT, errors TEXT, reward REAL,
          duration REAL, summary TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, type TEXT, data TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.commit(); c.close()

def save_job(j: dict):
    with _lock:
        c = _conn()
        c.execute("""INSERT OR REPLACE INTO jobs(id,problem,reference_proof,context,model,status,max_iterations,compiled,final_code,iterations)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (j["id"], j.get("problem",""), j.get("reference_proof",""), j.get("context",""),
           j.get("model",""), j.get("status",""), j.get("max_iterations",8),
           1 if j.get("compiled") else 0, j.get("final_code",""), j.get("iterations",0)))
        c.commit(); c.close()

def save_iteration(job_id: str, it: dict):
    with _lock:
        c = _conn()
        c.execute("INSERT INTO iterations(job_id,n,code,stdout,stderr,errors,reward,duration,summary) VALUES(?,?,?,?,?,?,?,?,?)",
          (job_id, it.get("n",0), it.get("code",""), it.get("stdout","")[-4000:], it.get("stderr","")[-4000:],
           json.dumps(it.get("errors",[])), it.get("reward",0), it.get("duration",0), it.get("summary","")))
        c.commit(); c.close()

def push_event(job_id: str, typ: str, data: dict):
    with _lock:
        c = _conn()
        c.execute("INSERT INTO events(job_id,type,data) VALUES(?,?,?)", (job_id, typ, json.dumps(data)))
        c.commit(); c.close()

def get_events(job_id: str, after_id: int = 0):
    c = _conn()
    rows = c.execute("SELECT id,type,data FROM events WHERE job_id=? AND id>? ORDER BY id", (job_id, after_id)).fetchall()
    c.close()
    return [{"id": r["id"], "type": r["type"], "data": json.loads(r["data"])} for r in rows]

def get_iterations(job_id: str):
    c = _conn()
    rows = c.execute("SELECT n,code,stdout,stderr,errors,reward,duration,summary FROM iterations WHERE job_id=? ORDER BY n", (job_id,)).fetchall()
    c.close()
    out = []
    for r in rows:
        out.append({"n": r["n"], "code": r["code"], "stdout": r["stdout"], "stderr": r["stderr"],
                    "errors": json.loads(r["errors"] or "[]"), "reward": r["reward"], "duration": r["duration"], "summary": r["summary"]})
    return out
