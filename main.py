import re
from fastapi import FastAPI, HTTPException, status, Header
from pydantic import BaseModel

app = FastAPI(
    title="API B2B - Validación de Datos de Clientes",
    description="Servicio micro-SaaS para validar correos, teléfonos y documentos",
    version="1.0.0"
)

# Clave de API de prueba para tus clientes
API_KEY_VALIDA = "Clave_Secreta_Demo_123"

# Estructura de los datos que enviará el cliente
class SolicitudValidacion(BaseModel):
    correo: str
    telefono: str
    documento: str

@app.post("/v1/validar-cliente")
def validar_cliente(
    datos: SolicitudValidacion,
    x_api_key: str = Header(..., alias="x-api-key")
):
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
    telefono_formateado = f"+57 {telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}" if telefono_valido else datos.telefono

    # 4. Validar Documento / NIT (solo números, entre 6 y 10 dígitos)
    documento_limpio = re.sub(r"\D", "", datos.documento)
    documento_valido = 6 <= len(documento_limpio) <= 10

    # Respuesta estructurada
    es_valido_todo = correo_valido and telefono_valido and documento_valido

    return {
        "status": "exitoso",
        "resultado_general": "APROBADO" if es_valido_todo else "RECHAZADO",
        "detalles": {
            "correo": {
                "valor_recibido": datos.correo,
                "es_valido": correo_valido
            },
            "telefono": {
                "valor_recibido": datos.telefono,
                "es_valido": telefono_valido,
                "formato_internacional": telefono_formateado
            },
            "documento": {
                "valor_recibido": datos.documento,
                "es_valido": documento_valido
            }
        }
    }import re
import uuid
import sqlite3
import stripe
import dns.resolver
from fastapi import FastAPI, HTTPException, status, Header, Request
from pydantic import BaseModel

# Configuración de Stripe (Reemplaza con tus claves cuando tengas cuenta de Stripe)
STRIPE_SECRET_KEY = "sk_test_tu_clave_secreta_aqui"
STRIPE_WEBHOOK_SECRET = "whsec_tu_clave_webhook_aqui"

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(
    title="API B2B - Validación de Datos de Clientes",
    description="Servicio micro-SaaS con pasarela de pagos e integración de créditos",
    version="2.0.0"
)

# ---------------------------------------------------------
# INICIALIZACIÓN DE BASE DE DATOS (SQLite)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            api_key TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            creditos INTEGER NOT NULL
        )
    """)
    # Insertar clave de prueba demo si no existe
    cursor.execute("INSERT OR IGNORE INTO clientes VALUES (?, ?, ?)", 
                   ("Clave_Secreta_Demo_123", "demo@empresa.com", 100))
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# MODELOS DE DATOS
# ---------------------------------------------------------
DOMINIOS_DESECHABLES = {
    "yopmail.com", "tempmail.com", "10minutemail.com", "guerrillamail.com", 
    "mailinator.com", "trashmail.com", "sharklasers.com", "dispostable.com"
}

class SolicitudValidacion(BaseModel):
    correo: str
    telefono: str
    documento: str

class SolicitudCompra(BaseModel):
    email: str
    cantidad_creditos: int

# ---------------------------------------------------------
# LÓGICA DE VALIDACIÓN (MX + TELÉFONO + DOCUMENTO)
# ---------------------------------------------------------
def verificar_correo_avanzado(correo: str) -> dict:
    correo_limpio = correo.strip().lower()
    patron_correo = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(patron_correo, correo_limpio):
        return {"es_valido": False, "motivo": "Formato de correo inválido"}
    
    dominio = correo_limpio.split("@")[-1]
    if dominio in DOMINIOS_DESECHABLES:
        return {"es_valido": False, "motivo": "Dominio de correo desechable/temporal no permitido"}
    
    try:
        respuestas = dns.resolver.resolve(dominio, "MX")
        if not respuestas:
            return {"es_valido": False, "motivo": "El dominio no tiene servidores MX activos"}
    except Exception:
        return {"es_valido": False, "motivo": "Dominio inexistente o sin servidor MX"}

    return {"es_valido": True, "motivo": "Correo válido y activo"}


# ---------------------------------------------------------
# ENDPOINTS DE LA API
# ---------------------------------------------------------

@app.post("/v1/validar-cliente")
def validar_cliente(
    datos: SolicitudValidacion,
    x_api_key: str = Header(..., alias="x-api-key")
):
    # 1. Verificar clave API y saldo en la base de datos
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT creditos FROM clientes WHERE api_key = ?", (x_api_key,))
    resultado = cursor.fetchone()

    if not resultado:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o no registrada"
        )
    
    creditos_actuales = resultado[0]
    if creditos_actuales <= 0:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Saldo insuficiente. Compre más créditos para continuar."
        )

    # 2. Ejecutar validaciones
    resultado_correo = verificar_correo_avanzado(datos.correo)

    telefono_limpio = re.sub(r"\D", "", datos.telefono)
    telefono_valido = len(telefono_limpio) == 10 and telefono_limpio.startswith("3")
    telefono_formateado = f"+57 {telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}" if telefono_valido else datos.telefono

    documento_limpio = re.sub(r"\D", "", datos.documento)
    documento_valido = 6 <= len(documento_limpio) <= 10

    es_valido_todo = resultado_correo["es_valido"] and telefono_valido and documento_valido

    # 3. Descontar 1 crédito de la cuenta
    cursor.execute("UPDATE clientes SET creditos = creditos - 1 WHERE api_key = ?", (x_api_key,))
    conn.commit()
    conn.close()

    return {
        "status": "exitoso",
        "resultado_general": "APROBADO" if es_valido_todo else "RECHAZADO",
        "creditos_restantes": creditos_actuales - 1,
        "detalles": {
            "correo": {
                "valor_recibido": datos.correo,
                "es_valido": resultado_correo["es_valido"],
                "diagnostico": resultado_correo["motivo"]
            },
            "telefono": {
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

# ---------------------------------------------------------
# PASARELA DE PAGOS (STRIPE)
# ---------------------------------------------------------

@app.post("/v1/crear-sesion-pago")
def crear_sesion_pago(compra: SolicitudCompra):
    try:
        precio_unitario_cop = 50 
        monto_total = compra.cantidad_creditos * precio_unitario_cop

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "cop",
                    "product_data": {
                        "name": f"Paquete de {compra.cantidad_creditos} Validaciones API B2B",
                    },
                    "unit_amount": monto_total * 100,
                },
                "quantity": 1,
            }],
            mode="payment",
            customer_email=compra.email,
            metadata={
                "email": compra.email,
                "creditos": str(compra.cantidad_creditos)
            },
            success_url="https://tu-sitio-web.com/exito",
            cancel_url="https://tu-sitio-web.com/cancelado",
        )
        return {"url_de_pago": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/webhook-stripe")
async def webhook_stripe(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Firma de Webhook inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email_cliente = session["metadata"]["email"]
        creditos = int(session["metadata"]["creditos"])

        nueva_api_key = f"ak_live_{uuid.uuid4().hex}"

        conn = sqlite3.connect("clientes.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes VALUES (?, ?, ?)", (nueva_api_key, email_cliente, creditos))
        conn.commit()
        conn.close()

    return {"status": "success"}
fastapi
uvicorn
pydantic
dnspython
stripe
import sqlite3
import stripe
import dns.resolver
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
