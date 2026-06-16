# reglas_financiamiento.py

# Reglas para las planillas “20260128_Planilla_de_Precios_(nueva)_v1” y “20260216 W8 CR479 macro (envío) v2”:

# 1) Revisar en la planilla de precios que el valor de la columna “Valor Full Contado” (debajo de “Canales Masivos (Tarjeta de Crédito, Débito y Efectivo)”) corresponda al de la columna “valor full” de la planilla macro (ambos tienen incluido el IVA, solo hay que validar que los valores sean iguales)

# En la planilla macro al encontrar el SKU, para la columna “SALE_CHANNEL” hay que tomar solo los registros con valor “CAC”, para la columna “OR” los registros con valores entre 2 y 16 (puede que no existan numeros como el 5 y el 14, lo importante es que existan el 2, 3, 4, 6, 12, 13 y 16, si uno de estos no existe hay que alertarlo (no como error))

# 2) En la planilla de precios hay que buscar la columna "Total QA”, que está debajo de una de estas dos columnas: "Portabilidad" o "Financiamiento", y estas dos columnas están debajo de "Financiamiento", financiamiento está en la fila 1, portabilidad / recambio están en la fila 2, y Total QA en la fila 3. 

# En la tabla macro, hay que buscar ese SKU, y en la columna “ORDER_ACTIVITY” hay que ver si es "PI" o "R" (en base a esto se verá que Total QA buscar en la planilla de precios), y para la columna “SALE_CHANNEL” hay que tomar solo los registros con valor “CAC”, para la columna “OR” los registros con valores entre 2 y 16 (puede que no existan numeros como el 5 y el 14, lo importante es que existan el 2, 3, 4, 6, 12, 13 y 16, si uno de estos no existe hay que alertarlo (no como error)), y si está “PI” en la columna “ORDER_ACTIVITY” es “Portabilidad” en la planilla de precios, y si en la columna “ORDER_ACTIVITY” está “R” es “Recambio” en la planilla de precios, luego verificar que la columna "Total QA” en la planilla de precios sea igual al valor de la columna “C.A.” en la planilla macro (ambos están con IVA).

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger("uvicorn")

OR_OBLIGATORIOS = {2, 3, 4, 6, 12, 13, 16}


