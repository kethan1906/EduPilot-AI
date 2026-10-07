\# EduPilot AI



An academic research assistant. Upload a research PDF, ask a question, and get an answer that is generated only from the retrieved passages of your documents, with the filename and page of every source.



\*\*Stack:\*\* Python, Flask (REST APIs), RAG, Mistral LLM via Ollama, NLP (cleaning + chunking), Sentence Transformers (`BAAI/bge-small-en-v1.5`), MongoDB + MongoDB Atlas Vector Search, PyMuPDF.



\## How it works



```text

Upload:  PDF -> extract text per page -> clean -> chunk (450 words, 75 overlap)

&#x20;            -> embed each chunk -> store chunks + vectors in MongoDB



Ask:     question -> embed (same model) -> Atlas $vectorSearch (top 5 chunks)

&#x20;            -> build labelled context -> Mistral via Ollama (answer only from context)

&#x20;            -> answer + sources -> saved in query history

```



| Step     | Module                                 | What / why / data flow                                                                                                                                 |

| -------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |

| Validate | `routes/api.py`                        | Rejects missing files, non-PDFs and empty questions with `400` before any work happens. Routes stay thin and delegate to services.                     |

| Extract  | `utils/pdf\_utils.py`                   | PyMuPDF reads the upload from memory, page by page. Page numbers are kept so answers can cite a page. Pages with no text are skipped.                  |

| Clean    | `utils/text\_utils.clean\_text`          | Collapses whitespace so PDF line breaks don't distort chunk boundaries.                                                                                |

| Chunk    | `utils/text\_utils.chunk\_text`          | Word windows of 450 with 75 overlap, so an answer straddling a boundary appears whole in at least one chunk.                                           |

| Embed    | `services/embedding\_service.py`        | Same model for chunks and questions (required for comparable vectors), L2-normalised, converted to plain lists for BSON. The model loads on first use. |

| Store    | `services/document\_service.py`         | `documents` (metadata + status), `chunks` (text, page, embedding). Status goes `processing` -> `ready` / `failed`.                                     |

| Retrieve | `services/rag\_service.retrieve\_chunks` | Embeds the question and runs `$vectorSearch` (`numCandidates` 50, `limit` 5), returning each chunk's similarity score.                                 |

| Generate | `services/rag\_service.generate\_answer` | System prompt: answer only from the context, say so if the information is missing, never invent facts. Mistral runs locally through Ollama.            |

| Log      | `services/rag\_service.answer\_question` | Saves question, answer, and `{chunk\_id, score}` for each retrieved chunk in `queries`. If retrieval is empty the LLM is not called.                    |



\## Setup



Requires Python 3.10+, a MongoDB Atlas cluster (free M0 works), and Ollama with the Mistral model installed locally.



```bash

git clone <your-repo-url> edupilot-ai \&\& cd edupilot-ai

python -m venv .venv \&\& source .venv/bin/activate     # Windows: .venv\\Scripts\\activate

pip install -r requirements.txt

cp .env.example .env                                   # then edit .env

```



\## Ollama setup



Install Ollama and make sure the Mistral model is available locally:



```bash

ollama pull mistral

```



Start Ollama before running EduPilot.



By default, the application connects to:



```text

http://localhost:11434

```



The application uses the local `mistral:latest` model through Ollama, so no Mistral API key is required.



\## Environment variables (`.env`)



| Variable        | Required                      | Meaning                 |

| --------------- | ----------------------------- | ----------------------- |

| `MONGODB\_URI`   | yes                           | Atlas connection string |

| `MONGODB\_DB`    | no (`edupilot`)               | Database name           |

| `OLLAMA\_HOST`   | no (`http://localhost:11434`) | Local Ollama server     |

| `OLLAMA\_MODEL`  | no (`mistral:latest`)         | Local Mistral model     |

| `MAX\_UPLOAD\_MB` | no (`25`)                     | Upload size limit       |

| `FLASK\_DEBUG`   | no (`0`)                      | Flask debug mode        |



Missing variables produce a clear `503` JSON error naming the variable; they never crash at import.



\## MongoDB Atlas configuration



Create a free cluster, add a database user, and under Network Access allow your IP.



Put the connection string in `MONGODB\_URI`.



Create the Vector Search index on the `chunks` collection, either automatically:



