from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
import re

app = FastAPI(
    title="API B2B - Validación de Datos de Clientes",
    description="Servicio micro-SaaS para validar correos, teléfonos y documentos de identidad.",
    version="1.0.0"
)

# Clave de API de prueba para tus clientes
API_KEY_VALIDA = "clave_secreta_demo_123"

# Estructura de los datos que enviará el cliente
class SolicitudValidacion(BaseModel):
    correo: str
    telefono: str
    documento: str

@app.post("/v1/validar-cliente")
def validar_cliente(datos: SolicitudValidacion, x_api_key: str = Header(None)):
    # 1. Seguridad: Verificar la clave API del cliente
    if x_api_key != API_KEY_VALIDA:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o no proporcionada"
        )
    
    # 2. Validar Correo Electrónico
    patron_correo = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    correo_valido = bool(re.match(patron_correo, datos.correo.strip()))
    
    # 3. Validar y Formatear Teléfono Celular (Colombia - 10 dígitos)
    telefono_limpio = re.sub(r"\D", "", datos.telefono)
    telefono_valido = len(telefono_limpio) == 10 and telefono_limpio.startswith("3")
    telefono_formateado = f"+57 {telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}" if telefono_valido else None
    
    # 4. Validar Documento / NIT (solo números, entre 6 y 10 dígitos)
    documento_limpio = re.sub(r"\D", "", datos.documento)
    documento_valido = 6 <= len(documento_limpio) <= 10

    # Respuesta estructurada para la empresa cliente
    es_valido_todo = correo_valido and telefono_valido and documento_valido

    return {
        "status": "exitoso",
        "resultado_general": "APROBADO" if es_valido_todo else "RECHAZADO",
        "detalles": {
            "correo": {
                "valor_recibido": datos.correo,
                "es_valido": correo_valido
            },
            "telefonso": {
                "valor_recibido": datos.telefono,
                "es_valido": telefono_valido,
                "formato_internacional": telefono_formateado
            },
            "documento": {
                "valor_recibido": datos.documento,
                "es_valido": documento_valido
            }
        }
    }
