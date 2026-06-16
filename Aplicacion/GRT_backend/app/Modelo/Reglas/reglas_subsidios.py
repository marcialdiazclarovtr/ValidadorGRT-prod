# Reglas validación subsidios:

# Para realizar esta validación se usan 3 planillas: "20260128 Subsidio ClaroUp v1.xlsx", "20260128_Planilla_de_Precios_(nueva)_v1.xlsx" y "20260128 W5 CR479 macro (envío) v1.xlsx"

# Al realizar esta validación se creará una nueva planilla con las siguientes columnas:

#   Cargo Activación    
#   Subsidio Claro Up 
#   Subsidio 2 GRT  
#   Valor Full      
#   Valor full sin iva  
#   Total sin iva       
#   Total              
#   Resultado          

# Aquí se describe como se llena cada una de esas columnas desde valores de las planillas de precios, de subsidios y macro:

#   Cargo Activación    = "Pie + 12 Cuotas" de la planilla de precios según OR
#   Subsidio Claro Up   = DISCOUNT_RATE de la planilla de subsidios
#   Subsidio 2 GRT      = columna "Subs 2" de la macro
#   Valor Full          = columna "valor full" de la macro
#   Valor full sin iva  = Valor Full / 1.19
#   Total sin iva       = Valor full sin iva - Subsidio 2 GRT - Subsidio Claro Up
#   Total               = Total sin iva * 1.19 (redondeado a entero)
#   Resultado           = Total - Cargo Activación

# Estas planillas se identificarán desde el controlador detectando las siguientes subcadenas en los nombres de los excel de input:

# - "Subsidio ClaroUp": Planilla de subsidios
# - "Planilla_de_Precios": Planilla de precios
# - "macro (envío)": Planilla macro

# Regla 1:

# Las fechas de las columnas deben seguir el siguiente formato: 

# Planilla macro:

# Columna “EFFECTIVE_DATE”: AAAA-MM-DD 00:00:00
# Columna “EXPIRATION DATE“: DD-MM-AAAA 00:00:00

# Planilla subsidio claroup:

# Columna “EFFECTIVE_DATE”: DD-MM-AAAA 00:00:00 
# Columna “EXPIRATION_DATE”: DD-MM-AAAA 00:00:00

# ***************************************************************************************************

""" Dado que pandas, al recibir una fecha desde excel, automaticamente cambia el orden de DD-MM-AAAA a AAAA-MM-DD y agrega 00:00:00 si es que no está, se tuvo que simplificar la validación de esta forma:

En vez de validar el formato exacto (DD-MM-AAAA vs AAAA-MM-DD), simplemente verificamos que el valor de cada celda de fecha sea parseable como una fecha válida usando pd.to_datetime(). Si el valor está vacío, es texto sin sentido o tiene caracteres raros, se reporta error. Si es cualquier fecha reconocible, pasa.

Ejemplos:

Pasan ✅: "2026-03-10 04:00:00", "10-03-2026 04:00:00", "2026/03/10", objeto datetime de pandas
No pasan ❌: "hola", "N/A", "$$$$", vacío, None, '11-1996-02 01:00:00' (tiene el año al medio) """ 

# ***************************************************************************************************

# Regla 2:

# Validar que el valor de la columna "Resultado" (Total - Cargo Activación) es 0 al final de la validación

# Estos son los pasos a seguir para validar la regla 2:

# Abrimos la planilla de precios

# Buscamos las columnas "Pie + 12 cuotas" en la fila 3, columnas AM, AP y AS, debajo de Max Libre, y copiamos el "PIE + 12 cuotas" según el OR que estamos buscando (2, 3, 4, 5 o 6) en la columna "Cargo Activación" de la planilla nueva en formato "792000" (sin $ ni .)

# *** Para esta validacion solo revisamos con valores OR 2, 3, 4, 5 y 6

# *** Si el PIE + 12 cuotas aparece como no disponible se ignora para la validacion y se alerta como advertencia

# *** Para esta validación hay que rellenar una plantilla

# Abrimos planilla subsidios

# Buscamos el SKU que necesitamos, buscamos la fila con Offer Rank = 2, EQU_COMMITME_DURATION = 24 y SALE_CHANNEL = CAC, y buscamos el DISCOUNT_RATE, si está vacío buscamos en la siguiente fila, hay que buscar el discount para Order activity = P, PI y R

