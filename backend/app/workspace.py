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


def save_execution(run_id, request_payload, result_payload, status, parent_run_id=None):
    """Persist a bounded, replayable research execution record."""
    request_json=json.dumps(request_payload,separators=(",",":"),allow_nan=False)
    result_json=json.dumps(result_payload,separators=(",",":"),allow_nan=False)
    now=datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
          id TEXT PRIMARY KEY, parent_run_id TEXT, status TEXT NOT NULL,
          request_json TEXT NOT NULL, result_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        con.execute("""INSERT INTO workflow_runs
          (id,parent_run_id,status,request_json,result_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?)""",
          (run_id,parent_run_id,status,request_json,result_json,now,now))
    return {"id":run_id,"parent_run_id":parent_run_id,"status":status,
            "created_at":now,"updated_at":now}


def list_executions(limit=50):
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
          id TEXT PRIMARY KEY, parent_run_id TEXT, status TEXT NOT NULL,
          request_json TEXT NOT NULL, result_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        rows=con.execute("""SELECT id,parent_run_id,status,created_at,updated_at
          FROM workflow_runs ORDER BY created_at DESC LIMIT ?""",
          (max(1,min(int(limit),100)),)).fetchall()
    return [dict(row) for row in rows]


def get_execution(run_id):
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
          id TEXT PRIMARY KEY, parent_run_id TEXT, status TEXT NOT NULL,
          request_json TEXT NOT NULL, result_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        row=con.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
    if row is None:
        return None
    record=dict(row)
    record["request"]=json.loads(record.pop("request_json"))
    record["result"]=json.loads(record.pop("result_json"))
    checkpoint_json=record.pop("checkpoint_json", "{}")
    try:
        checkpoint=json.loads(checkpoint_json)
    except (TypeError, json.JSONDecodeError):
        checkpoint={}
        record["checkpoint_error"]="Stored checkpoint is malformed; it cannot be used for recovery."
    if not isinstance(checkpoint, dict):
        checkpoint={}
        record["checkpoint_error"]="Stored checkpoint has an invalid format; it cannot be used for recovery."
    record["checkpoint"]=checkpoint
    return record


def update_execution_checkpoint(run_id, checkpoint, status="running", result_payload=None):
    """Atomically persist the latest completed-layer checkpoint."""
    checkpoint_json=json.dumps(checkpoint,separators=(",",":"),allow_nan=False)
    result_json=json.dumps(result_payload,separators=(",",":"),allow_nan=False) if result_payload is not None else None
    now=datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        columns={row["name"] for row in con.execute("PRAGMA table_info(workflow_runs)")}
        if "checkpoint_json" not in columns:
            con.execute("ALTER TABLE workflow_runs ADD COLUMN checkpoint_json TEXT NOT NULL DEFAULT '{}'")
        if result_json is None:
            con.execute("""UPDATE workflow_runs SET checkpoint_json=?,status=?,updated_at=? WHERE id=?""",
              (checkpoint_json,status,now,run_id))
        else:
            con.execute("""UPDATE workflow_runs SET checkpoint_json=?,result_json=?,status=?,updated_at=? WHERE id=?""",
              (checkpoint_json,result_json,status,now,run_id))
        if con.total_changes == 0:
            raise KeyError("Workflow run not found")
    return {"id":run_id,"status":status,"updated_at":now}


def create_execution(run_id, request_payload, parent_run_id=None):
    """Create the durable run record before any task begins."""
    request_json=json.dumps(request_payload,separators=(",",":"),allow_nan=False)
    now=datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
          id TEXT PRIMARY KEY, parent_run_id TEXT, status TEXT NOT NULL,
          request_json TEXT NOT NULL, result_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        columns={row["name"] for row in con.execute("PRAGMA table_info(workflow_runs)")}
        if "checkpoint_json" not in columns:
            con.execute("ALTER TABLE workflow_runs ADD COLUMN checkpoint_json TEXT NOT NULL DEFAULT '{}'")
        con.execute("""INSERT INTO workflow_runs
          (id,parent_run_id,status,request_json,result_json,checkpoint_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?)""",
          (run_id,parent_run_id,"running",request_json,"{}","{}",now,now))
    return {"id":run_id,"parent_run_id":parent_run_id,"status":"running","created_at":now,"updated_at":now}
