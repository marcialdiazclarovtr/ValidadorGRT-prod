# reglas_equipos_accesorios.py

# Módulo de validación de reglas para equipos accesorios

# La validación se realiza con las planillas "20260128_Planilla_carga_Equipos_Accesorios_EPC_Enero v1" y "20260128_Planilla_de_Precios_(nueva)_v1", específicamente con el precio de la 5ta columna (Precio Oferta) de la hoja "Accesorios + IOT + BAM"

# Reglas a validar para cada fila:

# Regla 1:

# El nombre, color y modelo del equipo debe ser menor o igual a 30 caracteres.

# Regla 2:

# Los nombres, colores y modelos no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.

# Regla 3: 

# El precio de la columna "FULL PRICE" de la planilla "20260128_Planilla_carga_Equipos_Accesorios_EPC_Enero v1" multiplicado por 1,19 (IVA) debe ser igual al precio de la columna "Precio Oferta", en la hoja "Accesorios + IOT + BAM" de la planilla "20260128_Planilla_de_Precios_(nueva)_v1"

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


def validar_columnas_requeridas(
    df_base: pd.DataFrame,
    df_precios: pd.DataFrame
) -> Dict[str, str] | None:
    columnas_base = {"SKU Seriado", "FULL PRICE", "Nombre", "Model", "COLOR"}
    columnas_precios = {"SKU", "Precio Oferta"}
    
    # Columnas que realmente existen en los DataFrames
    existentes_base = list(df_base.columns)
    existentes_precios = list(df_precios.columns)

    faltantes_base = columnas_base - set(df_base.columns)
    faltantes_precios = columnas_precios - set(df_precios.columns)

    if faltantes_base:
        return {"error": f"A la planilla de equipos accesorios le faltan columnas: {', '.join(sorted(faltantes_base))}. Columnas detectadas: {', '.join(existentes_base)}"}
    if faltantes_precios:
        return {"error": f"A la hoja 'Accesorios + IOT + BAM' le faltan columnas: {', '.join(sorted(faltantes_precios))}. Columnas detectadas: {', '.join(existentes_precios)}"}

    return None


def validar_equipos_accesorios(
    df_base: pd.DataFrame,
    df_precios: pd.DataFrame
) -> Dict[str, Any]:

    error = validar_columnas_requeridas(df_base, df_precios)
    if error:
        return error

    # Indexar planilla de precios por SKU
    df_precios_idx = df_precios.drop_duplicates(subset=["SKU"], keep="first").set_index("SKU")

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

        tipo_accesorio = str(fila.get("TIPO ACCESORIO", "")).strip().upper()
        es_creacion = tipo_accesorio == "CREACION"

        logger.info(f"Fila {idx+2} | color='{color}' | use_category='{fila.get('Use Category')}'")

        precio_base_iva = calcular_precio_con_iva(full_price) if pd.notna(full_price) else None

        # Regla 1 y 2: solo aplican si es creación
        if es_creacion:
            # Regla 1
            if validar_largo_texto(nombre):
                errores.append(f"El valor {nombre} supera 30 caracteres (revisar regla 1 mas arriba)")
            if validar_largo_texto(modelo):
                errores.append(f"El valor {modelo} supera 30 caracteres (revisar regla 1 mas arriba)")
            if validar_largo_texto(color):
                errores.append(f"El valor {color} supera 30 caracteres (revisar regla 1 mas arriba)")

            
            # Regla 2
            chars_nombre = validar_caracteres_invalidos(nombre)
            if chars_nombre:
                errores.append(f"El valor {nombre} tiene caracteres inválidos: {', '.join(chars_nombre)} (revisar regla 2 mas arriba)")
            chars_modelo = validar_caracteres_invalidos(modelo)
            if chars_modelo:
                errores.append(f"El valor {modelo} tiene caracteres inválidos: {', '.join(chars_modelo)} (revisar regla 2 mas arriba)")
            chars_color = validar_caracteres_invalidos(color)
            if chars_color:
                errores.append(f"El valor {color} tiene caracteres inválidos: {', '.join(chars_color)} (revisar regla 2 mas arriba)")

        # Regla 3: comparación de precio contra planilla de precios
        if pd.isna(sku) or sku not in df_precios_idx.index:
            errores.append(f"El SKU {sku} no existe en la hoja 'Accesorios + IOT + BAM' de la planilla de precios")
            comparaciones.append({
                "regla": "SKU no encontrado",
                "descripcion": "SKU no existe en planilla de precios",
                "precio_base_iva": to_python_type(precio_base_iva),
                "precio_comp": None,
                "diferencia": None
            })
        else:
            precio_oferta = df_precios_idx.loc[sku]["Precio Oferta"]
            precio_oferta_int = int(precio_oferta) if pd.notna(precio_oferta) else None

            if precio_base_iva is not None and precio_oferta_int is not None and precio_base_iva != precio_oferta_int:
                diferencia = precio_base_iva - precio_oferta_int
                errores.append(f"El SKU {sku} no cumple con la regla 3 (revisar reglas mas arriba)")
                comparaciones.append({
                    "regla": "Regla 3",
                    "descripcion": "FULL PRICE * 1.19 vs Precio Oferta",
                    "precio_base_iva": to_python_type(precio_base_iva),
                    "precio_comp": to_python_type(precio_oferta_int),
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
                    "model": to_python_type(modelo),
                    "color": to_python_type(color),
                    "make": to_python_type(fila.get("Make")),
                    "equipment_rank_value": to_python_type(fila.get("Equipment Rank Value")),
                    "use_category": to_python_type(fila.get("Use Category")),
                    "equipment_classification": to_python_type(fila.get("Equipment Classification")),
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
        "tipo": "equipos_accesorios",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }