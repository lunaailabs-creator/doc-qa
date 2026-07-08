import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Document Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parent
TEMP_PDF_PATH = ROOT_DIR / "temp.pdf"
STATIC_DIR = ROOT_DIR / "static"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
PDF_MAGIC_BYTES = b"%PDF-"


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    first_chunk = await file.read(len(PDF_MAGIC_BYTES))
    if not first_chunk.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(status_code=400, detail="File does not look like a valid PDF.")

    total_bytes = len(first_chunk)
    tmp_path = TEMP_PDF_PATH.with_suffix(".part")
    try:
        with open(tmp_path, "wb") as f:
            f.write(first_chunk)
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="PDF exceeds the 25 MB upload limit.")
                f.write(chunk)
        tmp_path.replace(TEMP_PDF_PATH)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return {"filename": file.filename, "message": "File uploaded successfully."}


@app.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    if not TEMP_PDF_PATH.exists():
        raise HTTPException(status_code=400, detail="No document uploaded yet.")

    # NOTE: AI logic intentionally not implemented here.
    # Plug in document Q&A logic using temp.pdf and payload.question.
    answer = "AI logic not implemented yet."
    return AskResponse(answer=answer)


# Serve the vanilla JS frontend as static files.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
