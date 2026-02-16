from fastapi import APIRouter, UploadFile, File, Request
import os
import uuid
import shutil
import time

router = APIRouter()

@router.post("/")
async def upload_file(request: Request, file: UploadFile = File(...)):
    if not os.path.exists("static/uploads"):
        os.makedirs("static/uploads", exist_ok=True)
        
    file_extension = file.filename.split(".")[-1]
    filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_location = f"static/uploads/{filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    # Return relative URL so it works through any domain/proxy
    return {"url": f"/static/uploads/{filename}"}
