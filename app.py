from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List, Dict, Any
from PIL import Image, ImageOps
import io, threading
import numpy as np

app = FastAPI(title="NOVOYAZ Backend (OCR v1, lazy & robust)")

# --- Lazy singleton for PaddleOCR ---
_ocr = None
_ocr_lock = threading.Lock()

def get_ocr():
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                from paddleocr import PaddleOCR  # import lazily to keep startup fast
                _ocr = PaddleOCR(lang="ru", use_angle_cls=True)  # angle cls enabled via ctor
    return _ocr

@app.get("/ping")
def ping():
    return {"ok": True, "service": "novoyaz-ocr-v1"}

def pil_from_upload(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    return ImageOps.exif_transpose(img).convert("RGB")

def _normalize_paddle_result(result: Any) -> Dict[str, Any]:
    """Accepts PaddleOCR.ocr(...) output across versions and normalizes to lines+text."""
    lines, texts = [], []

    # result is typically a list[page] where page is list[line]
    if not isinstance(result, (list, tuple)):
        return {"lines": [], "text": ""}

    for page in result:
        if not isinstance(page, (list, tuple)):
            continue
        for item in page:
            bbox, txt, conf = None, "", 0.0

            # Case A: dict-shaped (some pipelines)
            if isinstance(item, dict):
                bbox = item.get("points") or item.get("bbox") or item.get("box")
                txt = item.get("text") or ""
                conf = float(item.get("score") or item.get("confidence") or 0.0)

            # Case B: list/tuple, common shapes:
            #   [points, (text, score)]
            #   [points, [text, score]]
            #   [points, text, score]
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                bbox = item[0]
                second = item[1]
                if isinstance(second, (list, tuple)) and len(second) >= 2:
                    # [points, (text, score)]
                    txt = second[0]
                    conf = float(second[1])
                elif len(item) >= 3:
                    # [points, text, score]
                    txt = second
                    try:
                        conf = float(item[2])
                    except Exception:
                        conf = 0.0
                else:
                    # [points, text] (rare)
                    txt = str(second)
                    conf = 0.0

            if bbox is None:
                continue

            lines.append({"text": txt, "confidence": conf, "bbox": bbox})
            texts.append(txt)

    return {"lines": lines, "text": "\n".join(texts)}

def ocr_image(img: Image.Image) -> Dict[str, Any]:
    arr = np.array(img)  # RGB ndarray
    ocr = get_ocr()
    result = ocr.ocr(arr)  # no cls kwarg in recent versions
    return _normalize_paddle_result(result)

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
