# Source Notes

Source Notes finds passages in a small library of text documents. It gives exact quotes, links back to their context, and asks a person to review a note before approving it.

## Try the main task

Sign in as `demo` and load the two sample guides. Ask, "Who must approve a stock adjustment?" The answer should include the manager rule. Click its source to open the passage and line numbers.

Send the answer for review. It becomes a pending note. Open **Review notes**, read it, and approve or reject it. Asking a question alone never creates an approved note.

Ask about the employee dental insurance premium. The sample guides do not contain that information, so the app should say it could not find an answer.

Open **Quality checks** and run the eight fixed questions. Then raise the match threshold and compare the saved runs. These checks measure the supplied examples, not every question someone might ask.

## Where the code lives

| Part | File | Job |
| --- | --- | --- |
| Page | `web/src/App.tsx` | Questions, source library, note review, and results |
| API | `app/main.py` | Imports documents and handles questions and review |
| Retrieval | `app/retrieval.py` | Splits text, builds vectors, finds passages, and checks quotes |
| Answer record | `app/answers.py` | Handles repeated requests and logs outcomes |
| Optional model | `app/provider.py` | Sends a bounded request to the OpenAI Responses API |
| Fixed checks | `app/evaluation.py` | Questions with expected answers and no-answer cases |
| Database | `app/schema.sql` | Documents, passages, questions, notes, and evaluations |

## Documents become passages

The app accepts plain text and Markdown. It keeps the original text and splits it at blank lines or the size limit. Each passage keeps its original line numbers. Reimporting identical text reuses the same document.

Passages containing a few common prompt-injection phrases are marked and excluded from retrieval. The text stays visible for review. This simple detector will not recognize every hostile instruction. The more important limit is that the model has no write tools and can only propose source quotes.

## What a vector means here

A vector is a list of numbers. Similar lists can be compared with a distance or similarity score. pgvector adds those operations to PostgreSQL.

The local demo turns words into a repeatable 256-number vector using hashing. It removes common words and handles a few related word forms. It is a small lexical baseline. It does not understand synonyms or meaning the way a trained embedding model can.

The database compares the question vector with passage vectors. A second word-overlap check removes matches caused by hash collisions. Only passages above a minimum score and overlap count are kept.

This works on the small sample library, but it can miss paraphrased questions or return a passage that shares words without answering the question. Source links and human review remain necessary. Replacing this baseline with learned embeddings is a future experiment, not an existing claim.

## Local mode and API mode

Local mode picks relevant sentences from the retrieved passages. It makes no model calls and costs no API money. Its answers are exact source excerpts.

API mode sends the question and a small set of passages to the configured OpenAI model. It uses Structured Outputs to request a list of source IDs and exact quotes. It does not give the model tools that can change the database.

The backend then checks every quote against the retrieved passage. A missing source or invented quote makes the request fail. Even a perfectly copied quote can be irrelevant or misleading out of context, so this check is evidence checking, not a guarantee of correctness.

To enable API mode, set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`, then restart Source Notes. Use a model that supports the Responses API and Structured Outputs. Add the current input and output prices per million tokens if you want a cost estimate. Blank prices show an unknown cost. Estimates do not account for every possible pricing rule, such as cached-token discounts.

Only text you choose to search in API mode is sent to OpenAI. The demo documents are safe sample material. Use documents you have permission to send. The key stays on the backend.

Official references used for the adapter: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [embeddings](https://developers.openai.com/api/docs/guides/embeddings), and [pgvector](https://github.com/pgvector/pgvector). The embeddings guide is a reference for a later semantic-search upgrade; this build does not call the embeddings API.

## Repeated requests and review

Each question has a request key. PostgreSQL locks that key while handling it. Repeating the same question with the same key returns the stored result. Reusing a key for a different question is rejected.

Creating a note is a separate action. The server accepts only answers with checked citations. A note starts pending. Only the review endpoint can approve or reject it, and a second review is rejected.

This is a single-account review demo. It proves an explicit review step, not a two-person approval process or a production role system. Rejected and approved notes stay in the history.

## What the measurements mean

Each answer records elapsed time, mode, status, citations, token counts when returned by the provider, and an estimated cost when prices are set. Failed calls with unknown usage do not get a made-up zero-dollar estimate.

The eight-question evaluation runs local retrieval at a chosen threshold. It checks for a known phrase or a no-answer result. It is a small regression set. It does not measure general language understanding, live-model quality, or all forms of prompt injection.

The adapter tests use a fake HTTP response to check the API request shape, rate-limit failures, and quote validation. A real paid API call has not been made during this build because no key was configured.

## Practice explaining it

Explain the difference between retrieval and generation. Explain why an exact quote can still be a poor answer. Describe how a model-generated result becomes a pending note, and which server route is allowed to approve it.
