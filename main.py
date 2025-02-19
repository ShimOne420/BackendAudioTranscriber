
import torch
import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, UploadFile, Form, HTTPException
import uvicorn
import shutil

# ✅ Optimize GPU memory allocation
torch.cuda.empty_cache()
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ✅ Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")  # Update with your actual JSON key file
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firebase connected successfully!")

# ✅ Predefined access codes
ACCESS_CODES = {"abc123", "test456", "demo789"}  # Change or expand these

# ✅ Function to load the best model based on language
def load_model(language):
    if language == "it":
        print("🔹 Loading Whisper Large v2 optimized for Italian...")
        return whisper.load_model("large-v2", device="cuda")
    else:
        print(f"🔹 Loading Whisper Large for {language}...")
        return whisper.load_model("large", device="cuda")

# ✅ Initialize FastAPI
app = FastAPI()

@app.post("/login")
def login(code: str = Form(...)):
    """Validates the access code before allowing transcription."""
    if code in ACCESS_CODES:
        return {"status": "success", "message": "Access granted"}
    raise HTTPException(status_code=403, detail="Invalid access code")

@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("auto"), code: str = Form(...)):
    """
    ✅ API Endpoint to transcribe an audio file using Whisper and save it in Firebase.
    """
    try:
        # 🔹 Validate access code
        if code not in ACCESS_CODES:
            raise HTTPException(status_code=403, detail="Invalid access code")

        file_path = f"/tmp/{file.filename}"

        # 🔹 Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 🔹 Load the appropriate Whisper model
        model = load_model(language)

        # 🔹 Transcribe audio
        result = model.transcribe(file_path, language=language)
        output_text = result["text"]

        # 🔹 Save the transcription in Firebase Firestore
        db.collection("transcriptions").document(file.filename).set({
            "text": output_text,
            "language": language
        })

        # 🔹 Remove the file after processing
        os.remove(file_path)

        print(f"✅ Transcription saved successfully for {file.filename}.")
        return {"transcription": output_text, "message": "Transcription saved successfully!"}

    except Exception as e:
        print(f"❌ Error transcribing {file.filename}: {str(e)}")
        return {"error": str(e)}

# ✅ Start FastAPI
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)