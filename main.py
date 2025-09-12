import os
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, status
from google.cloud import pubsub_v1
import sys # Importar el módulo sys

# Configuración de variables de entorno
# Estas variables se configuran en el despliegue de Cloud Run
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT')
TOPIC_ID = os.environ.get('PUBSUB_TOPIC_ID')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
APP_SECRET = os.environ.get('APP_SECRET')

# Validar que las variables de entorno existen
"""
if not all([PROJECT_ID, TOPIC_ID, VERIFY_TOKEN, APP_SECRET]):
    missing_vars = [name for name, val in {'PROJECT_ID': PROJECT_ID, 'TOPIC_ID': TOPIC_ID, 'VERIFY_TOKEN': VERIFY_TOKEN, 'APP_SECRET': APP_SECRET}.items() if not val]
    print(f"Error fatal: Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")
    sys.exit(1) # Salir con un código de error
"""
print("DEBUG ENV:", PROJECT_ID, TOPIC_ID, VERIFY_TOKEN, APP_SECRET)

# Inicialización del cliente de Pub/Sub
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

# Inicialización de la aplicación FastAPI
app = FastAPI()

def is_valid_signature(signature: str, payload: bytes) -> bool:
    """
    Valida la firma del webhook para asegurar que la solicitud proviene de Meta.
    Se utiliza HMAC SHA256 para verificar la autenticidad.
    """
    try:
        if not signature.startswith('sha256='):
            return False
        
        signature_hash = signature.split('=')[1]
        
        expected_hash = hmac.new(
            APP_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature_hash, expected_hash)
    except Exception:
        return False

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Endpoint para la verificación inicial del webhook de Meta.
    Responde al GET request con el token de desafío si el token de verificación es correcto.
    """
    hub_challenge = request.query_params.get('hub.challenge')
    hub_verify_token = request.query_params.get('hub.verify_token')
    
    if hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Token de verificación no válido."
        )

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Endpoint principal para recibir y encolar los eventos del webhook de WhatsApp.
    """
    # 1. Obtención y validación de la firma del webhook
    signature = request.headers.get('X-Hub-Signature-256')
    body = await request.body()

    if not signature or not is_valid_signature(signature, body):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Firma de Webhook no válida."
        )

 # 2. Encolamiento del mensaje en Pub/Sub
    try:
        # Se publica el cuerpo del mensaje (bytes) en el topic de Pub/Sub
        publisher.publish(topic_path, data=body)
        print("Mensaje publicado en Pub/Sub de forma asíncrona.")
        
    except Exception as e:
        print(f"Error al publicar en Pub/Sub: {e}")
        # En caso de error de encolamiento, se puede registrar, pero la respuesta sigue siendo 200
        # para no alertar a Meta. El error se maneja en el sistema de monitoreo.
        return {"status": "error", "message": "Error al encolar el mensaje."}, status.HTTP_200_OK

    # 3. Respuesta inmediata a Meta
    return {"status": "success", "message": "Mensaje recibido y encolado."}