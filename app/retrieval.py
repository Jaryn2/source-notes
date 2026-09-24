import hashlib
import math
import re
import uuid
from .db import connect

STOP = set("a an and are as at be been by can could do does for from has have how i in is it me of on or our should that the their them there these they this to was we what when where which who why will with would you your tell please".split())
ALIASES = {"approves": "approve", "approval": "approve", "approved": "approve", "adjustments": "adjustment", "boxes": "box", "orders": "order", "damaged": "damage", "damages": "damage", "missing": "short", "shortage": "short", "duplicates": "duplicate", "readings": "reading", "retry": "retries"}
INJECTION = re.compile(r"ignore.{0,50}(instruction|previous|above)|system\s*prompt|developer\s*message|reveal.{0,30}(secret|key|password)|bypass.{0,30}(review|approval)|<\|im_start\|>", re.I | re.S)


def tokens(text):
    return {ALIASES.get(word, word) for word in re.findall(r"[a-z0-9_]+", text.lower()) if word not in STOP and len(word) > 1}


def vector(text):
    # A small word vector keeps the local demo free and repeatable.
    # It matches words, not meaning. The guide explains that limit.
    values = [0.0] * 256
    for word in tokens(text):
        digest = hashlib.sha256(word.encode()).digest()
        values[int.from_bytes(digest[:2], "big") % 256] += 1 if digest[2] % 2 else -1
    norm = math.sqrt(sum(value * value for value in values)) or 1
    return "[" + ",".join(str(round(value / norm, 7)) for value in values) + "]"


def split_passages(text):
    lines = text.splitlines()
    buffer, first = [], 1
    for line_number, line in enumerate(lines, 1):
        if not line.strip() or sum(len(part) for part in buffer) + len(line) > 1800:
            if buffer:
                yield "\n".join(buffer), first, line_number - 1
                buffer = []
        if line.strip():
            if not buffer:
                first = line_number
            # Long lines are split below so retrieval cannot swallow a whole file.
            if len(line) > 1800:
                for offset in range(0, len(line), 1800):
                    yield line[offset:offset + 1800], line_number, line_number
            else:
                buffer.append(line)
    if buffer:
        yield "\n".join(buffer), first, len(lines)


def import_document(title, body):
    digest = hashlib.sha256(body.encode()).hexdigest()
    with connect() as db:
        row = db.execute("INSERT INTO documents(id,title,body,digest) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
                         (uuid.uuid4(), title, body, digest)).fetchone()
        if not row:
            return {"id": str(db.execute("SELECT id FROM documents WHERE digest=%s", (digest,)).fetchone()["id"]), "reused": True}
        for passage, first, last in split_passages(body):
            db.execute("INSERT INTO chunks(document_id,passage,start_line,end_line,embedding,flagged) VALUES (%s,%s,%s,%s,%s::vector,%s)",
                       (row["id"], passage, first, last, vector(passage), bool(INJECTION.search(passage))))
        return {"id": str(row["id"]), "reused": False}


def retrieve(question, threshold=0.16):
    query_tokens = tokens(question)
    if not query_tokens or INJECTION.search(question):
        return []
    with connect() as db:
        rows = db.execute("SELECT c.id,c.document_id,c.passage,c.start_line,c.end_line,d.title,1-(embedding <=> %s::vector) AS score "
                          "FROM chunks c JOIN documents d ON d.id=c.document_id WHERE NOT c.flagged "
                          "ORDER BY embedding <=> %s::vector LIMIT 8", (vector(question), vector(question))).fetchall()
    # Word overlap stops hash collisions from becoming a source match.
    return [row for row in rows if row["score"] >= threshold and
            len(query_tokens & tokens(row["passage"])) >= min(2, len(query_tokens))][:4]


def local_quotes(question, passages):
    selected = []
    for passage in passages[:2]:
        sentences = [sentence for line in passage["passage"].splitlines() if line.strip() and not line.lstrip().startswith("#")
                     for sentence in re.split(r"(?<=[.!?])\s+", line)]
        if not sentences:
            continue
        sentence = max(sentences, key=lambda text: len(tokens(question) & tokens(text)))
        selected.append({"chunk_id": passage["id"], "quote": sentence})
    return selected


def validate_quotes(quotes, passages):
    by_id = {row["id"]: row for row in passages}
    citations = []
    if len(quotes) > 3:
        raise ValueError("Too many source passages returned")
    for quote in quotes:
        if not isinstance(quote, dict):
            raise ValueError("The answer contained an invalid source entry")
        row = by_id.get(quote.get("chunk_id"))
        text = quote.get("quote", "")
        if not row or not isinstance(text, str) or not text.strip() or text not in row["passage"]:
            raise ValueError("The answer contained a quote that was not in its source")
        citations.append({"chunk_id": row["id"], "document_id": str(row["document_id"]), "title": row["title"],
                          "quote": text, "start_line": row["start_line"], "end_line": row["end_line"]})
    return citations
