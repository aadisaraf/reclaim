import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS remit_files (
    sha256 TEXT PRIMARY KEY,
    file_name TEXT,
    received_at TEXT,
    status TEXT,
    reject_rule TEXT,
    claim_count INTEGER
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    hospital_claim_id TEXT UNIQUE,
    lane TEXT,
    status TEXT,
    payer_claim_id TEXT,
    payer TEXT,
    payer_id TEXT,
    member_id TEXT,
    rendering_npi TEXT,
    procedure_qualifier TEXT,
    procedure_code TEXT,
    date_of_service TEXT,
    denial_code TEXT,
    denial_reason TEXT,
    billed_amount REAL,
    paid_amount REAL,
    denied_amount REAL,
    remit_file TEXT,
    remit_sha256 TEXT,
    needs_review_field TEXT,
    last_error TEXT,
    running INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS step_outputs (
    case_id TEXT,
    step TEXT,
    output_json TEXT,
    created_at TEXT,
    PRIMARY KEY (case_id, step)
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    step TEXT,
    summary TEXT,
    detail_json TEXT,
    ehr_requests_json TEXT,
    llm_usage_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    case_id TEXT,
    task_type TEXT,
    requirement_id TEXT,
    assignee_role TEXT,
    question TEXT,
    status TEXT,
    close_note TEXT,
    created_at TEXT,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS packets (
    case_id TEXT,
    version INTEGER,
    status TEXT,
    content_sha256 TEXT,
    letter_json TEXT,
    blocked_reason TEXT,
    html TEXT,
    pdf BLOB,
    approved_by TEXT,
    approved_role TEXT,
    approved_at TEXT,
    PRIMARY KEY (case_id, version)
);
CREATE TABLE IF NOT EXISTS submissions (
    idempotency_key TEXT PRIMARY KEY,
    case_id TEXT,
    version INTEGER,
    request_sha256 TEXT,
    status TEXT,
    appeal_id TEXT,
    received_at TEXT,
    expected_resolution_days INTEGER,
    payer_status TEXT,
    error_code TEXT,
    error_message TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    case_id TEXT,
    document_type TEXT,
    content_type TEXT,
    bytes BLOB,
    sha256 TEXT,
    uploaded_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repo:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def insert_remit_file(self, sha256: str, file_name: str, status: str,
                           reject_rule: str | None, claim_count: int) -> bool:
        existing = self.conn.execute(
            "SELECT 1 FROM remit_files WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if existing:
            return False
        self.conn.execute(
            "INSERT INTO remit_files (sha256, file_name, received_at, status, reject_rule, claim_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sha256, file_name, _now(), status, reject_rule, claim_count),
        )
        self.conn.commit()
        return True

    def list_remit_files(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM remit_files ORDER BY received_at").fetchall()
        return [dict(r) for r in rows]

    def upsert_case(self, case_id: str, **fields) -> None:
        existing = self.conn.execute(
            "SELECT case_id FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        now = _now()
        if existing:
            cols = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(
                f"UPDATE cases SET {cols}, updated_at = ? WHERE case_id = ?",
                (*fields.values(), now, case_id),
            )
        else:
            fields.setdefault("hospital_claim_id", None)
            cols = ", ".join(["case_id", *fields.keys(), "created_at", "updated_at"])
            placeholders = ", ".join(["?"] * (len(fields) + 3))
            self.conn.execute(
                f"INSERT INTO cases ({cols}) VALUES ({placeholders})",
                (case_id, *fields.values(), now, now),
            )
        self.conn.commit()

    def get_case(self, case_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return dict(row) if row else None

    def get_case_by_hospital_claim_id(self, hospital_claim_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM cases WHERE hospital_claim_id = ?", (hospital_claim_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_cases(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM cases ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def update_case(self, case_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE cases SET {cols}, updated_at = ? WHERE case_id = ?",
            (*fields.values(), _now(), case_id),
        )
        self.conn.commit()

    def save_step_output(self, case_id: str, step: str, output_json: str) -> None:
        self.conn.execute(
            "INSERT INTO step_outputs (case_id, step, output_json, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(case_id, step) DO UPDATE SET output_json = excluded.output_json, "
            "created_at = excluded.created_at",
            (case_id, step, output_json, _now()),
        )
        self.conn.commit()

    def get_step_output(self, case_id: str, step: str) -> dict | None:
        row = self.conn.execute(
            "SELECT output_json FROM step_outputs WHERE case_id = ? AND step = ?", (case_id, step)
        ).fetchone()
        return json.loads(row["output_json"]) if row else None

    def insert_audit_event(self, case_id: str | None, step: str, summary: str,
                            detail: dict | None, ehr_requests: list[str] | None,
                            llm_usage: dict | None) -> None:
        self.conn.execute(
            "INSERT INTO audit_events (case_id, step, summary, detail_json, ehr_requests_json, "
            "llm_usage_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                case_id, step, summary,
                json.dumps(detail or {}),
                json.dumps(ehr_requests or []),
                json.dumps(llm_usage) if llm_usage else None,
                _now(),
            ),
        )
        self.conn.commit()

    def list_events(self, case_id: str | None) -> list[dict]:
        if case_id is None:
            rows = self.conn.execute(
                "SELECT * FROM audit_events WHERE case_id IS NULL ORDER BY id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM audit_events WHERE case_id = ? ORDER BY id", (case_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_task(self, task_id: str, **fields) -> None:
        existing = self.conn.execute(
            "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if existing:
            cols = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(
                f"UPDATE tasks SET {cols} WHERE task_id = ?", (*fields.values(), task_id)
            )
        else:
            cols = ", ".join(["task_id", *fields.keys(), "created_at"])
            placeholders = ", ".join(["?"] * (len(fields) + 2))
            self.conn.execute(
                f"INSERT INTO tasks ({cols}) VALUES ({placeholders})",
                (task_id, *fields.values(), _now()),
            )
        self.conn.commit()

    def close_task(self, task_id: str, close_note: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET status = 'closed', close_note = ?, closed_at = ? WHERE task_id = ?",
            (close_note, _now(), task_id),
        )
        self.conn.commit()

    def list_tasks(self, case_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE case_id = ? ORDER BY created_at", (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_packet(self, case_id: str, version: int, **fields) -> None:
        existing = self.conn.execute(
            "SELECT 1 FROM packets WHERE case_id = ? AND version = ?", (case_id, version)
        ).fetchone()
        if existing:
            cols = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(
                f"UPDATE packets SET {cols} WHERE case_id = ? AND version = ?",
                (*fields.values(), case_id, version),
            )
        else:
            cols = ", ".join(["case_id", "version", *fields.keys()])
            placeholders = ", ".join(["?"] * (len(fields) + 2))
            self.conn.execute(
                f"INSERT INTO packets ({cols}) VALUES ({placeholders})",
                (case_id, version, *fields.values()),
            )
        self.conn.commit()

    def get_packet(self, case_id: str, version: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM packets WHERE case_id = ? AND version = ?", (case_id, version)
        ).fetchone()
        return dict(row) if row else None

    def latest_packet(self, case_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM packets WHERE case_id = ? ORDER BY version DESC LIMIT 1", (case_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_document(self, document_id: str, case_id: str, document_type: str,
                       content_type: str, content: bytes, sha256: str,
                       uploaded_at: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO documents (document_id, case_id, document_type, content_type, bytes, "
            "sha256, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(document_id) DO UPDATE SET bytes = excluded.bytes, sha256 = excluded.sha256, "
            "uploaded_at = excluded.uploaded_at",
            (document_id, case_id, document_type, content_type, content, sha256, uploaded_at),
        )
        self.conn.commit()

    def mark_document_uploaded(self, document_id: str, uploaded_at: str) -> None:
        self.conn.execute(
            "UPDATE documents SET uploaded_at = ? WHERE document_id = ?", (uploaded_at, document_id)
        )
        self.conn.commit()

    def get_document(self, document_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_submission(self, idempotency_key: str, **fields) -> None:
        existing = self.conn.execute(
            "SELECT 1 FROM submissions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if existing:
            cols = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(
                f"UPDATE submissions SET {cols}, updated_at = ? WHERE idempotency_key = ?",
                (*fields.values(), _now(), idempotency_key),
            )
        else:
            cols = ", ".join(["idempotency_key", *fields.keys(), "updated_at"])
            placeholders = ", ".join(["?"] * (len(fields) + 2))
            self.conn.execute(
                f"INSERT INTO submissions ({cols}) VALUES ({placeholders})",
                (idempotency_key, *fields.values(), _now()),
            )
        self.conn.commit()

    def get_submission(self, idempotency_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM submissions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return dict(row) if row else None

    def reset_all(self) -> None:
        for table in [
            "remit_files", "cases", "step_outputs", "audit_events", "tasks",
            "packets", "submissions", "documents",
        ]:
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.commit()
