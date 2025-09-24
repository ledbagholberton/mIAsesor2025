import os
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, status
from google.cloud import pubsub_v1

# Variables de entorno
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET = os.getenv("APP_SECRET")

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Service is running V9"}

@app.post("/")
def root(payload: dict):
    return {"message": f"Hola {payload['name']}"}

def is_valid_signature(signature: str, payload: bytes) -> bool:
    if not APP_SECRET:
        return False
    if not signature or not signature.startswith("sha256="):    
        return False
    
    signature_hash = signature.split("=")[1]
    expected_hash = hmac.new(
        APP_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature_hash, expected_hash)

@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")
    
    if hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token de verificación no válido."
    )

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    print("Payload recibido:", body)
    return {"status": "success", "message": "Mensaje recibido y encolado."}
"""    
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()

    if not is_valid_signature(signature, body):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firma de Webhook no válida."
        )

    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        publisher.publish(topic_path, data=body)
        print("Mensaje publicado en Pub/Sub de forma asíncrona.")
    except Exception as e:
        print(f"Error al publicar en Pub/Sub: {e}")
        return {"status": "error"}, status.HTTP_200_OK

    return {"status": "success", "message": "Mensaje recibido y encolado."}
    """
