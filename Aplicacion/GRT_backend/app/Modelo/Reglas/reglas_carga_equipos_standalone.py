# reglas_carga_equipos_standalone.py

# Módulo de validación de reglas para equipos standalone

# La validación se realiza con las planillas "20260128_Planilla_carga_Equipos EPC Enero SKU Unico v1" y "20260128_Planilla_de_Precios_(nueva)_v1", específicamente con los precios de la sección "Contado (Tarjeta de Crédito, Débito y Efectivo) Solo CAC". El precio con el que se compara depende de si en el nombre del articulo aparece el prefijo "PRE", "EP" o "FIDE".

# Reglas a validar para cada fila:

# Regla 1:

# El precio de la columna Full price multiplicado por 1,19 (IVA) debe ser igual al precio que tiene el SKU en la planilla “20260128_Planilla_de_Precios_(nueva)_v1” en la hoja "Planilla de Precios", si el nombre del articulo empieza con “EP”, se debe buscar esa categoría en la segunda planilla (lo mismo para “FIDE” y “PRE”). Las columnas en la planilla de precios son Precio Liberado / Prepago (PRE), Precio Equipo + Plan Contado (EP), Precio Recambio Contado (FIDE).

# Regla 2:

# Los nombres, colores y modelos (columnas Nombre, COLOR y Model) no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.

# Regla 3: 

# El nombre, color y modelo (columnas Nombre, COLOR y Model) del equipo debe ser menor o igual a 30 caracteres.

import pandas as pd
import numpy as np
from typing import Dict, Any
import re

import logging
logger = logging.getLogger("uvicorn")

