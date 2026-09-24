import time
import uuid
import httpx
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from .db import connect
from .retrieval import retrieve, local_quotes, validate_quotes
from . import provider


def answer_question(question, key, mode="local", threshold=0.16):
    started = time.perf_counter()
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(key),))
        previous = db.execute("SELECT * FROM answers WHERE request_key=%s", (key,)).fetchone()
        if previous:
            if previous["question"] != question or previous["mode"] != mode:
                raise HTTPException(409, "This request key belongs to a different question.")
            return previous
        passages = retrieve(question, threshold)
        citations, usage, error = [], {}, None
        status = "unanswered"
        try:
            if passages:
                if mode == "api":
                    quotes, usage = provider.extract(question, passages)
                else:
                    quotes = local_quotes(question, passages)
                citations = validate_quotes(quotes, passages)
                status = "answered" if citations else "unanswered"
        except (ValueError, TypeError, KeyError, httpx.HTTPError):
            status = "failed"
            error = "The answer could not be verified. Check the API settings or try a new request."
        text = "\n\n".join(c["quote"] for c in citations) if citations else "I could not find an answer in the documents."
        if status == "failed":
            text = error
        row = db.execute("INSERT INTO answers(id,request_key,question,mode,status,answer,citations,duration_ms,input_tokens,output_tokens,estimated_cost,error) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                         (uuid.uuid4(), key, question, mode, status, text, Jsonb(citations), round((time.perf_counter()-started)*1000),
                          usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                          0 if mode == "local" else provider.estimate_cost(usage) if usage else None, error)).fetchone()
        return row
