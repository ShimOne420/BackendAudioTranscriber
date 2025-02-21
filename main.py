import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import shutil

# ✅ Initialize Firebase (only if not already active)
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")  # Make sure this file exists on VM
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firebase connected successfully!")

# ✅ Predefined access codes for authentication
ACCESS_CODES = {"abc123", "test456", "demo789"}  # Modify as needed

# ✅ Initialize FastAPI
app = FastAPI()

# Configura CORS per permettere l'accesso dal frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend-3746xyhru-simones-projects-5e0d6eb3.vercel.app/"],  # 🔥 Se vuoi limitare, metti l'URL del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Server is running!"}

@app.post("/login")
def login(code: str = Form(...)):
    ACCESS_CODES = {"abc123", "test456", "demo789"}
    if code in ACCESS_CODES:
        return {"status": "success", "message": "Access granted"}
    raise HTTPException(status_code=403, detail="Invalid access code")

@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("auto"), code: str = Form(...)):
    """
    ✅ API Endpoint to store audio files and transcription results in Firebase.
    The actual transcription happens in Google Colab.
    """
    try:
        # 🔹 Validate access code
        if code not in ACCESS_CODES:
            raise HTTPException(status_code=403, detail="Invalid access code")

        file_path = f"/tmp/{file.filename}"

        # 🔹 Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 🔹 Store file metadata in Firebase (to trigger Colab processing)
        db.collection("transcriptions").document(file.filename).set({
            "status": "pending",
            "language": language,
            "file_path": file_path
        })

        print(f"✅ Audio file {file.filename} stored for processing.")
        return {"message": "File uploaded successfully. Processing will start soon."}

    except Exception as e:
        print(f"❌ Error storing file {file.filename}: {str(e)}")
        return {"error": str(e)}

# ✅ Start FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