def to_python_type(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def calcular_precio_con_iva(precio: float, tasa_iva: float = 0.19) -> int:
    return int(np.floor(precio * (1 + tasa_iva) + 0.5))


def validar_largo_texto(valor: Any, max_len: int = 30) -> bool:
    if pd.isna(valor):
        return False
    return len(str(valor).strip()) > max_len


def validar_caracteres_invalidos(valor: Any) -> list:
    if pd.isna(valor):
        return []
    texto = str(valor).strip()
    matches = re.findall(r'[/*\-#,.()[\]{}|\\<>_=+@!$%^&;:\'\"`~?]', texto)
    return list(set(matches))


def determinar_columna_precio(nombre: str) -> str | None:
    """
    Determina qué columna de precio usar según el prefijo del nombre.
    Retorna None si no aplica ningún prefijo conocido.
    """
    nombre_upper = str(nombre).strip().upper()
    if nombre_upper.startswith("EP"):
        return "ep"
    elif nombre_upper.startswith("FIDE"):
        return "fide"
    elif nombre_upper.startswith("PRE"):
        return "pre"
    return None


def leer_planilla_precios_standalone(path: str) -> Dict[str, Any]:
    """
    Lee la hoja 'Planilla de Precios' con encabezados en filas 2 y 3 (índice 1 y 2).
    Retorna un dict con:
      - df: DataFrame con MultiIndex de columnas
      - col_sku: nombre de la columna SKU
      - col_pre: columna de precio para PRE (Precio Liberado/Prepago > Contado)
      - col_ep: columna de precio para EP (Precio Equipo + Plan Contado > Contado)
      - col_fide: columna de precio para FIDE (Precio Recambio Contado > Contado)
    """
    df = pd.read_excel(path, sheet_name="Planilla de Precios", header=[1, 2])

    # Aplanar MultiIndex de columnas para poder trabajar con ellas
    # Cada columna queda como "NivelSuperior | NivelInferior"
    df.columns = [
        f"{str(a).strip()} | {str(b).strip()}" if not str(a).startswith("Unnamed") else str(b).strip()
        for a, b in df.columns
    ]

    # Buscar columna SKU (está en fila 3, sin encabezado superior)
    col_sku = next((c for c in df.columns if str(c).strip().upper() == "SKU"), None)

    # Buscar columnas de precio buscando por encabezado compuesto
    col_pre = next((
        c for c in df.columns
        if "Precio Liberado" in c and "Prepago" in c and "Contado" in c
    ), None)

    col_ep = next((
        c for c in df.columns
        if "Precio Equipo" in c and "Plan" in c and "Contado" in c
    ), None)

    col_fide = next((
        c for c in df.columns
        if "Recambio" in c and "Contado" in c
    ), None)

    return {
        "df": df,
        "col_sku": col_sku,
        "col_pre": col_pre,
        "col_ep": col_ep,
        "col_fide": col_fide
    }


def validar_columnas_requeridas(
    df_base: pd.DataFrame,
    info_precios: Dict
) -> Dict[str, str] | None:
    columnas_base = {"SKU Seriado", "FULL PRICE", "Nombre", "Model", "COLOR"}
    faltantes_base = columnas_base - set(df_base.columns)
    if faltantes_base:
        return {"error": f"A la planilla de equipos standalone le faltan columnas: {', '.join(sorted(faltantes_base))}. Columnas detectadas: {', '.join(df_base.columns)}"}

    errores_precios = []
    if not info_precios["col_sku"]:
        errores_precios.append("SKU")
    if not info_precios["col_pre"]:
        errores_precios.append("Precio Liberado/Prepago > Contado (para PRE)")
    if not info_precios["col_ep"]:
        errores_precios.append("Precio Equipo + Plan Contado > Contado (para EP)")
    if not info_precios["col_fide"]:
        errores_precios.append("Precio Recambio Contado > Contado (para FIDE)")

    if errores_precios:
        return {"error": f"No se encontraron las siguientes columnas en 'Planilla de Precios': {', '.join(errores_precios)}"}

    return None


def validar_equipos_standalone(
    df_base: pd.DataFrame,
    info_precios: Dict
) -> Dict[str, Any]:

    error = validar_columnas_requeridas(df_base, info_precios)
    if error:
        return error

    df_precios = info_precios["df"]
    col_sku = info_precios["col_sku"]
    col_pre = info_precios["col_pre"]
    col_ep = info_precios["col_ep"]
    col_fide = info_precios["col_fide"]

    # Indexar planilla de precios por SKU
    df_precios_clean = df_precios.dropna(subset=[col_sku])
    df_precios_idx = df_precios_clean.drop_duplicates(subset=[col_sku], keep="first").set_index(col_sku)

    # Mapa prefijo → columna de precio
    mapa_columnas = {
        "pre": col_pre,
        "ep": col_ep,
        "fide": col_fide
    }

    # Descripción legible por prefijo
    mapa_descripcion = {
        "pre": "FULL PRICE * 1.19 vs Precio Liberado/Prepago Contado",
        "ep": "FULL PRICE * 1.19 vs Precio Equipo + Plan Contado",
        "fide": "FULL PRICE * 1.19 vs Precio Recambio Contado"
    }

    df_base = df_base.reset_index(drop=True)
    resumen = []

    for idx, fila in df_base.iterrows():
        errores = []
        comparaciones = []

        sku = fila["SKU Seriado"]
        nombre = fila["Nombre"]
        modelo = fila["Model"]
        color = fila["COLOR"]
        full_price = fila["FULL PRICE"]

        precio_base_iva = calcular_precio_con_iva(full_price) if pd.notna(full_price) else None

        tipo_equipo = str(fila.get("TIPO Equipo", "")).strip().upper()
        es_creacion = tipo_equipo == "CREACION"

        # Regla 2 y 3: solo aplican si es creación
        if es_creacion:

            # Regla 3: largo máximo 30 caracteres

            if validar_largo_texto(nombre):
                #errores.append(f"El valor de la columna Nombre en la planilla SKU único para el SKU {sku} supera 30 caracteres (revisar Regla 3 más arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 3 (revisar reglas más arriba)")
            if validar_largo_texto(modelo):
                #errores.append(f"El valor de la columna Model en la planilla SKU único para el SKU {sku} supera 30 caracteres (revisar Regla 3 más arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 3 (revisar reglas más arriba)")
            if validar_largo_texto(color):
                #errores.append(f"El valor de la columna Color en la planilla SKU único para el SKU {sku} supera 30 caracteres (revisar Regla 3 más arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 3 (revisar reglas más arriba)")

            # Regla 2: caracteres inválidos
            
            chars_nombre = validar_caracteres_invalidos(nombre)
            if chars_nombre:
                #errores.append(f"El valor de la columna Nombre en la planilla SKU único para el SKU {sku} tiene caracteres inválidos: {', '.join(chars_nombre)} (revisar Regla 2 mas arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 2 (revisar reglas más arriba)")
            chars_modelo = validar_caracteres_invalidos(modelo)
            if chars_modelo:
                #errores.append(f"El valor de la columna Modelo en la planilla SKU único para el SKU {sku} tiene caracteres inválidos: {', '.join(chars_modelo)} (revisar Regla 2 mas arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 2 (revisar reglas más arriba)")
            chars_color = validar_caracteres_invalidos(color)
            if chars_color:
                #errores.append(f"El valor de la columna Color en la planilla SKU único para el SKU {sku} tiene caracteres inválidos: {', '.join(chars_color)} (revisar Regla 2 mas arriba)")
                errores.append(f"El SKU {sku} no cumple la Regla 2 (revisar reglas más arriba)")

        # Regla 1: comparación de precio según prefijo
        prefijo = determinar_columna_precio(nombre)

        if prefijo is None:
            errores.append(f"El nombre del SKU {sku} en la planilla SKU único no comienza con PRE, EP ni FIDE, no se puede determinar columna de precio (revisar regla 1 mas arriba)")
        elif pd.isna(sku) or sku not in df_precios_idx.index:
            errores.append(f"El SKU {sku} no existe en la hoja 'Planilla de Precios' de la planilla de precios (revisar regla 1 mas arriba)")
            comparaciones.append({
                "regla": "SKU no encontrado",
                "descripcion": "SKU no existe en planilla de precios",
                "precio_base_iva": to_python_type(precio_base_iva),
                "precio_comp": None,
                "diferencia": None
            })
        else:
            col_precio = mapa_columnas[prefijo]
            precio_comp = df_precios_idx.loc[sku][col_precio]
            precio_comp_int = int(precio_comp) if pd.notna(precio_comp) else None

            if precio_base_iva is not None and precio_comp_int is not None and precio_base_iva != precio_comp_int:
                diferencia = precio_base_iva - precio_comp_int
                errores.append(f"El SKU {sku} no cumple la Regla 1 (revisar reglas mas arriba)")
                comparaciones.append({
                    "regla": "Regla 1",
                    "descripcion": mapa_descripcion[prefijo],
                    "precio_base_iva": to_python_type(precio_base_iva),
                    "precio_comp": to_python_type(precio_comp_int),
                    "diferencia": to_python_type(diferencia)
                })

        if errores:
            resumen.append({
                "sku": str(sku),
                "nombre": nombre,
                "numero_fila": idx + 2,
                "estado": "Con error",
                "detalle_error": {
                    "errores": errores,
                    "nombre": nombre,
                    "model": to_python_type(fila.get("Model")) if hasattr(fila, 'get') else to_python_type(fila["Model"]) if "Model" in df_base.columns else None,
                    "color": to_python_type(fila.get("COLOR")) if hasattr(fila, 'get') else to_python_type(fila["COLOR"]) if "COLOR" in df_base.columns else None,
                    "make": to_python_type(fila.get("Make")) if hasattr(fila, 'get') else to_python_type(fila["Make"]) if "Make" in df_base.columns else None,
                    "equipment_rank_value": to_python_type(fila.get("Equipment Rank Value")) if hasattr(fila, 'get') else to_python_type(fila["Equipment Rank Value"]) if "Equipment Rank Value" in df_base.columns else None,
                    "use_category": to_python_type(fila.get("Use Category")) if hasattr(fila, 'get') else to_python_type(fila["Use Category"]) if "Use Category" in df_base.columns else None,
                    "equipment_classification": to_python_type(fila.get("Equipment Classification")) if hasattr(fila, 'get') else to_python_type(fila["Equipment Classification"]) if "Equipment Classification" in df_base.columns else None,
                    "precio_base": to_python_type(full_price),
                    "comparaciones": comparaciones
                }
            })
        else:
            resumen.append({
                "sku": str(sku),
                "nombre": nombre,
                "numero_fila": idx + 2,
                "estado": "OK",
                "detalle_error": None
            })

    return {
        "tipo": "equipos_standalone",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }