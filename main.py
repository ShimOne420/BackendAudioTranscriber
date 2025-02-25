import os
import firebase_admin
import requests
from firebase_admin import credentials, firestore
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import uvicorn

# ✅ Inizializza Firebase solo se non già attivo
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firebase connected successfully!")

# ✅ Codici di accesso predefiniti per autenticazione
ACCESS_CODES = {"abc123", "test456", "demo789"}

def get_colab_url():
    """✅ Recupera l'ultimo URL di Colab da Firebase."""
    doc = db.collection("config").document("colab").get()
    if doc.exists:
        return doc.to_dict().get("url", None)
    return None

# ✅ Configura FastAPI
app = FastAPI()

# ✅ Configurazione CORS (gestita da Nginx)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Authorization"]
)

@app.get("/")
def root():
    return {"message": "Server is running!"}

@app.post("/login")
def login(code: str = Form(...)):
    """✅ Valida il codice di accesso prima di permettere la trascrizione"""
    if code in ACCESS_CODES:
        return {"status": "success", "message": "Access granted"}
    raise HTTPException(status_code=403, detail="Invalid access code")

@app.get("/progress")
def get_progress(file: str):
    """✅ Recupera il progresso della trascrizione in tempo reale."""
    doc = db.collection("transcriptions").document(file).get()
    if not doc.exists:
        return {"error": "File not found"}

    data = doc.to_dict()
    progress = data.get("progress", 0)  # Percentuale completamento
    text = data.get("text", "")

    return {"progress": progress, "text": text}

@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("auto"), code: str = Form(...)):
    """
    ✅ API Endpoint per ricevere file audio e inviarlo a Google Colab.
    """
    try:
        # 🔹 Verifica il codice di accesso
        if code not in ACCESS_CODES:
            raise HTTPException(status_code=403, detail="Invalid access code")

        print(f"📥 Ricevuto file: {file.filename}")

        file_path = f"/tmp/{file.filename}"

        # 🔹 Salva il file localmente sulla VM
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"✅ File salvato in: {file_path}")

        # 🔹 Controlla se il file è vuoto
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"❌ Errore: file vuoto!")
            return {"error": "Uploaded file is empty"}

        # 🔹 Recupera l'URL di Colab
        colab_url = get_colab_url()
        if not colab_url:
            print("❌ Errore: Colab URL non trovato!")
            return {"error": "Colab URL not found. Try again later."}

        print(f"🚀 Inviando file a Colab: {colab_url}")

        # 🔹 Invia direttamente il file a Colab con timeout aumentato
        url = f"{colab_url}/transcribe"
        with open(file_path, 'rb') as audio_file:
            files = {'file': audio_file}
            data = {'language': language}

            response = requests.post(url, files=files, data=data, timeout=600)  # ⏳ Timeout aumentato a 10 minuti

        print(f"📌 Risposta ricevuta da Colab: {response.status_code}")

        # ✅ Se Colab risponde con errore, restituisci il messaggio di errore
        if response.status_code != 200:
            print(f"❌ Errore da Colab: {response.text}")
            return {"error": f"Colab returned an error: {response.status_code}"}

        result = response.json()
        print("📄 JSON ricevuto da Colab:", result)

        return {"message": "Transcription started successfully!"}

    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione con Colab: {str(e)}")
        return {"error": "Failed to connect to Colab"}

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"error": str(e)}


# ✅ Avvia il server FastAPI sulla VM (porta 8000)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=6000)