# En la plantilla, llenamos las columnas "Order Activity", "SKU", "OR" con los valores de la planilla de subsidios

# El valor DISCOUNT_RATE de la planilla de subsidios lo ponemos en la columna "Subsidio Claro UP" de la planilla nueva

# Para llenar los valores de las columnas "Subsidio 2 GRT" y "Valor Full" de la planilla nueva abrimos la macro y buscamos las columnas "Subs 2" y "valor full"

# Después tomamos el valor full que obtuvimos recién en el paso 7 y lo dividimos por 1,19 para llenar la columna "Valor full sin iva"

# Para llenar la columna "Total sin iva" tomamos el valor de "Valor full" y le restamos el valor de "Subsidio 2 GRT" y luego le restamos el de "Subsidio claro up"

# Después, tomamos el resultado que obtuvimos en la columna "Total sin iva" y lo multiplicamos por 1,19 para llenar la columna "Total"

# Finalmente, tomamos el valor de la columna "Cargo activación" y le restamos el de la columna "Total" que llenamos recién para llenar la columna "Resultado", si resultado da distinto de 0 arrojamos un error en el front.

# *** Hay que empezar con los SKU de la planilla de precios (nueva), pero si el Pie + 12 cuotas no está disponible, no tomamos en cuenta ese SKU

# Regla 3:

# Las fechas de expiración de las columnas "EXPIRATION DATE" (planilla macro) y "EXPIRATION_DATE" (planilla de subsidios) debe ser igual o posterior a la fecha actual pero sumándole un año.

# Es decir, si la fecha actual es 10-03-2026 04:00:00 (en el caso de "EXPIRATION_DATE" (planilla de subsidios), en el caso de "EXPIRATION DATE" (planilla macro) sería 10-03-2026 4:00:00), la fecha de EXPIRATION_DATE debe ser igual a 10-03-2027 04:00:00 o posterior

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("uvicorn")

from datetime import datetime, timedelta
from collections import Counter

# ---------------------------------
# Limitador de logs de debug
# ---------------------------------
LOG_LIMIT = 5
_log_counts = {}

def debug_limit(key: str, message: str):
    count = _log_counts.get(key, 0)

    if count < LOG_LIMIT:
        logger.info(message)
        _log_counts[key] = count + 1

# OR → índice de columna (0-based) para "Pie + 12 Cuotas" en la planilla de precios
# AN=38 (MAX L Libre OR2), AQ=41 (MAX XL Libre OR3), AT=44 (MAX Libre Pro OR4-5-6)
OR_A_IDX_COLUMNA = {
    2: 38,
    3: 41,
    4: 44,
    6: 44,
}

OR_VALIDOS = [2, 3, 4, 6]
ORDER_ACTIVITIES = ["P", "PI", "R"]
NO_DISPONIBLE = "No Disp"

# ---------------------------------
# Flags de validación
# ---------------------------------
VALIDAR_REGLA_FECHAS = True
VALIDAR_REGLA_EXPIRACION = True

