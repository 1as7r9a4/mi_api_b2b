from fastapi import FastAPI, HTTPException, Header
import time

app = FastAPI(
    title="Mi API de Datos B2B",
    description="Servidor de micro-servicios monetizable",
    version="1.0.0"
)

# Clave de prueba inicial
API_KEY_VALIDA = "clave_secreta_demo_123"

@app.get("/")
def inicio():
    return {
        "estado": "Servidor Activo",
        "mensaje": "Bienvenido al centro de datos B2B"
    }

@app.get("/v1/obtener-datos")
def obtener_datos(x_api_key: str = Header(None)):
    if x_api_key != API_KEY_VALIDA:
        raise HTTPException(
            status_code=403, 
            detail="Acceso denegado: API Key inválida o no proporcionada"
        )
    
    # Simulación de respuesta de datos en tiempo real
    return {
        "status": "exitoso",
        "timestamp": time.time(),
        "datos": {
            "precio_mercado_usd": 125.50,
            "tendencia": "Alcista",
            "peticion_cobrada": "$0.001 USD"
        }
    }