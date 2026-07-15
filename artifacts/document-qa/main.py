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

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024
PDF_MAGIC_BYTES = b"%PDF-"

qa_chain = None


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    global qa_chain

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
                    raise HTTPException(status_code=413, detail="PDF exceeds the 25 MB limit.")
                f.write(chunk)
        tmp_path.replace(TEMP_PDF_PATH)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    from langchain_groq import ChatGroq
    from langchain.chains import RetrievalQA
    from langchain.prompts import PromptTemplate

    loader = PyPDFLoader(str(TEMP_PDF_PATH))
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    prompt_template = """Use the context below to answer the question.
At the end, mention which page(s) the info came from.
If you don't know, say "I couldn't find that in the document."

Context: {context}
Question: {question}
Answer:"""

    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )

    llm = ChatGroq(
        model="llama3-8b-8192",
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        chain_type_kwargs={"prompt": PROMPT}
    )

    return {"filename": file.filename, "pages": len(docs), "message": "Ready!"}


@app.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    if not TEMP_PDF_PATH.exists() or qa_chain is None:
        raise HTTPException(status_code=400, detail="No document uploaded yet.")

    result = qa_chain.invoke(payload.question)
    return AskResponse(answer=result["result"])


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