# Convierte tipos de NumPy (np.integer, np.floating) a tipos nativos de Python (int, float) para que puedan serializarse a JSON. También convierte NaN/None a None.
def to_python_type(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value

# Multiplica un float por 1 y lo redondea al entero más cercano usando el método "round half up" (0.5 → 1, no el redondeo bancario de Python).
def redondear_total(valor: float) -> int:
    return int(np.floor(valor + 0.5))

# ------------------------------
# Lectura planilla de precios
# ------------------------------
def leer_cargo_activacion_desde_precios(path: str) -> Dict:
    """
    Lee la hoja 'Planilla de Precios' y extrae el Cargo Activación
    (Pie + 12 Cuotas) por SKU y OR.

    Estructura de la hoja:
      Fila 1 (idx 0): encabezado general "ClaroUp (...)"
      Fila 2 (idx 1): grupos "MAX L Libre (2)", "MAX XL Libre (3)", "MAX Libre Pro (4-5-6)"
      Fila 3 (idx 2): subcolumnas "Pie", "12 Cuotas", "Pie + 12 Cuotas"
      Fila 4+ (idx 3+): datos, SKU en columna G (índice 6)

    Columnas Pie + 12 Cuotas: AM (38), AP (41), AS (44)
    """
    df_raw = pd.read_excel(path, sheet_name="Planilla de Precios", header=None)

    col_sku_idx = 6  # columna G

    # Datos desde fila 4 (índice 3) en adelante
    df_datos = df_raw.iloc[3:].dropna(how='all').reset_index(drop=True)
    """ debug_limit(
        "precios_total_filas",
        f"[DEBUG] Total filas en df_datos (planilla de precios): {len(df_datos)}"
    ) """

    resultado = {}  # { sku: { "cargos": { or_val: ... }, "datos_fila": { ... } } }

    for _, fila in df_datos.iterrows():
        sku = fila.iloc[col_sku_idx]
        if pd.isna(sku):
            continue
        sku = str(sku).strip()
        if not sku:
            continue

        def get_val(idx):
            if idx >= len(fila):
                return None
            v = fila.iloc[idx]
            return None if pd.isna(v) else str(v).strip()

        datos_fila = {
            "generacion":      get_val(0),   # A
            "up":              get_val(1),   # B
            "phone_protect":   get_val(2),   # C
            "segmento":        get_val(3),   # D
            "status":          get_val(4),   # E
            "sku":             get_val(6),   # G
            "marca":           get_val(8),   # I
            "modelo_master":   get_val(9),   # J
            "modelo_tecnico":  get_val(10),  # K
            "modelo_comercial":get_val(11),  # L
            "valor_full_plan": get_val(12),  # M
        }

        cargos = {}
        for or_val in OR_VALIDOS:
            idx_col = OR_A_IDX_COLUMNA[or_val]
            if idx_col >= len(fila):
                cargos[or_val] = None
                continue
            valor = fila.iloc[idx_col]
            if pd.isna(valor) or str(valor).strip().upper() == NO_DISPONIBLE.upper():
                cargos[or_val] = None
            else:
                try:
                    valor_limpio = str(valor).replace("$", "").replace(".", "").replace(",", "").strip()
                    cargos[or_val] = int(float(valor_limpio))
                except (ValueError, TypeError):
                    cargos[or_val] = None

        resultado[sku] = {
            "cargos": cargos,
            "datos_fila": datos_fila
        }

    """ debug_limit(
        "precios_total_skus",
        f"[DEBUG] Total SKUs leídos desde planilla de precios: {len(resultado)}"
    ) """

    return resultado


# ------------------------------
# Lectura planilla de subsidios
# ------------------------------
def leer_subsidios(df_subsidios: pd.DataFrame) -> Dict:
    """
    Extrae DISCOUNT_RATE por (SKU, OR, Order Activity)
    filtrando por EQU_COMMITME_DURATION = 24 y SALE_CHANNEL = CAC.

    Retorna: { (sku, or_val, order_activity): discount_rate }
    """
    columnas_requeridas = {
        "SKU", "OFFER_RANK", "EQU_COMMITME_DURATION",
        "SALE_CHANNEL", "Order Activity", "DISCOUNT_RATE"
    }
    faltantes = columnas_requeridas - set(df_subsidios.columns)
    if faltantes:
        return {"error": f"A la planilla de subsidios le faltan columnas: {', '.join(sorted(faltantes))}"}

    resultado = {}

    df_filtrado = df_subsidios[
        (df_subsidios["EQU_COMMITME_DURATION"].astype(str).str.strip() == "24") &
        (df_subsidios["SALE_CHANNEL"].astype(str).str.strip().str.upper() == "CAC")
    ]

    for _, fila in df_filtrado.iterrows():
        sku = str(fila["SKU"]).strip()
        order_activity = str(fila["Order Activity"]).strip().upper()
        discount_rate = fila["DISCOUNT_RATE"]

        try:
            or_val = int(float(fila["OFFER_RANK"]))
        except (ValueError, TypeError):
            continue

        if or_val not in OR_VALIDOS:
            continue
        if order_activity not in ORDER_ACTIVITIES:
            continue
        if pd.isna(discount_rate):
            continue

        clave = (sku, or_val, order_activity)
        # Solo tomar el primer valor encontrado por clave
        if clave not in resultado:
            resultado[clave] = float(discount_rate)

    return resultado

# ------------------------------
# Lectura planilla macro
# ------------------------------
def leer_macro_subsidios(df_macro: pd.DataFrame) -> Dict:
    """
    Extrae Subs 2 y Valor Full por (SKU, OR, Order Activity) desde la macro.

    Retorna: { (sku, or_val, order_activity): { "subs2": ..., "valor_full": ... } }
    """
    columnas_requeridas = {"EQUIPMENT_SKU", "OR", "ORDER_ACTIVITY", "Subs 2", "valor full"}
    faltantes = columnas_requeridas - set(df_macro.columns)
    if faltantes:
        return {"error": f"A la planilla macro le faltan columnas: {', '.join(sorted(faltantes))}"}

    resultado = {}

    for _, fila in df_macro.iterrows():
        sku = str(fila["EQUIPMENT_SKU"]).strip()
        order_activity = str(fila["ORDER_ACTIVITY"]).strip().upper()
        subs2 = fila["Subs 2"]
        valor_full = fila["valor full"]

        try:
            or_val = int(float(fila["OR"]))
        except (ValueError, TypeError):
            continue

        if or_val not in OR_VALIDOS:
            continue
        if order_activity not in ORDER_ACTIVITIES:
            continue

        clave = (sku, or_val, order_activity)
        if clave not in resultado:
            resultado[clave] = {
                "subs2": to_python_type(subs2),
                "valor_full": to_python_type(valor_full)
            }

    return resultado


# ------------------------------
# Validación Regla 1: fechas
# ------------------------------
def validar_formato_fecha(valor, nombre_columna: str) -> Optional[str]:
    if pd.isna(valor) or str(valor).strip() == "":
        return f"La columna '{nombre_columna}' tiene un valor vacío (Regla 1)"
    try:
        pd.to_datetime(str(valor))
        return None
    except:
        return f"La columna '{nombre_columna}' tiene un valor inválido: '{valor}' (Regla 1)"


def validar_fechas_macro(df_macro: pd.DataFrame) -> list:
    errores = []
    for col in ["EFFECTIVE_DATE", "EXPIRATION DATE"]:
        if col not in df_macro.columns:
            continue
        
        # Convertimos la columna a fecha
        convertidas = pd.to_datetime(df_macro[col].astype(str), format='mixed', dayfirst=True, errors='coerce')
        
        for i, (original, convertida) in enumerate(zip(df_macro[col], convertidas)):
            # 1. Definir el SKU de forma segura antes de usarlo
            if "EQUIPMENT_SKU" in df_macro.columns:
                sku_valor = df_macro.iloc[i]["EQUIPMENT_SKU"]
            else:
                sku_valor = "SIN SKU"

            # 2. Validar si la conversión falló (Regla 1)
            # Si el original no es nulo pero la conversión dio NaT, hay un error de formato
            if pd.isna(convertida) and not pd.isna(original) and str(original).strip() != "":
                errores.append({
                    "fila": i + 2,
                    "error": f"El SKU {sku_valor} no cumple con la regla 1 (Formato de fecha inválido en {col})"
                })
    return errores

def validar_expiracion_macro(df_macro: pd.DataFrame) -> list:
    errores = []
    conteo_total = 0
    primer_error = None
    primer_fila = None

    for i, (_, fila) in enumerate(df_macro.iterrows()):
        numero_fila = i + 2
        if "EXPIRATION DATE" not in df_macro.columns:
            break
        valor = fila.get("EXPIRATION DATE")
        err = validar_expiracion_minima(valor, "DD-MM-AAAA", "EXPIRATION DATE")
        if err:
            conteo_total += 1
            if primer_error is None:
                primer_error = err
                primer_fila = numero_fila

    if primer_error:
        errores.append({
            "fila": primer_fila,
            "error": primer_error,
            "total_ocurrencias": conteo_total,
            "planilla": "macro"
        })

    return errores

def validar_fechas_subsidios(df_subsidios: pd.DataFrame) -> list:
    errores = []
    for col in ["EFFECTIVE_DATE", "EXPIRATION_DATE"]:
        if col not in df_subsidios.columns:
            continue
        
        # Conversión segura
        convertidas = pd.to_datetime(df_subsidios[col].astype(str), format='mixed', dayfirst=True, errors='coerce')
        
        for i, (original, convertida) in enumerate(zip(df_subsidios[col], convertidas)):
            # Si el dato original existe pero la conversión falló
            if pd.isna(convertida) and not pd.isna(original) and str(original).strip() != "":
                
                # Verificamos si la columna existe para evitar un KeyError
                if "SKU" in df_subsidios.columns:
                    valor_sku = df_subsidios.iloc[i]["SKU"]
                else:
                    valor_sku = "N/A"
                
                errores.append({
                    "fila": i + 2, 
                    "error": f"El SKU '{valor_sku}' no cumple con la Regla 1 (Formato de fecha inválido en {col})"
                })
    return errores

def validar_expiracion_subsidios(df_subsidios: pd.DataFrame) -> list:
    errores = []
    conteo_total = 0
    primer_error = None
    primer_fila = None

    for i, (_, fila) in enumerate(df_subsidios.iterrows()):
        numero_fila = i + 2
        if "EXPIRATION_DATE" not in df_subsidios.columns:
            break
        valor = fila.get("EXPIRATION_DATE")
        err = validar_expiracion_minima(valor, "DD-MM-AAAA", "EXPIRATION_DATE")
        if err:
            conteo_total += 1
            if primer_error is None:
                primer_error = err
                primer_fila = numero_fila

    if primer_error:
        errores.append({
            "fila": primer_fila,
            "error": primer_error,
            "total_ocurrencias": conteo_total,
            "planilla": "subsidios"
        })

    return errores

# ------------------------------
# Validación Regla 3: expiración >= hoy + 1 año
# ------------------------------
def validar_expiracion_minima(valor, formato: str, nombre_columna: str) -> Optional[str]:

    if pd.isna(valor) or str(valor).strip() == "":
        return f"La columna '{nombre_columna}' tiene un valor vacío (Regla 3)"

    valor_str = re.sub(r'\s+', ' ', str(valor).strip())

    try:
        fecha = pd.to_datetime(str(valor), format='mixed', dayfirst=True)
    except Exception:
        return f"No se pudo interpretar la fecha '{valor_str}' en la columna '{nombre_columna}' (Regla 3)"

    fecha_minima = datetime.now() + timedelta(days=365)

    if fecha < fecha_minima:
        return (
            f"La fecha '{valor_str}' en '{nombre_columna}' es menor a la mínima permitida "
            f"({fecha_minima.strftime('%d-%m-%Y %H:%M:%S')}) (Regla 3)"
        )

    return None


# ------------------------------
# Validación principal
# ------------------------------
def validar_subsidios_claroup(
    df_subsidios: pd.DataFrame,
    cargo_activacion_por_sku: Dict,   # resultado de leer_cargo_activacion_desde_precios
    df_macro: pd.DataFrame
) -> Dict[str, Any]:

    resumen = []
    alertas_globales = []

    # --- Regla 1: validar fechas ---
    errores_fecha_macro = []
    errores_fecha_subsidios = []

    if VALIDAR_REGLA_FECHAS:
        errores_fecha_macro = validar_fechas_macro(df_macro)
        errores_fecha_subsidios = validar_fechas_subsidios(df_subsidios)

    """ else:
        logger.info(f"[DEBUG] Validación de regla 1 (formato fechas) desactivada") """

    for e in errores_fecha_macro:
        resumen.append({
            "sku": "—",
            "nombre": "—",
            "numero_fila": e["fila"],
            "order_activity": "—",
            "or_val": "—",
            "estado": "Con error",
            "alertas": [],
            "detalle_error": {
                "errores": [f"Macro fila {e['fila']}: {e['error']}"],
                "cargo_activacion": None,
                "subsidio_claroup": None,
                "subsidio_2_grt": None,
                "valor_full": None,
                "valor_full_sin_iva": None,
                "total_sin_iva": None,
                "total": None,
                "resultado": None,
            }
        })

    for e in errores_fecha_subsidios:
        resumen.append({
            "sku": "—",
            "nombre": "—",
            "numero_fila": e["fila"],
            "order_activity": "—",
            "or_val": "—",
            "estado": "Con error",
            "alertas": [],
            "detalle_error": {
                "errores": [f"Subsidio fila {e['fila']}: {e['error']}"],
                "cargo_activacion": None,
                "subsidio_claroup": None,
                "subsidio_2_grt": None,
                "valor_full": None,
                "valor_full_sin_iva": None,
                "total_sin_iva": None,
                "total": None,
                "resultado": None,
            }
        })

    # --- Regla 2: validar cálculo ---
    subsidios = leer_subsidios(df_subsidios)
    if isinstance(subsidios, dict) and "error" in subsidios:
        return subsidios

    macro_data = leer_macro_subsidios(df_macro)
    if isinstance(macro_data, dict) and "error" in macro_data:
        return macro_data

    SKU_DEBUG = "70015676"

    # Claves en subsidios para ese SKU
    claves_sub = [k for k in subsidios.keys() if k[0] == SKU_DEBUG]
    """ debug_limit(
        "debug_subsidios_claves",
        f"[DEBUG] Claves en subsidios para {SKU_DEBUG}: {claves_sub}"
    ) """

    # Claves en macro para ese SKU
    claves_mac = [k for k in macro_data.keys() if k[0] == SKU_DEBUG]
    """ debug_limit(
        "debug_macro_claves",
        f"[DEBUG] Claves en macro para {SKU_DEBUG}: {claves_mac}"
    ) """

    # Cargo activación para ese SKU
    cargo_debug = cargo_activacion_por_sku.get(SKU_DEBUG)
    """ debug_limit(
        "debug_cargo_activacion",
        f"[DEBUG] Cargo activación para {SKU_DEBUG}: {cargo_debug}"
    ) """

    """ debug_limit(
        "debug_total_skus",
        f"[DEBUG] Total SKUs en cargo_activacion_por_sku: {len(cargo_activacion_por_sku)}"
    ) """

    for sku, info_sku in cargo_activacion_por_sku.items():
        cargos_por_or = info_sku["cargos"]
        datos_fila = info_sku["datos_fila"]
        for or_val in OR_VALIDOS:
            cargo_activacion = cargos_por_or.get(or_val)

            # Si Pie + 12 Cuotas no está disponible, alerta global y saltar
            if cargo_activacion is None:
                alertas_globales.append(
                    f"SKU {sku} OR {or_val}: Pie + 12 Cuotas no disponible, se omite la validación"
                )
                continue

            for order_activity in ORDER_ACTIVITIES:
                clave = (sku, or_val, order_activity)
                alertas_fila = []
                errores_fila = []

                # Buscar Subsidio ClaroUp
                subsidio_claroup = subsidios.get(clave)
                if subsidio_claroup is None:
                    alertas_fila.append(
                        f"No se encontró DISCOUNT_RATE para SKU={sku}, OR={or_val}, "
                        f"Order Activity={order_activity} con SALE_CHANNEL=CAC y EQU_COMMITME_DURATION=24"
                    )

                # Buscar Subs 2 y Valor Full desde macro
                macro_fila = macro_data.get(clave)
                if macro_fila is None:
                    alertas_fila.append(
                        f"No se encontró fila en macro para SKU={sku}, OR={or_val}, "
                        f"Order Activity={order_activity}"
                    )
                    subs2 = None
                    valor_full = None
                else:
                    subs2 = macro_fila["subs2"]
                    valor_full = macro_fila["valor_full"]

                # 👇 AQUÍ va el debug
                """ if sku == SKU_DEBUG:
                    debug_limit(
                        "debug_calculo_sku",
                        f"[DEBUG] {sku} | OR{or_val} | {order_activity} → "
                        f"cargo={cargo_activacion}, "
                        f"subsidio_claroup={subsidio_claroup}, "
                        f"macro_fila={macro_fila}"
                    ) """

                # Calcular columnas derivadas solo si tenemos todos los datos
                valor_full_sin_iva = None
                total_sin_iva = None
                total = None
                resultado_val = None

                if valor_full is not None and subs2 is not None and subsidio_claroup is not None:
                    valor_full_sin_iva = valor_full / 1.19
                    total_sin_iva = valor_full_sin_iva - subs2 - subsidio_claroup
                    total = redondear_total(total_sin_iva * 1.19)
                    resultado_val = total - cargo_activacion

                    if resultado_val != 0:
                        errores_fila.append(
                            f"El SKU '{sku}' no cumple con la Regla 2 (revisar reglas mas arriba)"
                        )

                else:
                    faltantes = []
                    if subsidio_claroup is None:
                        faltantes.append("Subsidio Claro up")
                    if subs2 is None:
                        faltantes.append("Subsidio 2 GRT")
                    if valor_full is None:
                        faltantes.append("Valor Full")
                    
                    errores_fila.append(
                        f"No se pudieron calcular Valor full sin iva, Total sin iva, Total y Resultado "
                        f"porque faltan los siguientes datos: {', '.join(faltantes)} (Regla 2)"
                    )

                estado = "Con error" if errores_fila else "OK"

                entrada = {
                    "sku": sku,
                    "nombre": sku,
                    "numero_fila": f"{sku} | OR{or_val} | {order_activity}",
                    "order_activity": order_activity,
                    "or_val": or_val,
                    "estado": estado,
                    "alertas": alertas_fila,
                    "cargo_activacion": to_python_type(cargo_activacion),      
                    "subsidio_claroup": to_python_type(subsidio_claroup),      
                    "subsidio_2_grt": to_python_type(subs2),                   
                    "valor_full": to_python_type(valor_full),    
                }

                if errores_fila:
                    entrada["detalle_error"] = {
                        "errores": errores_fila,
                        "cargo_activacion": to_python_type(cargo_activacion),
                        "subsidio_claroup": to_python_type(subsidio_claroup),
                        "subsidio_2_grt": to_python_type(subs2),
                        "valor_full": to_python_type(valor_full),
                        "valor_full_sin_iva": to_python_type(valor_full_sin_iva),
                        "total_sin_iva": to_python_type(total_sin_iva),
                        "total": to_python_type(total),
                        "resultado": to_python_type(resultado_val),
                        "pie_12_cuotas": to_python_type(cargo_activacion),  # mismo valor
                        "datos_planilla": datos_fila,
                    }
                else:
                    entrada["detalle_error"] = None

                resumen.append(entrada)

    # logger.info(f"[DEBUG] Total entradas en resumen antes de retornar: {len(resumen)}")
    # logger.info(f"[DEBUG] Entradas Regla 1 (fechas): {len(errores_fecha_macro) + len(errores_fecha_subsidios)}")

    # --- Regla 3: validar expiración ---
    errores_exp_macro = []
    errores_exp_subsidios = []

    if VALIDAR_REGLA_EXPIRACION:

        errores_exp_macro = validar_expiracion_macro(df_macro)
        errores_exp_subsidios = validar_expiracion_subsidios(df_subsidios)

    """ else:
        logger.info("[DEBUG] Validación de regla 3 (expiración mínima) desactivada") """

    for e in errores_exp_macro:
        resumen.append({
            "sku": "—",
            "nombre": "—",
            "numero_fila": e["fila"],
            "order_activity": "—",
            "or_val": "—",
            "estado": "Con error",
            "alertas": [],
            "detalle_error": {
                "errores": [f"Macro fila {e['fila']}: {e['error']}"],
                "total_ocurrencias": e.get("total_ocurrencias"),
                "planilla": e.get("planilla"),
            }
        })

    for e in errores_exp_subsidios:
        resumen.append({
            "sku": "—",
            "nombre": "—",
            "numero_fila": e["fila"],
            "order_activity": "—",
            "or_val": "—",
            "estado": "Con error",
            "alertas": [],
            "detalle_error": {
                "errores": [f"Subsidio fila {e['fila']}: {e['error']}"],
                "total_ocurrencias": e.get("total_ocurrencias"),
                "planilla": e.get("planilla"),
            }
        })

    # Resumen de tipos de error
    tipos_error = Counter()
    ejemplos_por_tipo = {}

    for r in resumen:
        if r["estado"] == "Con error" and r.get("detalle_error"):
            for err in r["detalle_error"].get("errores", []):
                tipos_error[err[:80]] += 1
                if err[:80] not in ejemplos_por_tipo:
                    ejemplos_por_tipo[err[:80]] = r.get("sku", "—")

    # logger.info(f"[RESUMEN ERRORES] Total filas en resumen: {len(resumen)}")
    # logger.info(f"[RESUMEN ERRORES] Total con error: {sum(1 for r in resumen if r['estado'] == 'Con error')}")
    # for tipo, count in tipos_error.most_common(20):
        # logger.info(f"[RESUMEN ERRORES] ({count}x) SKU ejemplo={ejemplos_por_tipo[tipo]} | {tipo}")

    return {
        "tipo": "subsidios_claroup",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "alertas_globales": alertas_globales,
        "resumen": resumen
    }
