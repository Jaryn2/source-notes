import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from .auth import router, session
from .db import connect, initialize
from .retrieval import import_document
from .answers import answer_question
from .evaluation import evaluate
from .provider import configured


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


app = FastAPI(title="Source Notes", lifespan=lifespan)
app.include_router(router, prefix="/api")


class Document(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=20, max_length=100000)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=600)
    key: uuid.UUID
    mode: str = Field(default="local", pattern="^(local|api)$")


class Note(BaseModel):
    answer_id: uuid.UUID
    title: str = Field(min_length=1, max_length=120)


class Review(BaseModel):
    approve: bool


class Evaluation(BaseModel):
    threshold: float = Field(default=0.16, ge=0.05, le=0.8)


@app.get("/api/health")
def health():
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/dashboard", dependencies=[Depends(session)])
def dashboard():
    with connect() as db:
        documents = db.execute("SELECT d.id,d.title,d.created_at,count(c.id) AS chunks,count(c.id) FILTER(WHERE c.flagged) AS flagged FROM documents d LEFT JOIN chunks c ON d.id=c.document_id GROUP BY d.id ORDER BY d.created_at").fetchall()
        answers = db.execute("SELECT * FROM answers ORDER BY created_at DESC LIMIT 30").fetchall()
        notes = db.execute("SELECT n.*,a.answer,a.citations FROM notes n JOIN answers a ON a.id=n.answer_id ORDER BY n.created_at DESC LIMIT 100").fetchall()
        evaluations = db.execute("SELECT * FROM evaluations ORDER BY created_at DESC LIMIT 10").fetchall()
    return {"documents": documents, "answers": answers, "notes": notes, "evaluations": evaluations, "api_available": configured()}


@app.post("/api/documents", dependencies=[Depends(session)])
def upload(body: Document):
    if not body.text.strip() or not body.title.strip():
        raise HTTPException(422, "Add a title and document text.")
    return import_document(body.title.strip(), body.text)


@app.post("/api/samples", dependencies=[Depends(session)])
def samples():
    return [import_document(path.stem.replace("-", " ").title(), path.read_text()) for path in sorted(Path("samples").glob("*.md"))]


@app.get("/api/documents/{document_id}", dependencies=[Depends(session)])
def document(document_id: uuid.UUID):
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id=%s", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found.")
        row["passages"] = db.execute("SELECT id,passage,start_line,end_line,flagged FROM chunks WHERE document_id=%s ORDER BY id", (document_id,)).fetchall()
        return row


@app.post("/api/questions", dependencies=[Depends(session)])
def ask(body: Question):
    if body.mode == "api" and not configured():
        raise HTTPException(409, "The optional API connection has not been set up.")
    return answer_question(body.question.strip(), body.key, body.mode)


@app.post("/api/notes", dependencies=[Depends(session)])
def propose(body: Note):
    with connect() as db:
        answer = db.execute("SELECT * FROM answers WHERE id=%s", (body.answer_id,)).fetchone()
        if not answer or answer["status"] != "answered":
            raise HTTPException(409, "Only an answer with verified source quotes can be sent for review.")
        row = db.execute("INSERT INTO notes(id,answer_id,title) VALUES (%s,%s,%s) ON CONFLICT(answer_id) DO NOTHING RETURNING id",
                         (uuid.uuid4(), body.answer_id, body.title.strip())).fetchone()
        if not row:
            row = db.execute("SELECT id FROM notes WHERE answer_id=%s", (body.answer_id,)).fetchone()
    return row


@app.post("/api/notes/{note_id}/review", dependencies=[Depends(session)])
def review(note_id: uuid.UUID, body: Review):
    with connect() as db:
        row = db.execute("UPDATE notes SET status=%s,reviewed_by='demo',reviewed_at=now() WHERE id=%s AND status='pending' RETURNING id",
                         ("approved" if body.approve else "rejected", note_id)).fetchone()
    if not row:
        raise HTTPException(409, "This note is missing or has already been reviewed.")
    return row


@app.post("/api/evaluations", dependencies=[Depends(session)])
def evaluations(body: Evaluation):
    cases = evaluate(body.threshold)
    with connect() as db:
        return db.execute("INSERT INTO evaluations(id,mode,cases,passed,total) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                          (uuid.uuid4(), f"local; threshold={body.threshold}", Jsonb(cases), sum(c["passed"] for c in cases), len(cases))).fetchone()


if Path("web/dist").exists():
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="web")
