# reglas_precios_full.py

# Módulo de validación de reglas para precios full

# La validación se realiza con las planillas "20260128 CW5 Planilla_Precios Full v1" y "20260128 W5 CR479 macro (envío) v1"

# Reglas a validar para cada fila:

# Regla 1:

# El precio que aparece en la columna FINAL S/IVA, multiplicado por 1.19, debe ser igual al precio que aparece en la columna C/iva.

# Regla 2:

# Validar que la primera fila con el mismo SKU, el cual en la planilla de precios full está en la columna "SKU" y en la planilla macro está en la columna "EQUIPMENT_SKU" en la planilla macro en la columna "valor full" tenga el mismo precio que el de la columna C/iva

# Regla 3: 

# Si el nombre en la columna "Nombre" contiene la palabra “ClaroUp”, deben haber 3 repeticiones de ese SKU.

import pandas as pd
import numpy as np
from typing import Dict, Any, List


# =========================
# Utilidades
# =========================

def to_python_type(value):
    """Convierte tipos numpy/pandas a tipos nativos de Python"""
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def calcular_precio_con_iva(precio: float, tasa_iva: float = 0.19) -> int:
    """Calcula precio con IVA con redondeo estándar"""
    return int(np.floor(precio * (1 + tasa_iva) + 0.5))

def sanitizar_fila(fila: dict) -> dict:
    return {k: to_python_type(v) for k, v in fila.items()}

# =========================
# Validación de columnas
# =========================

def validar_columnas_requeridas(
    df_full: pd.DataFrame,
    df_macro: pd.DataFrame
) -> Dict[str, str] | None:
    """
    Valida que ambas planillas tengan las columnas mínimas necesarias.
    """

    columnas_full = {
        "SKU",
        "FINAL S/IVA",
        "C/iva",
        "Nombre",
        "Equipment Rank Value"
    }

    columnas_macro = {
        "EQUIPMENT_SKU",
        "valor full"
    }

    faltantes_full = columnas_full - set(df_full.columns)
    faltantes_macro = columnas_macro - set(df_macro.columns)

    if columnas_full - set(df_full.columns):
        return {"error": f"A la planilla de precios full le faltan las siguientes columnas requeridas: {', '.join(sorted(faltantes_full))}"}

    if columnas_macro - set(df_macro.columns):
        return {"error": f"A la planilla macro le faltan las siguientes columnas requeridas: {', '.join(sorted(faltantes_macro))}"}

    return None


# =========================
# Función principal
# =========================

