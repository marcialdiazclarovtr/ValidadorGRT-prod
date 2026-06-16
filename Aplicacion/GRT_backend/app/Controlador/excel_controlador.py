from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from Modelo.excel_modelo import procesar_excel, leer_primera_hoja_desde_path, leer_hoja_desde_path

from datetime import datetime

import sys
import os

# Import de nombres de las planillas a validar
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from config import NOMBRES as N

# Imports de reglas
from Modelo.Reglas.reglas_post_nuevos_equipos import validar_grt as validar_grt_reglas
from Modelo.Reglas.reglas_precios_full import validar_precios_full as validar_full_reglas
from Modelo.Reglas.reglas_equipos_accesorios import validar_equipos_accesorios
from Modelo.Reglas.reglas_carga_equipos_standalone import validar_equipos_standalone, leer_planilla_precios_standalone
from Modelo.Reglas.reglas_financiamiento import validar_financiamiento, leer_planilla_precios_financiamiento
from Modelo.Reglas.reglas_grt_pie import validar_grt_pie
from Modelo.Reglas.reglas_cargos_claroup import validar_cargos_claroup
from Modelo.Reglas.reglas_nuevos_equipos_claroup import validar_nuevos_equipos_claroup

from Modelo.Reglas.reglas_subsidios import validar_subsidios_claroup, leer_cargo_activacion_desde_precios
from Modelo.generar_planilla_subsidios import generar_planilla_subsidios
from fastapi.responses import FileResponse
import uuid

from Vista.excel_vista import construir_payload
import json
import time
import shutil
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

router = APIRouter()
logger = logging.getLogger("uvicorn")

# ---------------------------------------------
# Flags para activar/desactivar validaciones
# ---------------------------------------------
VALIDAR_PRECIOS_FULL = True
VALIDAR_POST_NUEVOS_EQUIPOS = True
VALIDAR_EQUIPOS_ACCESORIOS = True
VALIDAR_EQUIPOS_STANDALONE = True
VALIDAR_FINANCIAMIENTO = True
VALIDAR_GRT_PIE = True
VALIDAR_SUBSIDIOS_CLAROUP = True
VALIDAR_CARGOS_CLAROUP = True
VALIDAR_NUEVOS_EQUIPOS_CLAROUP = True

# ---------------------------------------------
# Rutas
# ---------------------------------------------
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

TMP_PATH = os.path.join(BASE_DIR, "tmp")
os.makedirs(TMP_PATH, exist_ok=True)

# Rutas de almacenamiento de GRTs
STORAGE_VALIDAS = os.path.join(BASE_DIR, "storage", "GRT", "Validas")
STORAGE_INVALIDAS = os.path.join(BASE_DIR, "storage", "GRT", "Invalidas")
os.makedirs(STORAGE_VALIDAS, exist_ok=True)
os.makedirs(STORAGE_INVALIDAS, exist_ok=True)

# Ruta fija de la planilla macro
MACRO_PATH = os.path.join(BASE_DIR, "data", "macro_envio.xlsx")

# Ruta fija de la planilla de precios
PRICES_PATH = os.path.join(BASE_DIR, "data", "planilla_de_precios.xlsx")

# Ruta fija de la planilla vacía de subsidios
SUBSIDIOS_TEMPLATE_PATH = os.path.join(BASE_DIR, "data", "planilla_subsidios.xlsx")

# ------------------------------
# Upload normal
# ------------------------------
@router.post("/upload-excel")
async def upload_excel(files: list[UploadFile] = File(...)):
    response = []
    for file in files:
        sheets = procesar_excel(file.file)
        response.append(construir_payload(file.filename, sheets))
    return response


