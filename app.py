from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List, Dict, Any
from PIL import Image, ImageOps
import io, threading

app = FastAPI(title="NOVOYAZ Backend (OCR v1)")

# --- Lazy singleton for PaddleOCR ---
_ocr = None
_ocr_lock = threading.Lock()

def get_ocr():
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:  # double-check under lock
                from paddleocr import PaddleOCR  # import here to avoid heavy import at startup
                _ocr = PaddleOCR(lang="ru", use_angle_cls=True)
    return _ocr

@app.get("/ping")
def ping():
    return {"ok": True, "service": "novoyaz-ocr-v1"}

def pil_from_upload(data: bytes):
    img = Image.open(io.BytesIO(data))
    return ImageOps.exif_transpose(img).convert("RGB")

def ocr_image(img):
    # Bytes to PNG (stable for PaddleOCR buffer input)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    ocr = get_ocr()
    result = ocr.ocr(buf, cls=True)

    lines, text = [], []
    for page in result:
        for (bbox, (txt, conf)) in page:
            lines.append({"text": txt, "confidence": float(conf), "bbox": bbox})
            text.append(txt)
    return {"lines": lines, "text": "\n".join(text)}

@app.post("/ocr")
async def ocr_endpoint(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    outputs = []
    for f in files:
        raw = await f.read()
        try:
            img = pil_from_upload(raw)
        except Exception:
            raise HTTPException(status_code=415, detail=f"Unsupported file type for {f.filename}. Use JPG/PNG for now.")
        out = ocr_image(img)
        outputs.append({
            "input": f.filename,
            "kind": "image",
            "pre_reform_text": out["text"],
            "modern_text": "",
            "lines": out["lines"]
        })
    return {"results": outputs, "lang": "ru"}
