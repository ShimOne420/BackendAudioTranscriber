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
    """✅ Recupera l'ultimo URL di Colab da Firebase, se non esiste restituisce None."""
    doc = db.collection("config").document("colab").get()
    if doc.exists:
        return doc.to_dict().get("url", None)
    return None

# ✅ Configura FastAPI
app = FastAPI()

# ✅ Lista dei domini autorizzati
ALLOWED_ORIGINS = [
    "https://frontend-eight-puce-41.vercel.app",
    "https://frontend-simones-projects-5e0d6eb3.vercel.app"
]

# ✅ Configura CORS per permettere SOLO l'accesso dai frontend autorizzati
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 🔹 Specifica solo i domini necessari
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # 🔹 Permetti solo i metodi che servono
    allow_headers=["Content-Type", "Authorization"],  # 🔹 Solo gli header necessari
    expose_headers=["Content-Type", "Authorization"]
)

@app.get("/")
def root():
    return {"message": "Server is running!"}

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

@app.post("/login")
def login(code: str = Form(...)):
    """✅ Valida il codice di accesso prima di permettere la trascrizione"""
    if code in ACCESS_CODES:
        return {"status": "success", "message": "Access granted"}
    raise HTTPException(status_code=403, detail="Invalid access code")

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

        # 🔹 Verifica se il file è stato salvato correttamente
        if not os.path.exists(file_path):
            print(f"❌ Errore: il file non è stato salvato!")
            return {"error": "File not saved"}

        # 🔹 Recupera l'URL aggiornato di Google Colab
        colab_url = get_colab_url()
        if not colab_url:
            print("❌ Errore: Colab URL non trovato!")
            return {"error": "Colab URL not found. Try again later."}

        print(f"🚀 Inviando file a Colab: {colab_url}")

        # 🔹 Invia il file audio a Google Colab per la trascrizione
        url = f"{colab_url}/transcribe"
        with open(file_path, 'rb') as audio_file:
            files = {'file': audio_file}
            data = {'language': language}

            response = requests.post(url, files=files, data=data)

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
            old_data = transcription_ref.get()
            old_text = old_data.to_dict().get("text", "") if old_data.exists else ""

            updated_text = old_text + " " + transcription  # Continua la trascrizione
            transcription_ref.set({"text": updated_text, "language": language})

            print(f"✅ Trascrizione salvata con successo per {file.filename}")

            return {"message": "Transcription saved successfully!", "transcription": updated_text}

        print("❌ Errore: Nessuna trascrizione trovata nel JSON")
        return {"error": "Error processing transcription"}

    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione con Colab: {str(e)}")
        return {"error": "Failed to connect to Colab"}

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"error": str(e)}
    
    
# ✅ Avvia il server FastAPI sulla VM (porta 8000)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)