def validar_precios_full(
    df_full: pd.DataFrame,
    df_macro: pd.DataFrame
) -> Dict[str, Any]:
    """
    Valida reglas de precios full.

    Reglas:

    Regla 1:
    FINAL S/IVA * 1.19 debe ser igual a C/iva

    Regla 2:
    Para cada SKU, el precio C/iva debe coincidir con el valor full
    de la PRIMERA ocurrencia del SKU en la planilla macro.

    Regla 3:
    Si Nombre contiene "ClaroUp":
    - Deben existir 3 filas con el mismo SKU
    - Nombres esperados:
        ClaroUp {codigo_modelo}
        ClaroUp PI {codigo_modelo}
        ClaroUp FIDE {codigo_modelo}
    - Equipment Rank Value deben ser consecutivos
    - El resto de las columnas deben ser iguales
    """

    # -----------------------
    # Validar columnas
    # -----------------------

    error = validar_columnas_requeridas(df_full, df_macro)
    if error:
        return error

    # -----------------------
    # Preparar macro (SKU único)
    # -----------------------

    df_macro_unico = df_macro.drop_duplicates(
        subset=["EQUIPMENT_SKU"],
        keep="first"
    ).set_index("EQUIPMENT_SKU")

    resumen = []

    # -----------------------
    # Iteración por SKU
    # -----------------------

    # Antes del groupby
    df_full = df_full.reset_index(drop=True)

    for sku, grupo in df_full.groupby("SKU", sort=False):

        filas = grupo.to_dict("records")

        # ==========================================
        # Regla 3 (ClaroUp) - se evalúa a nivel SKU
        # ==========================================
        error_claroup = None
        contiene_claroup = any("claroup" in str(f["Nombre"]).lower() for f in filas)

        if contiene_claroup:
            filas_claroup = [f for f in filas if "claroup" in str(f["Nombre"]).lower()]
            if len(filas_claroup) != 3:
                error_claroup = f"SKU ClaroUp debe tener 3 repeticiones con ClaroUp en el nombre y tiene {len(filas_claroup)} (Regla 3)"

        # ===============================================================
        # Regla 2 - se evalúa a nivel SKU para obtener precio_macro
        # ===============================================================
        sku_no_existe = sku not in df_macro_unico.index
        precio_macro = None if sku_no_existe else df_macro_unico.loc[sku]["valor full"]

        # =====================
        # Iterar fila por fila
        # =====================
        for idx, fila in grupo.iterrows():
            errores = []

            # Regla 1: por fila individual
            precio_sin_iva = fila["FINAL S/IVA"]
            precio_con_iva = fila["C/iva"]
            esperado = calcular_precio_con_iva(precio_sin_iva)
            if precio_con_iva != esperado:
                errores.append(
                    f"El SKU {sku} no cumple la Regla 1 (revisar reglas mas arriba)"
                )

            # Regla 2: por fila individual contra la macro
            if sku_no_existe:
                errores.append(f"El SKU {sku} no existe en planilla macro")
            elif precio_macro != precio_con_iva:
                errores.append(
                    f"El SKU {sku} no cumple con la Regla 2"
                )

            # Regla 3: solo en filas con ClaroUp en el nombre
            if error_claroup and "claroup" in str(fila["Nombre"]).lower():
                errores.append(error_claroup)

            # Resultado por fila
            fila_dict = sanitizar_fila(dict(fila))

            # Calcular diferencias según qué regla falló
            comparaciones = []

            if precio_con_iva != esperado:
                comparaciones.append({
                    "regla": "Regla 1",
                    "descripcion": "FINAL S/IVA * 1.19 vs C/iva",
                    "precio_base_iva": esperado,
                    "precio_comp": precio_con_iva,
                    "diferencia": precio_con_iva - esperado
                })

            if sku_no_existe:
                comparaciones.append({
                    "regla": "SKU no encontrado",
                    "descripcion": "SKU no existe en planilla macro",
                    "precio_base_iva": None,
                    "precio_comp": None,
                    "diferencia": None
                })
            elif precio_macro != precio_con_iva:
                comparaciones.append({
                    "regla": "Regla 2",
                    "descripcion": "C/iva vs valor full macro",
                    "precio_base_iva": precio_con_iva,
                    "precio_comp": precio_macro,
                    "diferencia": precio_con_iva - precio_macro
                })
            
            if errores:
                resumen.append({
                    "sku": str(sku),
                    "indice_original": idx,
                    "numero_fila": idx + 2,
                    "nombre": fila_dict.get("Nombre"),
                    "estado": "Con error",
                    "detalle_error": {
                        "errores": errores,
                        "nombre": fila_dict.get("Nombre"),
                        "model": fila_dict.get("Model"),
                        "color": fila_dict.get("Color"),
                        "make": fila_dict.get("Make"),
                        "equipment_rank_value": fila_dict.get("Equipment Rank Value"),
                        "use_category": fila_dict.get("Use Category"),
                        "equipment_classification": fila_dict.get("Equipment Classification"),
                        "precio_base": fila_dict.get("FINAL S/IVA"),
                        "comparaciones": comparaciones
                    }
                })
            else:
                resumen.append({
                    "sku": str(sku),
                    "nombre": fila_dict.get("Nombre"), 
                    "indice_original": idx,
                    "numero_fila": idx + 2,
                    "estado": "OK",
                    "detalle_error": None
                })

    # -----------------------
    # Resultado final
    # -----------------------

    # Reordenar resumen según orden original del excel
    resumen_ordenado = sorted(resumen, key=lambda r: r["indice_original"])

    # Limpiar el índice antes de retornar
    for r in resumen_ordenado:
        r.pop("indice_original")

    return {
        "tipo": "precios_full",
        "total_filas": to_python_type(len(resumen_ordenado)),
        "total_ok": sum(1 for r in resumen_ordenado if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen_ordenado if r["estado"] == "Con error"),
        "resumen": resumen_ordenado
    }