```bash

python scripts/create\_vector\_index.py

```



or in the Atlas UI (Atlas Search -> Create Search Index -> Atlas Vector Search -> JSON editor, database `edupilot`, collection `chunks`, index name `chunk\_vector\_index`):



```json

{

&#x20; "fields": \[

&#x20;   {

&#x20;     "type": "vector",

&#x20;     "path": "embedding",

&#x20;     "numDimensions": 384,

&#x20;     "similarity": "cosine"

&#x20;   }

&#x20; ]

}

```



384 is the output size of `bge-small-en-v1.5`; if you change the model, change this number.



Wait until the index shows Active before asking questions. A missing/building index is the most common reason for "could not find relevant information" or a `503` retrieval error.



The first upload downloads the embedding model (\~130 MB) from Hugging Face, so it needs internet and is slow once.



\## Run



Make sure Ollama is running, then start EduPilot:



```bash

python app.py          # http://127.0.0.1:5000   (FLASK\_DEBUG=1 for debug mode)

```



\## API



\### `POST /api/documents`



Multipart form, field `file`:



```bash

curl -F "file=@paper.pdf" http://127.0.0.1:5000/api/documents

```



```text

201 {"document\_id":"<id>","filename":"paper.pdf","chunk\_count":<n>}

400 {"error":"No file uploaded"} | {"error":"Only PDF files are supported"}

422 {"error":"..."}  corrupt / password-protected / no extractable text

```



\### `POST /api/query`



JSON:



```bash

curl -X POST http://127.0.0.1:5000/api/query -H "Content-Type: application/json" \\

&#x20;    -d '{"question": "What method do the authors propose?"}'

```



```text

200 {"answer":"...","sources":\[{"filename":"paper.pdf","page":3,"score":0.87}, ...]}

400 {"error":"Question is required"}

502 LLM request failed | 503 missing config / MongoDB unreachable / vector index unavailable

```



Two read endpoints are additions to the original specification, used by the dashboard to show stored metadata and history:



\* `GET /api/documents`

\* `GET /api/queries?limit=20`



\## Tests



```bash

python -m unittest -v

pip install -r requirements-dev.txt \&\& python -m pytest

```



Unit tests replace only the boundaries (MongoDB, embedding model, and local Ollama/Mistral client) with in-memory fakes; chunking, cleaning, validation, ingestion flow, pipeline construction, prompt building and error handling run for real.



The real-PDF extraction tests are skipped unless PyMuPDF and reportlab are installed.



\## Project structure



```text

app.py                         Flask app factory, error handlers, dashboard route

config.py                      RAG parameters, env helpers, Ollama configuration

exceptions.py                  Errors with HTTP status codes

routes/api.py                  REST endpoints (validation only)

services/document\_service.py   Ingestion pipeline, document listing

services/embedding\_service.py  Sentence Transformer wrapper

services/rag\_service.py        Retrieval, context, local Mistral/Ollama call, query history

db/mongo.py                    Lazy MongoDB connection

utils/pdf\_utils.py             PDF text extraction

utils/text\_utils.py            Cleaning and chunking

scripts/create\_vector\_index.py Creates the Atlas vector index

templates/ static/             Dashboard (HTML / CSS / fetch-based JS)

tests/                         Unit tests

```



\## Differences from the original code listing



Mongo client, embedding model and local Ollama client are created on first use instead of at import, so missing config gives a clear error rather than a startup crash.



One `build\_context()` is used (the listing defined it but `answer\_question` used a second inline format).



A PDF with no extractable text is marked `failed` (422) rather than `ready` with zero chunks; partial chunks are removed if ingestion fails.



Empty retrieval is also written to query history.



`chunk\_text` rejects `overlap >= chunk\_size` (it would loop forever).



The Mistral LLM is run locally through Ollama instead of using the hosted Mistral API.



\## Limitations



Text PDFs only: scanned/image PDFs have no OCR and are rejected.



Retrieval searches all uploaded documents together; there are no per-document filters, users or authentication.



Chunking is by words within each page, so a passage spanning a page break is split.



No similarity-score threshold: the top 5 chunks are always sent to the LLM; the prompt, not a filter, handles irrelevant context.



Ingestion runs synchronously inside the upload request; large PDFs take a while.



No retrieval-quality or answer-quality evaluation has been performed, so no accuracy claims are made.



