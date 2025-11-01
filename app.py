from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List, Dict, Any

app = FastAPI(title="NOVOYAZ Backend (stub)")

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "novoyaz-stub"}

@app.post("/ocr")
async def ocr_stub(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    meta = []
    for f in files:
        # read chunk to validate streaming works, then discard
        head = await f.read(4096)
        meta.append({
            "filename": f.filename,
            "content_type": f.content_type,
            "sample_bytes": len(head),
        })
    
    return {
        "stage": "stub",
        "received_files": meta,
        "pre_reform_text": "",  # to be filled later
        "modern_text": ""       # to be filled later
    }