def to_python_type(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def leer_planilla_precios_financiamiento(path: str) -> Dict[str, Any]:
    df = pd.read_excel(path, sheet_name="Planilla de Precios", header=[0, 1, 2])

    def aplanar(cols):
        resultado = []
        for partes in cols:
            partes_limpias = [str(p).strip() for p in partes if not str(p).startswith("Unnamed")]
            resultado.append(" | ".join(partes_limpias) if partes_limpias else "_")
        return resultado

    df.columns = aplanar(df.columns)
    # logger.info(f"Columnas planilla financiamiento: {list(df.columns)}")

    df.columns = (
        df.columns
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    df = df.loc[:, ~df.columns.duplicated()]

    col_sku = next((
        c for c in df.columns
        if "sku" in str(c).lower() and "sku pre" not in str(c).lower()
    ), None)

    col_valor_full_contado = next((
        c for c in df.columns
        if "Canales Masivos" in c and "Valor Full" in c and "Contado" in c
    ), None)
    if not col_valor_full_contado:
        col_valor_full_contado = next((
            c for c in df.columns
            if "Valor Full" in c and "Contado" in c
        ), None)

    col_total_qa_portabilidad = next((
        c for c in df.columns
        if "Financiamiento" in c and "Portabilidad" in c and "Total QA" in c
    ), None)

    col_total_qa_recambio = next((
        c for c in df.columns
        if "Financiamiento" in c and "Recambio" in c and "Total QA" in c
    ), None)

    """ logger.info(f"col_sku={col_sku}, col_valor_full_contado={col_valor_full_contado}, "
                f"col_total_qa_portabilidad={col_total_qa_portabilidad}, "
                f"col_total_qa_recambio={col_total_qa_recambio}") """
    
    cols_info = [
        "Generación", "UP", "Phone Protect", "Segmento", "Status", "Ord",
        "Sku Pre", "Marca", "Modelo Master", "Modelo Técnico",
        "Modelo Comercial", "Valor Full contratando un plan", "Estándar", "Max",
        "Precio Referencial"
    ]

    mapa_cols_info = {}
    for nombre_buscado in cols_info:
        col_encontrada = next((
            c for c in df.columns
            if str(c).strip().lower() == nombre_buscado.strip().lower()
        ), None)
        if not col_encontrada:
            col_encontrada = next((
                c for c in df.columns
                if nombre_buscado.strip().lower() in str(c).strip().lower()
            ), None)
        mapa_cols_info[nombre_buscado] = col_encontrada

    # logger.info(f"Columnas info encontradas: {mapa_cols_info}")

    return {
        "df": df,
        "col_sku": col_sku,
        "col_valor_full_contado": col_valor_full_contado,
        "col_total_qa_portabilidad": col_total_qa_portabilidad,
        "col_total_qa_recambio": col_total_qa_recambio,
        "mapa_cols_info": mapa_cols_info,
    }


def validar_columnas_requeridas_financiamiento(
    info_precios: Dict,
    df_macro: pd.DataFrame
) -> Dict[str, str] | None:

    errores = []
    if not info_precios["col_sku"]:
        errores.append("SKU")
    if not info_precios["col_valor_full_contado"]:
        errores.append("Valor Full Contado (bajo 'Canales Masivos')")
    if not info_precios["col_total_qa_portabilidad"]:
        errores.append("Total QA Portabilidad (bajo 'Financiamiento')")
    if not info_precios["col_total_qa_recambio"]:
        errores.append("Total QA Recambio (bajo 'Financiamiento')")

    if errores:
        return {"error": f"No se encontraron columnas en la planilla de precios: {', '.join(errores)}"}

    columnas_macro = {"EQUIPMENT_SKU", "valor full", "ORDER_ACTIVITY", "SALE_CHANNEL", "OR", "C.A."}
    faltantes_macro = columnas_macro - set(df_macro.columns)
    if faltantes_macro:
        return {"error": f"A la planilla macro le faltan columnas: {', '.join(sorted(faltantes_macro))}"}

    return None


def validar_financiamiento(
    df_precios_raw: pd.DataFrame,
    info_precios: Dict,
    df_macro: pd.DataFrame
) -> Dict[str, Any]:

    error = validar_columnas_requeridas_financiamiento(info_precios, df_macro)
    if error:
        return error

    df_precios = info_precios["df"]
    col_sku = info_precios["col_sku"]
    col_valor_full_contado = info_precios["col_valor_full_contado"]
    col_total_qa_portabilidad = info_precios["col_total_qa_portabilidad"]
    col_total_qa_recambio = info_precios["col_total_qa_recambio"]

    mapa_cols_info = info_precios.get("mapa_cols_info", {})

    def extraer_info_fila(fila):
        info = {}
        for nombre, col in mapa_cols_info.items():
            info[nombre] = to_python_type(fila[col]) if col and col in fila.index else None
        return info

    df_precios_clean = df_precios.dropna(subset=[col_sku]).copy()
    df_precios_clean[col_sku] = df_precios_clean[col_sku].astype(str).str.strip()
    df_precios_idx = df_precios_clean.drop_duplicates(subset=[col_sku], keep="first").set_index(col_sku)

    df_macro = df_macro.copy()
    df_macro["EQUIPMENT_SKU"] = df_macro["EQUIPMENT_SKU"].astype(str).str.strip()
    df_macro["OR_num"] = pd.to_numeric(df_macro["OR"], errors="coerce")

    resumen = []

    for i, sku in enumerate(df_precios_idx.index):
        errores = []
        alertas = []
        comparaciones = []
        numero_fila = i + 4

        fila_precio = df_precios_idx.loc[sku]
        valor_full_contado = fila_precio[col_valor_full_contado]
        valor_full_contado_int = int(valor_full_contado) if pd.notna(valor_full_contado) else None

        filas_macro_sku = df_macro[df_macro["EQUIPMENT_SKU"] == sku]

        # Validar si el sku existe
        if filas_macro_sku.empty:
            errores.append(f"El SKU {sku} no existe en la planilla macro")
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    **extraer_info_fila(fila_precio),
                    "precio_base": to_python_type(valor_full_contado),
                    "comparaciones": comparaciones
                }
            })
            continue

        # Subconjunto filtrado para reglas (CAC + OR 2-16)
        filas_cac = filas_macro_sku[
            (filas_macro_sku["SALE_CHANNEL"].astype(str).str.strip().str.upper() == "CAC") &
            (filas_macro_sku["OR_num"].between(2, 16))
        ].copy()

        filas_cac_sin_filtro_or = filas_macro_sku[
            filas_macro_sku["SALE_CHANNEL"].astype(str).str.strip().str.upper() == "CAC"
        ].copy()

        # if sku == "70015920":
            # logger.info(f"ORDER_ACTIVITY únicos para SKU {sku}: {filas_cac['ORDER_ACTIVITY'].unique().tolist()}")

        if filas_cac.empty:
            errores.append(f"No existen registros con valor 'CAC' en la columna 'SALE_CHANNEL' y valor 'OR' entre 2 y 16 en la planilla macro para el SKU {sku}")
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    **extraer_info_fila(fila_precio),
                    "precio_base": to_python_type(valor_full_contado),
                    "comparaciones": comparaciones
                }
            })
            continue

        # Alerta en caso de que falten filas con OR Obligatorios
        for order_activity_check in ["P", "PI", "R"]:
            filas_oa = filas_cac_sin_filtro_or[
                filas_cac_sin_filtro_or["ORDER_ACTIVITY"].astype(str).str.strip().str.upper() == order_activity_check
            ]
            if filas_oa.empty:
                continue
            or_presentes_oa = set(filas_oa["OR_num"].dropna().astype(int).tolist())
            or_faltantes_oa = OR_OBLIGATORIOS - or_presentes_oa
            if or_faltantes_oa:
                alertas.append(
                    f"OR obligatorios no encontrados (CAC, {order_activity_check}, 2-16): {sorted(or_faltantes_oa)}"
                )

        # Regla 1 usando subconjunto filtrado
        valor_full_macro_int = None
        valores_full_macro = filas_cac["valor full"].dropna().unique()

        if len(valores_full_macro) == 0:
            errores.append("No existen valores full válidos para registros con valor 'CAC' y 'OR' entre 2 y 16 en la planilla macro (revisar Regla 1 más arriba)")
        else:
            if len(valores_full_macro) > 1:
                errores.append(
                    f"Inconsistencia en valor full macro para registros con valor 'CAC' y 'OR' entre 2 y 16 en la planilla macro (revisar Regla 1 más arriba): {valores_full_macro.tolist()}"
                )
            else:
                valor_full_macro_int = int(valores_full_macro[0])

        if valor_full_contado_int is not None and valor_full_macro_int is not None:
            if valor_full_contado_int != valor_full_macro_int:
                errores.append(
                    f"El SKU {sku} no cumple la Regla 1 (revisar reglas mas arriba)"
                )
                comparaciones.append({
                    "regla": "Regla 1",
                    "descripcion": "Valor Full Contado vs valor full macro",
                    "precio_base_iva": to_python_type(valor_full_contado_int),
                    "precio_comp": to_python_type(valor_full_macro_int),
                    "diferencia": to_python_type(valor_full_contado_int - valor_full_macro_int)
                })

        # Regla 2

        for _, fila_macro in filas_cac.iterrows():
            order_activity = str(fila_macro["ORDER_ACTIVITY"]).strip().upper()
            ca = fila_macro["C.A."]
            or_val = to_python_type(fila_macro["OR_num"])
            ca_int = int(ca) if pd.notna(ca) else None

            if order_activity == "PI":
                total_qa = fila_precio[col_total_qa_portabilidad]
                tipo_qa = "Portabilidad"
            elif order_activity == "R":
                total_qa = fila_precio[col_total_qa_recambio]
                tipo_qa = "Recambio"
            else:
                continue

            total_qa_int = int(total_qa) if pd.notna(total_qa) else None

            if ca_int is not None and total_qa_int is not None and ca_int != total_qa_int:
                errores.append(
                    f"El SKU {sku} con OR = {or_val} y ORDER_ACTIVITY = {order_activity} no cumple la Regla 2 (revisar reglas mas arriba)"
                )
                comparaciones.append({
                    "regla": "Regla 2",
                    "descripcion": f"OR={or_val} ({order_activity}): C.A. vs Total QA {tipo_qa}",
                    "precio_base_iva": to_python_type(ca_int),
                    "precio_comp": to_python_type(total_qa_int),
                    "diferencia": to_python_type(ca_int - total_qa_int)
                })

        if errores:
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    **extraer_info_fila(fila_precio),
                    "precio_base": to_python_type(valor_full_contado),
                    "comparaciones": comparaciones
                }
            })
        else:
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "OK",
                "alertas": alertas,
                "detalle_error": None
            })

    return {
        "tipo": "financiamiento",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }