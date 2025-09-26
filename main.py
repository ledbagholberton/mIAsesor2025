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
SUBSCRIPTION_ID = "webhook-sub"

app = FastAPI()

@app.get("/")
def health_check():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    # Leer mensajes con pull (máximo 5 en este ejemplo)
    response = subscriber.pull(
        request={"subscription": subscription_path, "max_messages": 5}
    )

    mensajes = []
    for msg in response.received_messages:
        data = msg.message.data.decode("utf-8")
        print(f"📩 Mensaje recibido: {data}")  # imprime en consola
        mensajes.append(data)

        # Confirmar que ya procesaste este mensaje
        subscriber.acknowledge(
            request={"subscription": subscription_path, "ack_ids": [msg.ack_id]}
        )

    return {
        "status": "ok",
        "message": "Service is running V12",
        "mensajes_en_colados": mensajes or "No hay mensajes pendientes"
    }

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
    body = await request.body()  # contenido crudo del webhook
    print("📥 Payload recibido:", body.decode("utf-8"))

    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

        # Publicar el mensaje en Pub/Sub
        future = publisher.publish(topic_path, data=body)
        message_id = future.result()  # opcional: esperar a que confirme
        print(f"✅ Mensaje encolado en Pub/Sub con ID: {message_id}")

    except Exception as e:
        print(f"❌ Error al publicar en Pub/Sub: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al encolar mensaje"
        )

    return {"status": "success", "message": "Mensaje recibido y encolado en Pub/Sub"}