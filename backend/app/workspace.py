"""SQLite persistence for named visual research workflows."""
import json, os, sqlite3, uuid
from pathlib import Path
from datetime import datetime, timezone

def _db_path():
    path=Path(os.getenv("MARKET_MIND_DB","./data/market_mind.db"))
    path.parent.mkdir(parents=True,exist_ok=True)
    return path

def _connect():
    con=sqlite3.connect(_db_path(),timeout=10)
    con.row_factory=sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS workflows (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      graph_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    return con

def save_workflow(title, description, nodes, edges, workflow_id=None):
    if len(nodes)>250 or len(edges)>1000:
        raise ValueError("Workflow exceeds the 250-node or 1000-edge limit.")
    payload=json.dumps({"nodes":nodes,"edges":edges},separators=(",",":"),allow_nan=False)
    now=datetime.now(timezone.utc).isoformat()
    wid=workflow_id or str(uuid.uuid4())
    with _connect() as con:
        exists=con.execute("SELECT id,created_at FROM workflows WHERE id=?",(wid,)).fetchone()
        if exists:
            con.execute("UPDATE workflows SET title=?,description=?,graph_json=?,updated_at=? WHERE id=?",
              (title,description,payload,now,wid))
            created=exists["created_at"]
        else:
            con.execute("INSERT INTO workflows VALUES (?,?,?,?,?,?)",
              (wid,title,description,payload,now,now))
            created=now
    return {"id":wid,"title":title,"description":description,"created_at":created,"updated_at":now}

def list_workflows(limit=50):
    with _connect() as con:
        rows=con.execute("SELECT id,title,description,created_at,updated_at FROM workflows ORDER BY updated_at DESC LIMIT ?",
          (max(1,min(int(limit),100)),)).fetchall()
    return [dict(row) for row in rows]

def get_workflow(workflow_id):
    with _connect() as con:
        row=con.execute("SELECT * FROM workflows WHERE id=?",(workflow_id,)).fetchone()
    if row is None: return None
    result=dict(row); graph=json.loads(result.pop("graph_json"))
    return {**result,**graph}

def delete_workflow(workflow_id):
    with _connect() as con:
        cur=con.execute("DELETE FROM workflows WHERE id=?",(workflow_id,))
        return cur.rowcount>0
