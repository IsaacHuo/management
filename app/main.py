from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.database import PROJECT_ROOT, get_connection, get_db_path, init_database
from app.security import create_token, hash_token, verify_password


SESSION_HOURS = 8
STATIC_DIR = PROJECT_ROOT / "app" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not get_db_path().exists():
        init_database(reset=False, seed=True)
    yield


app = FastAPI(title="Library Management System", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class LoginPayload(BaseModel):
    username: str
    password: str


class BookPayload(BaseModel):
    isbn: str
    title: str
    author: str
    publisher: str = ""
    category: str = ""
    published_year: Optional[int] = None
    total_count: int = 1
    available_count: Optional[int] = None
    location: str = ""
    status: str = "active"


class ReaderPayload(BaseModel):
    card_no: str
    name: str
    phone: str = ""
    email: str = ""
    department: str = ""
    status: str = "active"


class LoanPayload(BaseModel):
    book_id: int
    reader_id: int
    days: int = 30
    due_date: Optional[str] = None
    note: str = ""


class ReturnPayload(BaseModel):
    return_date: Optional[str] = None


def utc_now_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def today_text() -> str:
    return date.today().isoformat()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


def parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} 必须是 YYYY-MM-DD 格式")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


def require_admin(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    token = authorization.removeprefix("Bearer ").strip()
    token_digest = hash_token(token)
    now = utc_now_text()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT a.id, a.username, a.display_name, s.expires_at
            FROM sessions s
            JOIN admins a ON a.id = s.admin_id
            WHERE s.token_hash = ? AND s.expires_at > ?
            """,
            (token_digest, now),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
    return row_to_dict(row)


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> Dict[str, Any]:
    username = clean_text(payload.username)
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now_text(),))
        admin = conn.execute(
            "SELECT id, username, password_hash, display_name FROM admins WHERE username = ?",
            (username,),
        ).fetchone()
        if not admin or not verify_password(payload.password, admin["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_token()
        expires_at = (datetime.utcnow() + timedelta(hours=SESSION_HOURS)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO sessions (admin_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (admin["id"], hash_token(token), expires_at),
        )

    return {
        "token": token,
        "expires_at": expires_at,
        "admin": {
            "id": admin["id"],
            "username": admin["username"],
            "display_name": admin["display_name"],
        },
    }


@app.post("/api/auth/logout")
def logout(
    authorization: Optional[str] = Header(default=None),
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, str]:
    del admin
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        with get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    return {"message": "已退出登录"}


@app.get("/api/auth/me")
def me(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return {"admin": admin}


def validate_book_payload(payload: BookPayload, book_id: Optional[int] = None) -> Dict[str, Any]:
    isbn = clean_text(payload.isbn)
    title = clean_text(payload.title)
    author = clean_text(payload.author)
    if not isbn or not title or not author:
        raise HTTPException(status_code=400, detail="ISBN、书名和作者不能为空")
    if payload.status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="图书状态必须是 active 或 inactive")
    if payload.published_year is not None and (payload.published_year < 0 or payload.published_year > 2100):
        raise HTTPException(status_code=400, detail="出版年份不合法")
    if payload.total_count < 0:
        raise HTTPException(status_code=400, detail="馆藏数量不能小于 0")

    available_count = payload.total_count if payload.available_count is None else payload.available_count
    if available_count < 0 or available_count > payload.total_count:
        raise HTTPException(status_code=400, detail="可借数量必须在 0 到馆藏数量之间")

    if book_id is not None:
        with get_connection() as conn:
            borrowed = conn.execute(
                "SELECT COUNT(*) AS count FROM loans WHERE book_id = ? AND status = 'borrowed'",
                (book_id,),
            ).fetchone()["count"]
        if payload.total_count < borrowed:
            raise HTTPException(status_code=400, detail="馆藏数量不能小于当前未归还数量")
        if available_count > payload.total_count - borrowed:
            raise HTTPException(status_code=400, detail="可借数量不能超过扣除未归还后的库存")

    return {
        "isbn": isbn,
        "title": title,
        "author": author,
        "publisher": clean_text(payload.publisher),
        "category": clean_text(payload.category),
        "published_year": payload.published_year,
        "total_count": payload.total_count,
        "available_count": available_count,
        "location": clean_text(payload.location),
        "status": payload.status,
    }


@app.get("/api/books")
def list_books(
    q: str = "",
    status_filter: Optional[str] = Query(default=None, alias="status"),
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    del admin
    clauses = ["deleted_at IS NULL"]
    params: List[Any] = []
    search = clean_text(q)
    if search:
        clauses.append("(isbn LIKE ? OR title LIKE ? OR author LIKE ? OR category LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern])
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)

    sql = f"SELECT * FROM books WHERE {' AND '.join(clauses)} ORDER BY id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@app.post("/api/books", status_code=201)
def create_book(payload: BookPayload, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    data = validate_book_payload(payload)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books
                (isbn, title, author, publisher, category, published_year, total_count,
                 available_count, location, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["isbn"],
                    data["title"],
                    data["author"],
                    data["publisher"],
                    data["category"],
                    data["published_year"],
                    data["total_count"],
                    data["available_count"],
                    data["location"],
                    data["status"],
                ),
            )
            row = conn.execute("SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="ISBN 已存在")
    return {"item": row_to_dict(row)}


@app.put("/api/books/{book_id}")
def update_book(book_id: int, payload: BookPayload, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    data = validate_book_payload(payload, book_id=book_id)
    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM books WHERE id = ? AND deleted_at IS NULL",
                (book_id,),
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="图书不存在")
            conn.execute(
                """
                UPDATE books
                SET isbn = ?, title = ?, author = ?, publisher = ?, category = ?,
                    published_year = ?, total_count = ?, available_count = ?,
                    location = ?, status = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    data["isbn"],
                    data["title"],
                    data["author"],
                    data["publisher"],
                    data["category"],
                    data["published_year"],
                    data["total_count"],
                    data["available_count"],
                    data["location"],
                    data["status"],
                    book_id,
                ),
            )
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="ISBN 已存在")
    return {"item": row_to_dict(row)}


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, str]:
    del admin
    with get_connection() as conn:
        active_loans = conn.execute(
            "SELECT COUNT(*) AS count FROM loans WHERE book_id = ? AND status = 'borrowed'",
            (book_id,),
        ).fetchone()["count"]
        if active_loans:
            raise HTTPException(status_code=400, detail="图书存在未归还记录，不能删除")
        cursor = conn.execute(
            """
            UPDATE books
            SET status = 'inactive', deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND deleted_at IS NULL
            """,
            (book_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="图书不存在")
    return {"message": "图书已删除"}


def validate_reader_payload(payload: ReaderPayload) -> Dict[str, str]:
    card_no = clean_text(payload.card_no)
    name = clean_text(payload.name)
    if not card_no or not name:
        raise HTTPException(status_code=400, detail="借书证号和姓名不能为空")
    if payload.status not in {"active", "suspended"}:
        raise HTTPException(status_code=400, detail="读者状态必须是 active 或 suspended")
    return {
        "card_no": card_no,
        "name": name,
        "phone": clean_text(payload.phone),
        "email": clean_text(payload.email),
        "department": clean_text(payload.department),
        "status": payload.status,
    }


@app.get("/api/readers")
def list_readers(
    q: str = "",
    status_filter: Optional[str] = Query(default=None, alias="status"),
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    del admin
    clauses = ["deleted_at IS NULL"]
    params: List[Any] = []
    search = clean_text(q)
    if search:
        clauses.append("(card_no LIKE ? OR name LIKE ? OR phone LIKE ? OR department LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern])
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)

    sql = f"SELECT * FROM readers WHERE {' AND '.join(clauses)} ORDER BY id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@app.post("/api/readers", status_code=201)
def create_reader(payload: ReaderPayload, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    data = validate_reader_payload(payload)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO readers (card_no, name, phone, email, department, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (data["card_no"], data["name"], data["phone"], data["email"], data["department"], data["status"]),
            )
            row = conn.execute("SELECT * FROM readers WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="借书证号已存在")
    return {"item": row_to_dict(row)}


@app.put("/api/readers/{reader_id}")
def update_reader(reader_id: int, payload: ReaderPayload, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    data = validate_reader_payload(payload)
    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM readers WHERE id = ? AND deleted_at IS NULL",
                (reader_id,),
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="读者不存在")
            conn.execute(
                """
                UPDATE readers
                SET card_no = ?, name = ?, phone = ?, email = ?, department = ?,
                    status = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    data["card_no"],
                    data["name"],
                    data["phone"],
                    data["email"],
                    data["department"],
                    data["status"],
                    reader_id,
                ),
            )
            row = conn.execute("SELECT * FROM readers WHERE id = ?", (reader_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="借书证号已存在")
    return {"item": row_to_dict(row)}


@app.delete("/api/readers/{reader_id}")
def delete_reader(reader_id: int, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, str]:
    del admin
    with get_connection() as conn:
        active_loans = conn.execute(
            "SELECT COUNT(*) AS count FROM loans WHERE reader_id = ? AND status = 'borrowed'",
            (reader_id,),
        ).fetchone()["count"]
        if active_loans:
            raise HTTPException(status_code=400, detail="读者存在未归还记录，不能删除")
        cursor = conn.execute(
            """
            UPDATE readers
            SET status = 'suspended', deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND deleted_at IS NULL
            """,
            (reader_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="读者不存在")
    return {"message": "读者已删除"}


def loan_select_sql() -> str:
    return """
        SELECT
            l.*,
            b.title AS book_title,
            b.isbn AS book_isbn,
            r.name AS reader_name,
            r.card_no AS reader_card_no,
            CASE
                WHEN l.status = 'borrowed' AND l.due_date < date('now') THEN 'overdue'
                ELSE l.status
            END AS loan_status
        FROM loans l
        JOIN books b ON b.id = l.book_id
        JOIN readers r ON r.id = l.reader_id
    """


@app.get("/api/loans")
def list_loans(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    reader_id: Optional[int] = None,
    book_id: Optional[int] = None,
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    del admin
    clauses: List[str] = []
    params: List[Any] = []
    if status_filter == "overdue":
        clauses.append("l.status = 'borrowed' AND l.due_date < date('now')")
    elif status_filter == "borrowed":
        clauses.append("l.status = 'borrowed'")
    elif status_filter == "returned":
        clauses.append("l.status = 'returned'")
    elif status_filter:
        raise HTTPException(status_code=400, detail="借阅状态参数不合法")
    if reader_id is not None:
        clauses.append("l.reader_id = ?")
        params.append(reader_id)
    if book_id is not None:
        clauses.append("l.book_id = ?")
        params.append(book_id)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = loan_select_sql() + where + " ORDER BY l.id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@app.get("/api/loans/overdue")
def overdue_loans(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    sql = loan_select_sql() + " WHERE l.status = 'borrowed' AND l.due_date < date('now') ORDER BY l.due_date ASC"
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@app.post("/api/loans", status_code=201)
def create_loan(payload: LoanPayload, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    if payload.days <= 0 or payload.days > 365:
        raise HTTPException(status_code=400, detail="借阅天数必须在 1 到 365 之间")
    loan_date = date.today()
    due = parse_date(payload.due_date, "到期日期") if payload.due_date else loan_date + timedelta(days=payload.days)
    if due < loan_date:
        raise HTTPException(status_code=400, detail="到期日期不能早于借出日期")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        reader = conn.execute(
            "SELECT * FROM readers WHERE id = ? AND deleted_at IS NULL",
            (payload.reader_id,),
        ).fetchone()
        if not reader:
            raise HTTPException(status_code=404, detail="读者不存在")
        if reader["status"] != "active":
            raise HTTPException(status_code=400, detail="读者状态不是 active，不能借书")

        book = conn.execute(
            "SELECT * FROM books WHERE id = ? AND deleted_at IS NULL",
            (payload.book_id,),
        ).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="图书不存在")
        if book["status"] != "active":
            raise HTTPException(status_code=400, detail="图书状态不是 active，不能借出")
        if book["available_count"] <= 0:
            raise HTTPException(status_code=400, detail="图书暂无可借库存")

        cursor = conn.execute(
            """
            INSERT INTO loans (book_id, reader_id, loan_date, due_date, status, note)
            VALUES (?, ?, ?, ?, 'borrowed', ?)
            """,
            (payload.book_id, payload.reader_id, loan_date.isoformat(), due.isoformat(), clean_text(payload.note)),
        )
        conn.execute(
            """
            UPDATE books
            SET available_count = available_count - 1, updated_at = datetime('now')
            WHERE id = ?
            """,
            (payload.book_id,),
        )
        row = conn.execute(loan_select_sql() + " WHERE l.id = ?", (cursor.lastrowid,)).fetchone()
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"item": row_to_dict(row)}


@app.post("/api/loans/{loan_id}/return")
def return_loan(
    loan_id: int,
    payload: ReturnPayload = ReturnPayload(),
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    del admin
    return_date = parse_date(payload.return_date, "归还日期") if payload.return_date else date.today()

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
        if not loan:
            raise HTTPException(status_code=404, detail="借阅记录不存在")
        if loan["status"] == "returned":
            raise HTTPException(status_code=400, detail="该借阅记录已归还")
        if return_date < parse_date(loan["loan_date"], "借出日期"):
            raise HTTPException(status_code=400, detail="归还日期不能早于借出日期")

        conn.execute(
            """
            UPDATE loans
            SET status = 'returned', return_date = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (return_date.isoformat(), loan_id),
        )
        conn.execute(
            """
            UPDATE books
            SET available_count = CASE
                    WHEN available_count < total_count THEN available_count + 1
                    ELSE available_count
                END,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (loan["book_id"],),
        )
        row = conn.execute(loan_select_sql() + " WHERE l.id = ?", (loan_id,)).fetchone()
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"item": row_to_dict(row)}


@app.get("/api/dashboard/stats")
def dashboard_stats(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    del admin
    with get_connection() as conn:
        books = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(available_count), 0) AS available FROM books WHERE deleted_at IS NULL"
        ).fetchone()
        readers = conn.execute(
            "SELECT COUNT(*) AS total FROM readers WHERE deleted_at IS NULL AND status = 'active'"
        ).fetchone()
        borrowed = conn.execute(
            "SELECT COUNT(*) AS total FROM loans WHERE status = 'borrowed'"
        ).fetchone()
        overdue = conn.execute(
            "SELECT COUNT(*) AS total FROM loans WHERE status = 'borrowed' AND due_date < date('now')"
        ).fetchone()
    return {
        "books": books["total"],
        "available_books": books["available"],
        "active_readers": readers["total"],
        "borrowed_loans": borrowed["total"],
        "overdue_loans": overdue["total"],
    }