# ------------------------------
# Upload streaming
# ------------------------------
@router.post("/upload-excel-stream")
async def upload_excel_stream(files: list[UploadFile] = File(...)):

    async def event_generator():
        for file in files:
            sheets = procesar_excel(file.file)
            payload = construir_payload(file.filename, sheets)
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@router.get("/descargar-planilla-subsidios/{filename}")
async def descargar_planilla_subsidios(filename: str):
    file_path = os.path.join(TMP_PATH, filename)
    if not os.path.exists(file_path):
        return {"error": "El archivo no existe o ya fue eliminado."}
    return FileResponse(
        path=file_path,
        filename="planilla_subsidios.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ------------------------------
# Validar GRT
# ------------------------------
@router.post("/validar-grt")
async def validar_grt(files: list[UploadFile] = File(...)):
    # Contador para medir el tiempo del flujo
    inicio = time.time()
    logger.info(f"⏱️ Inicio de validación: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")

    # Separar archivos de referencia de archivos a validar
    archivos_validar = []

    # Verificar que se suban ambas planillas de referencia obligatorias
    nombres_lower = [archivo.filename.lower() for archivo in files]

    tiene_macro   = any(N["macro"].lower() in n for n in nombres_lower)
    tiene_precios = any(N["precios_referencia"].lower() in n for n in nombres_lower)

    tipos_detectados = set()
    for n in nombres_lower:
        if N["precios_full"].lower() in n:
            tipos_detectados.add("precios_full")
        if N["post_nuevos_equipos"].lower() in n and N["transpuesta"].lower() in n:
            tipos_detectados.add("post_nuevos_equipos")
        if N["equipos_accesorios"].lower() in n:
            tipos_detectados.add("equipos_accesorios")
        if N["equipos_standalone"].lower() in n and N["sku_unico"].lower() in n:
            tipos_detectados.add("equipos_standalone")
        if N["financiamiento"].lower() in n and tiene_macro:
            tipos_detectados.add("financiamiento")
        if N["grt_pie"].lower() in n:
            tipos_detectados.add("grt_pie")
        if N["subsidios_claroup"].lower() in n:
            tipos_detectados.add("subsidios_claroup")
        if N["cargos_claroup"].lower() in n:
            tipos_detectados.add("cargos_claroup")
        if N["nuevos_equipos_claroup"].lower() in n:
            tipos_detectados.add("nuevos_equipos_claroup")

    REQUIERE_MACRO = {"precios_full", "post_nuevos_equipos", "financiamiento", "nuevos_equipos_claroup", "subsidios_claroup"}
    REQUIERE_PRECIOS = {"equipos_accesorios", "equipos_standalone", "grt_pie", "financiamiento", "subsidios_claroup"}

    necesita_macro   = bool(tipos_detectados & REQUIERE_MACRO)
    necesita_precios = bool(tipos_detectados & REQUIERE_PRECIOS)

    if necesita_macro and necesita_precios and not tiene_macro and not tiene_precios:
        return {"error": "El envío de las planillas macro y precios (nueva) es obligatorio para las validaciones seleccionadas."}
    elif necesita_macro and not tiene_macro:
        return {"error": "El envío de la planilla macro (envío) es obligatorio para las validaciones seleccionadas."}
    elif necesita_precios and not tiene_precios:
        return {"error": "El envío de la planilla Planilla_de_Precios_(nueva) es obligatorio para las validaciones seleccionadas."}

    for archivo in files:
        nombre_archivo = archivo.filename

        if N["macro"].lower() in nombre_archivo.lower():
            logger.info(f"Reemplazando planilla macro con: {nombre_archivo}")
            if os.path.exists(MACRO_PATH):
                logger.info(f"Eliminando la planilla en {MACRO_PATH}")
                os.remove(MACRO_PATH)
            tmp_path = os.path.join(TMP_PATH, nombre_archivo)
            with open(tmp_path, "wb") as buffer:
                shutil.copyfileobj(archivo.file, buffer)

            archivo.file.seek(0)
            shutil.move(tmp_path, MACRO_PATH)

        elif N["precios_referencia"].lower() in nombre_archivo.lower():
            logger.info(f"Reemplazando planilla de precios con: {nombre_archivo}")

            if os.path.exists(PRICES_PATH):
                logger.info(f"Eliminando la planilla en {PRICES_PATH}")
                os.remove(PRICES_PATH)

            tmp_path = os.path.join(TMP_PATH, nombre_archivo)

            with open(tmp_path, "wb") as buffer:
                shutil.copyfileobj(archivo.file, buffer)

            archivo.file.seek(0)

            shutil.move(tmp_path, PRICES_PATH)

            if tiene_macro and VALIDAR_FINANCIAMIENTO:
                archivos_validar.append(archivo)
            else:
                logger.info(f"Planilla de precios subida sin macro, se omite financiamiento")

        elif N["grt_pie"].lower() in nombre_archivo.lower():
            archivos_validar.append(archivo)

        else:
            archivos_validar.append(archivo)

    if not os.path.exists(MACRO_PATH):
        return {"error": "No se encontró la planilla macro en el servidor. Contacta al administrador."}

    # Verificar que no haya planillas no reconocidas antes de procesar
    no_reconocidas = []
    for archivo in archivos_validar:
        n = archivo.filename.lower()
        reconocida = (
            N["precios_full"].lower()           in n or
            (N["post_nuevos_equipos"].lower()   in n and N["transpuesta"].lower()  in n) or
            N["equipos_accesorios"].lower()     in n or
            (N["equipos_standalone"].lower()    in n and N["sku_unico"].lower()     in n) or
            N["financiamiento"].lower()         in n or
            N["grt_pie"].lower()                in n or
            N["subsidios_claroup"].lower()      in n or
            N["cargos_claroup"].lower()         in n or
            N["nuevos_equipos_claroup"].lower() in n
        )
        if not reconocida:
            no_reconocidas.append(archivo.filename)

    if no_reconocidas:
        lista = ", ".join(f'"{n}"' for n in no_reconocidas)
        return {
            "error": (
                f"No se puede iniciar la validación.\n\n"
                f"Las siguientes planillas no están en el sistema: {lista}.\n\n"
                f"Planillas válidas: Precios Full, Post Nuevos Equipos transpuesta, "
                f"Equipos Accesorios, Equipos Standalone, Financiamiento, GRT PIE, "
                f"Subsidios ClaroUp, Cargos ClaroUp, Nuevos Equipos ClaroUp."
            )
        }

    if not archivos_validar:
        if tiene_precios and not tiene_macro:
            return {"error": "Se necesita la planilla macro también para realizar la validación de financiamiento."}
        return {"error": "No se ingresaron suficientes planillas GRT para validar."}

    df_comp = leer_primera_hoja_desde_path(MACRO_PATH)

    resultados = []

    for archivo in archivos_validar:
        nombre_archivo = archivo.filename
        nombre_lower = nombre_archivo.lower()
        es_financiamiento = N["financiamiento"].lower() in nombre_lower

        if es_financiamiento:
            base_path = PRICES_PATH
            df_base = leer_primera_hoja_desde_path(PRICES_PATH)
        else:
            base_path = os.path.join(TMP_PATH, nombre_archivo)
            with open(base_path, "wb") as buffer:
                shutil.copyfileobj(archivo.file, buffer)
            df_base = leer_primera_hoja_desde_path(base_path)

        if N["precios_full"].lower() in nombre_lower:
            if not VALIDAR_PRECIOS_FULL:
                logger.info(f"Validación Precios Full desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Precios Full para {nombre_archivo}")
            if not os.path.exists(MACRO_PATH):
                resultado = {"error": "No se encontró la planilla macro en el servidor."}
            else:
                t0 = time.time()
                resultado = validar_full_reglas(df_base, df_comp)
                logger.info(f"⏱️ Precios Full: {time.time() - t0:.2f}s")
                resultado["tipo"] = "precios_full"

        elif N["post_nuevos_equipos"].lower() in nombre_lower and N["transpuesta"].lower() in nombre_lower:
            if not VALIDAR_POST_NUEVOS_EQUIPOS:
                logger.info(f"Validación Post Nuevos Equipos desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Post Nuevos Equipos para {nombre_archivo}")
            if not os.path.exists(MACRO_PATH):
                resultado = {"error": "No se encontró la planilla macro en el servidor."}
            else:
                t0 = time.time()
                resultado = validar_grt_reglas(df_base, df_comp)
                logger.info(f"⏱️ Post Nuevos Equipos: {time.time() - t0:.2f}s")
                resultado["tipo"] = "post_nuevos_equipos"

        elif N["equipos_accesorios"].lower() in nombre_lower:
            if not VALIDAR_EQUIPOS_ACCESORIOS:
                logger.info(f"Validación Equipos Accesorios desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Equipos Accesorios para {nombre_archivo}")
            if not os.path.exists(PRICES_PATH):
                resultado = {"error": "No se encontró la planilla de precios en el servidor."}
            else:
                t0 = time.time()
                df_precios = leer_hoja_desde_path(PRICES_PATH, "Accesorios + IOT+ BAM", fila_header=1)
                resultado = validar_equipos_accesorios(df_base, df_precios)
                logger.info(f"⏱️ Equipos Accesorios: {time.time() - t0:.2f}s")
                resultado["tipo"] = "equipos_accesorios"

        elif N["equipos_standalone"].lower() in nombre_lower and N["sku_unico"].lower() in nombre_lower:
            if not VALIDAR_EQUIPOS_STANDALONE:
                logger.info(f"Validación Equipos Standalone desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Equipos Standalone para {nombre_archivo}")
            if not os.path.exists(PRICES_PATH):
                resultado = {"error": "No se encontró la planilla de precios en el servidor."}
            else:
                t0 = time.time()
                info_precios = leer_planilla_precios_standalone(PRICES_PATH)
                resultado = validar_equipos_standalone(df_base, info_precios)
                logger.info(f"⏱️ Equipos Standalone: {time.time() - t0:.2f}s")
                resultado["tipo"] = "equipos_standalone"

        elif N["financiamiento"].lower() in nombre_lower:
            if not VALIDAR_FINANCIAMIENTO:
                logger.info(f"Validación Financiamiento desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Financiamiento para {nombre_archivo}")

            if not os.path.exists(PRICES_PATH):
                resultado = {"error": "No se encontró la planilla de precios en el servidor."}

            elif not os.path.exists(MACRO_PATH):
                resultado = {"error": "No se encontró la planilla macro en el servidor."}

            else:
                t0 = time.time()
                info_precios = leer_planilla_precios_financiamiento(PRICES_PATH)
                resultado = validar_financiamiento(
                    info_precios["df"],
                    info_precios,
                    df_comp
                )
                logger.info(f"⏱️ Financiamiento: {time.time() - t0:.2f}s")
                resultado["tipo"] = "financiamiento"

        elif N["grt_pie"].lower() in nombre_lower:
            if not VALIDAR_GRT_PIE:
                logger.info(f"Validación GRT PIE desactivada, se omite")
                continue
            logger.info(f"Usando reglas: GRT PIE para {nombre_archivo}")
            if not os.path.exists(PRICES_PATH):
                resultado = {"error": "No se encontró la planilla de precios en el servidor."}
            else:
                t0 = time.time()
                info_precios = leer_planilla_precios_financiamiento(PRICES_PATH)
                resultado = validar_grt_pie(info_precios, df_base)
                logger.info(f"⏱️ Validación GRT PIE: {time.time() - t0:.2f}s")
                resultado["tipo"] = "grt_pie"

        elif N["subsidios_claroup"].lower() in nombre_lower:
            if not VALIDAR_SUBSIDIOS_CLAROUP:
                logger.info(f"Validación Subsidios ClaroUp desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Subsidios ClaroUp para {nombre_archivo}")

            if not os.path.exists(PRICES_PATH):
                resultado = {"error": "No se encontró la planilla de precios en el servidor."}
            elif not os.path.exists(MACRO_PATH):
                resultado = {"error": "No se encontró la planilla macro en el servidor."}
            elif not os.path.exists(SUBSIDIOS_TEMPLATE_PATH):
                resultado = {"error": "No se encontró la plantilla de subsidios en el servidor."}
            else:
                t0 = time.time()
                cargo_activacion = leer_cargo_activacion_desde_precios(PRICES_PATH)
                resultado = validar_subsidios_claroup(df_base, cargo_activacion, df_comp)
                logger.info(f"⏱️ Validación Subsidios ClaroUp: {time.time() - t0:.2f}s")
                logger.info(f"Total filas en resumen: {len(resultado.get('resumen', []))}")
                resultado["tipo"] = "subsidios_claroup"

                # Generar planilla de evidencia en tmp
                planilla_id = f"planilla_subsidios_{uuid.uuid4().hex}.xlsx"
                planilla_output_path = os.path.join(TMP_PATH, planilla_id)
                try:
                    generar_planilla_subsidios(
                        template_path=SUBSIDIOS_TEMPLATE_PATH,
                        output_path=planilla_output_path,
                        resumen=resultado["resumen"]
                    )
                    resumen_id = uuid.uuid4().hex
                    resumen_path = os.path.join(TMP_PATH, f"resumen_{resumen_id}.json")
                    with open(resumen_path, "w", encoding="utf-8") as f:
                        json.dump(resultado["resumen"], f, ensure_ascii=False)
                    resultado["planilla_subsidios_id"] = planilla_id
                    logger.info(f"Planilla de subsidios generada: {planilla_output_path}")
                except Exception as e:
                    logger.error(f"Error generando planilla de subsidios: {e}")
                    resultado["planilla_subsidios_id"] = None

        elif N["cargos_claroup"].lower() in nombre_lower:
            if not VALIDAR_CARGOS_CLAROUP:
                logger.info(f"Validación Cargos ClaroUp desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Cargos ClaroUp para {nombre_archivo}")
            t0 = time.time()
            resultado = validar_cargos_claroup(df_base)
            logger.info(f"⏱️ Validación Cargos ClaroUp: {time.time() - t0:.2f}s")
            resultado["tipo"] = "cargos_claroup"

        elif N["nuevos_equipos_claroup"].lower() in nombre_lower:
            if not VALIDAR_NUEVOS_EQUIPOS_CLAROUP:
                logger.info("Validación Nuevos Equipos ClaroUp desactivada, se omite")
                continue
            logger.info(f"Usando reglas: Nuevos Equipos ClaroUp para {nombre_archivo}")
            if not os.path.exists(MACRO_PATH):
                resultado = {"error": "No se encontró la planilla macro en el servidor."}
            else:
                t0 = time.time()
                resultado = validar_nuevos_equipos_claroup(df_base, df_comp)
                logger.info(f"⏱️ Validación Nuevos Equipos ClaroUp: {time.time() - t0:.2f}s")
                resultado["tipo"] = "nuevos_equipos_claroup"

        elif N["post_nuevos_equipos"].lower() in nombre_lower and N["transpuesta"].lower() not in nombre_lower:
            logger.info(f"Planilla ignorada (se requiere versión transpuesta): {nombre_archivo}")
            if os.path.exists(base_path):
                os.remove(base_path)
            continue

        else:
            logger.info(f"Planilla no reconocida, se omite: {nombre_archivo}")
            if os.path.exists(base_path):
                os.remove(base_path)
            continue

        if "error" not in resultado:
            tiene_errores = resultado.get("total_error", 0) > 0
            destino = STORAGE_INVALIDAS if tiene_errores else STORAGE_VALIDAS
            destino_path = os.path.join(destino, nombre_archivo)
            if os.path.exists(base_path):
                shutil.copy2(base_path, destino_path)
            else:
                logger.warning(f"No se pudo guardar en storage, archivo temporal no encontrado: {base_path}")
            logger.info(f"Archivo guardado en: {destino_path}")

        if not es_financiamiento and os.path.exists(base_path):
            os.remove(base_path)
            logger.info(f"Archivo temporal eliminado: {base_path}")

        resultados.append({
            "archivo": nombre_archivo,
            "resultado": resultado
        })

    duracion = time.time() - inicio
    logger.info(f"⏱️ Duración total del flujo: {duracion:.2f} segundos")

    return {
        "validaciones": resultados,
        "duracion_segundos": round(duracion, 2)  
    }

# ------------------------------
# Endpoint de paginación
# ------------------------------
@router.get("/resumen-subsidios/{resumen_id}")
async def obtener_resumen_subsidios(resumen_id: str, page: int = 1, page_size: int = 500, solo_errores: bool = False):
    resumen_path = os.path.join(TMP_PATH, f"resumen_{resumen_id}.json")
    if not os.path.exists(resumen_path):
        return {"error": "Resumen no encontrado"}
    
    with open(resumen_path, "r", encoding="utf-8") as f:
        resumen = json.load(f)
    
    if solo_errores:
        resumen = [r for r in resumen if r["estado"] == "Con error" or len(r.get("alertas", [])) > 0]
    
    total = len(resumen)
    inicio = (page - 1) * page_size
    fin = inicio + page_size
    
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "filas": resumen[inicio:fin]
    }