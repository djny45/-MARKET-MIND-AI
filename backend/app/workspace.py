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
    try:
        record["request"]=json.loads(record.pop("request_json"))
        if not isinstance(record["request"], dict):
            raise ValueError("Stored request has an invalid format.")
    except (TypeError, ValueError, json.JSONDecodeError):
        record["request"]={}
        record["request_error"]="Stored workflow request is malformed; it cannot be replayed."
    try:
        record["result"]=json.loads(record.pop("result_json"))
        if not isinstance(record["result"], dict):
            raise ValueError("Stored result has an invalid format.")
    except (TypeError, ValueError, json.JSONDecodeError):
        record["result"]={}
        record["result_error"]="Stored workflow result is malformed."
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


def save_synthesis_review(review):
    """Append a human review record with a SHA-256 integrity digest."""
    import hashlib
    review_json=json.dumps(review,separators=(",",":"),sort_keys=True,allow_nan=False)
    review_id=str(uuid.uuid4())
    digest=hashlib.sha256(review_json.encode("utf-8")).hexdigest()
    now=datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS synthesis_reviews (
          id TEXT PRIMARY KEY, status TEXT NOT NULL, reviewer_claim TEXT NOT NULL,
          review_json TEXT NOT NULL, created_at TEXT NOT NULL,
          review_sha256 TEXT NOT NULL DEFAULT ''
        )""")
        columns={row["name"] for row in con.execute("PRAGMA table_info(synthesis_reviews)")}
        if "review_sha256" not in columns:
            con.execute("ALTER TABLE synthesis_reviews ADD COLUMN review_sha256 TEXT NOT NULL DEFAULT ''")
        con.execute("""INSERT INTO synthesis_reviews
          (id,status,reviewer_claim,review_json,created_at,review_sha256) VALUES (?,?,?,?,?,?)""",
          (review_id,review.get("status","unknown"),review.get("reviewer",""),review_json,now,digest))
    return {"review_id":review_id,**review,"review_persistence":"append_only_record",
            "integrity":{"algorithm":"sha256","digest":digest,"verified":True}}

def get_synthesis_review(review_id):
    """Retrieve one immutable review record and verify its stored digest."""
    import hashlib
    with _connect() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='synthesis_reviews'").fetchone()
        if exists is None:
            return None
        columns={row["name"] for row in con.execute("PRAGMA table_info(synthesis_reviews)")}
        if "review_sha256" not in columns:
            con.execute("ALTER TABLE synthesis_reviews ADD COLUMN review_sha256 TEXT NOT NULL DEFAULT ''")
        row=con.execute("SELECT id,review_json,review_sha256,created_at FROM synthesis_reviews WHERE id=?",
                        (review_id,)).fetchone()
    if row is None:
        return None
    actual=hashlib.sha256(row["review_json"].encode("utf-8")).hexdigest()
    try:
        review=json.loads(row["review_json"])
    except json.JSONDecodeError as exc:
        raise ValueError("stored review JSON is invalid") from exc
    if not isinstance(review,dict):
        raise ValueError("stored review must be an object")
    expected=row["review_sha256"]
    return {"review_id":row["id"],**review,"created_at":row["created_at"],
            "integrity":{"algorithm":"sha256","verified":bool(expected) and actual==expected,
                         "reason":"verified" if expected and actual==expected else "digest_missing_or_mismatch"}}

def list_synthesis_reviews(limit=50, status=None, reviewer=None):
    """List review metadata with optional exact status/reviewer-label filters.

    Reviewer values are user-supplied labels, not authenticated identities.
    Full draft/evidence remains available only through get_synthesis_review.
    """
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100:
        raise ValueError("limit must be an integer between 1 and 100")
    if status is not None:
        if not isinstance(status,str) or not status.strip() or len(status)>64:
            raise ValueError("status must be a non-empty string of at most 64 characters")
        status=status.strip()
    if reviewer is not None:
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>128:
            raise ValueError("reviewer must be a non-empty string of at most 128 characters")
        reviewer=reviewer.strip()
    clauses=[]
    params=[]
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if reviewer is not None:
        clauses.append("reviewer_claim = ?")
        params.append(reviewer)
    where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
    with _connect() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='synthesis_reviews'").fetchone()
        if exists is None:
            return []
        columns={row["name"] for row in con.execute("PRAGMA table_info(synthesis_reviews)")}
        if "review_sha256" not in columns:
            con.execute("ALTER TABLE synthesis_reviews ADD COLUMN review_sha256 TEXT NOT NULL DEFAULT ''")
        rows=con.execute("""SELECT id,status,reviewer_claim,created_at,review_sha256
          FROM synthesis_reviews"""+where+""" ORDER BY created_at DESC LIMIT ?""",
          (*params,limit)).fetchall()
    return [{"review_id":row["id"],"status":row["status"],"reviewer_claim":row["reviewer_claim"],
             "created_at":row["created_at"],
             "integrity":{"algorithm":"sha256","digest_present":bool(row["review_sha256"])}} for row in rows]


def synthesis_review_summary(status=None, reviewer=None):
    """Return metadata-only review counts, optionally scoped to exact filters."""
    # Reuse filter validation and SQL parameter handling without returning draft data.
    if status is not None:
        if not isinstance(status,str) or not status.strip() or len(status)>64:
            raise ValueError("status must be a non-empty string of at most 64 characters")
        status=status.strip()
    if reviewer is not None:
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>128:
            raise ValueError("reviewer must be a non-empty string of at most 128 characters")
        reviewer=reviewer.strip()
    clauses=[]
    params=[]
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if reviewer is not None:
        clauses.append("reviewer_claim = ?")
        params.append(reviewer)
    where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
    with _connect() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='synthesis_reviews'").fetchone()
        if exists is None:
            return {"total":0,"by_status":{}}
        rows=con.execute("SELECT status, COUNT(*) AS count FROM synthesis_reviews"+where+
                         " GROUP BY status ORDER BY status",params).fetchall()
    counts={row["status"]:row["count"] for row in rows}
    return {"total":sum(counts.values()),"by_status":counts}
