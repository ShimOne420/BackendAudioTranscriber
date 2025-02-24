import os
import firebase_admin
import requests
from firebase_admin import credentials, firestore, storage
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import uvicorn

# ✅ Inizializza Firebase solo se non già attivo
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred, {"storageBucket": "tuo-bucket.appspot.com"})

db = firestore.client()
bucket = storage.bucket()
print("✅ Firebase connected successfully!")

# ✅ Codici di accesso predefiniti per autenticazione
ACCESS_CODES = {"abc123", "test456", "demo789"}

def get_colab_url():
    """✅ Recupera l'ultimo URL di Colab da Firebase, se non esiste restituisce None."""
    doc = db.collection("config").document("colab").get()
    if doc.exists:
        return doc.to_dict().get("url", None)
    return None

# ✅ Configura FastAPI
app = FastAPI()

# ✅ Rimuovi completamente la gestione di CORS in FastAPI
# perché lo gestisce già Nginx
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # 🔹 Vuoto per evitare duplicazioni
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
    progress = data.get("progress", 0)  # Valore tra 0-100
    text = data.get("text", "")

    return {"progress": progress, "text": text}

@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("auto"), code: str = Form(...)):
    """
    ✅ API Endpoint per ricevere file audio e inviarli a Google Colab per la trascrizione.
    La trascrizione avviene su Colab e viene poi salvata su Firebase.
    """
    try:
        # 🔹 Verifica il codice di accesso
        if code not in ACCESS_CODES:
            raise HTTPException(status_code=403, detail="Invalid access code")

        print(f"📥 Ricevuto file: {file.filename}")

        file_path = f"/tmp/{file.filename}"

        # 🔹 Salva il file audio temporaneamente sulla VM
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"✅ File salvato correttamente in: {file_path}")

        # 🔹 Verifica se il file ha dimensione maggiore di 0 bytes
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"❌ Errore: il file salvato è vuoto!")
            return {"error": "Uploaded file is empty"}

        # ✅ Carica il file su Firebase Storage
        blob = bucket.blob(f"audio/{file.filename}")
        blob.upload_from_filename(file_path)
        blob.make_public()
        file_url = blob.public_url

        print(f"✅ File caricato su Firebase Storage: {file_url}")

        # 🔹 Recupera l'URL aggiornato di Google Colab
        colab_url = get_colab_url()
        if not colab_url:
            print("❌ Errore: Colab URL non trovato!")
            return {"error": "Colab URL not found. Try again later."}

        print(f"🚀 Inviando URL del file a Colab: {colab_url}")

        # 🔹 Invia solo il link del file a Colab
        url = f"{colab_url}/transcribe"
        response = requests.post(url, data={"file_url": file_url, "language": language}, timeout=600)

        print(f"📌 Risposta da Colab ricevuta, codice {response.status_code}")

        # ✅ Se Colab risponde con errore, stampalo in console e ritorna un messaggio chiaro
        if response.status_code != 200:
            print(f"❌ Errore da Colab: {response.text}")
            return {"error": f"Colab returned an error: {response.status_code}"}

        result = response.json()

        print("📄 JSON ricevuto da Colab:", result)

        # ✅ Se la trascrizione è presente nel JSON di risposta, la salviamo in Firebase
        if "transcription" in result:
            transcription = result["transcription"]

            # 🔹 Salva la trascrizione su Firebase
            transcription_ref = db.collection("transcriptions").document(file.filename)
            transcription_ref.set({
                "text": transcription,
                "language": language,
                "filename": file.filename,
                "progress": 100
            })

            print(f"✅ Trascrizione salvata con successo per {file.filename}")

            return {"message": "Transcription saved successfully!", "transcription": transcription}

        print("❌ Errore: Nessuna trascrizione trovata nel JSON")
        return {"error": "Error processing transcription"}

    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione con Colab: {str(e)}")
        return {"error": "Failed to connect to Colab"}

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"error": str(e)}

@app.get("/get_transcription")
def get_transcription(filename: str):
    """
    ✅ Recupera la trascrizione di un file specifico da Firebase.
    """
    doc = db.collection("transcriptions").document(filename).get()
    if not doc.exists:  # ✅ Corretto: non è una funzione
        return {"error": "Transcription not found"}

    return doc.to_dict()
    
# ✅ Avvia il server FastAPI sulla VM (porta 8000)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=6000)