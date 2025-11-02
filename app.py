from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List, Dict, Any
from paddleocr import PaddleOCR
from PIL import Image, ImageOps
import io

app = FastAPI(title="NOVOYAZ Backend (OCR v1)")

# --- single global OCR instance (loads weights on first use) ---
# lang="ru" for Cyrillic; use_angle_cls fixes rotated lines.
ocr = PaddleOCR(lang="ru", use_angle_cls=True)

@app.get("/ping")
def ping():
    return {"ok": True, "service": "novoyaz-ocr-v1"}

def pil_from_upload(data: bytes) -> Image.Image:
    # Fix EXIF rotation, ensure RGB
    img = Image.open(io.BytesIO(data))
    return ImageOps.exif_transpose(img).convert("RGB")

def ocr_image(img: Image.Image) -> Dict[str, Any]:
    # PaddleOCR accepts file path or bytes-like; feed PNG bytes to be safe
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
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
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type for {f.filename}. Use JPG/PNG for this step."
            )
        out = ocr_image(img)
        outputs.append({
            "input": f.filename,
            "kind": "image",
            "pre_reform_text": out["text"],  # OCR result
            "modern_text": "",               # will fill in next step
            "lines": out["lines"]
        })

    return {"results": outputs, "lang": "ru"}
