from fastapi import FastAPI, UploadFile, Form
import whisper # type: ignore
import shutil
import os

app = FastAPI()

# Predefined access codes (replace with database later)
ACCESS_CODES = {"abc123", "test456", "demo789"}

# Load Whisper Model
model = whisper.load_model("small")  # Use "small" or "medium" for speed

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.post("/login")
def login(code: str = Form(...)):
    if code in ACCESS_CODES:
        return {"status": "success", "message": "Access granted"}
    return {"status": "error", "message": "Invalid code"}

@app.post("/transcribe")
async def transcribe(file: UploadFile):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Transcribe the file
    result = model.transcribe(file_path, language="it")

    # Save transcription
    output_path = os.path.join(OUTPUT_FOLDER, f"{file.filename}.txt")
    with open(output_path, "w") as f:
        f.write(result["text"])

    os.remove(file_path)  # Cleanup after processing
    return {"transcription": result["text"]}
