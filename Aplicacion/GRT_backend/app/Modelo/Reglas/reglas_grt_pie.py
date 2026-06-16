# reglas_grt_pie.py

# Reglas para las planillas “20260128_Planilla_de_Precios_(nueva)_v1” y “20260128 GRT PIE W5 v1”:

# 1) En la planilla de precios hay que tomar un SKU, e ir a buscar ese SKU en la planilla GRT PIE, luego hay que quedarse solo con las filas que tienen ese SKU, "PI" o "R" en la columna "OrderType", y el valor "CAC" en la columna "Sales Channel". Para la columna “OR” los registros con valores entre 2 y 16 (puede que no existan numeros como el 5 y el 14, lo importante es que existan el 2, 3, 4, 6, 12, 13 y 16, si uno de estos no existe hay que alertarlo (no como error))

# Una vez que tenemos estos valores, comparamos aca uno de los precios de la columna "PVP s/IVA" (multiplicado por 1,19) con uno de los siguientes precios en la planilla de precios: el de la columna "Pie Referencial" debajo de "Portabilidad" (la cual está debajo de "Financiamiento") si es que el valor de la columna "OrderType" es "PI", o el de la columna "Pie" debajo de "Recambio" (la cual está debajo de "Financiamiento") si es que el valor de la columna "OrderType" es "R".

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


def calcular_precio_con_iva(precio: float, tasa_iva: float = 0.19) -> int:
    return int(np.floor(precio * (1 + tasa_iva) + 0.5))


def leer_columnas_pie(info_precios: Dict) -> Dict[str, Any]:
    """
    Extrae las columnas de Pie Referencial (Portabilidad) y Pie (Recambio)
    desde el df ya leído y aplanado de leer_planilla_precios_financiamiento.
    """
    df = info_precios["df"]

    col_pie_portabilidad = next((
        c for c in df.columns
        if "Financiamiento" in c and "Portabilidad" in c and "Pie Referencial" in c
    ), None)

    col_pie_recambio = next((
        c for c in df.columns
        if "Financiamiento" in c and "Recambio" in c and "Pie" in c
        and "Referencial" not in c  # evitar confusión si hubiera ambas bajo recambio
    ), None)

    logger.info(f"col_pie_portabilidad={col_pie_portabilidad}, col_pie_recambio={col_pie_recambio}")

    return {
        **info_precios,
        "col_pie_portabilidad": col_pie_portabilidad,
        "col_pie_recambio": col_pie_recambio,
    }


def validar_columnas_requeridas_pie(
    info_precios: Dict,
    df_pie: pd.DataFrame
) -> Dict[str, str] | None:

    errores = []
    if not info_precios["col_sku"]:
        errores.append("SKU (planilla de precios)")
    if not info_precios.get("col_pie_portabilidad"):
        errores.append("Pie Referencial bajo Portabilidad (Financiamiento)")
    if not info_precios.get("col_pie_recambio"):
        errores.append("Pie bajo Recambio (Financiamiento)")

    if errores:
        return {"error": f"No se encontraron columnas en la planilla de precios: {', '.join(errores)}"}

    columnas_pie = {"SKU", "OrderType", "Sales Channel", "Offer Rank", "PVP s/IVA"}
    faltantes_pie = columnas_pie - set(df_pie.columns)
    if faltantes_pie:
        return {"error": f"A la planilla GRT PIE le faltan columnas: {', '.join(sorted(faltantes_pie))}"}

    return None


def validar_grt_pie(
    info_precios: Dict,
    df_pie: pd.DataFrame
) -> Dict[str, Any]:

    # Agregar columnas pie al info_precios
    info_precios = leer_columnas_pie(info_precios)

    error = validar_columnas_requeridas_pie(info_precios, df_pie)
    if error:
        return error

    df_precios = info_precios["df"]
    col_sku = info_precios["col_sku"]
    col_pie_portabilidad = info_precios["col_pie_portabilidad"]
    col_pie_recambio = info_precios["col_pie_recambio"]
    mapa_cols_info = info_precios.get("mapa_cols_info", {})

    def extraer_info_fila(fila):
        info = {}
        for nombre, col in mapa_cols_info.items():
            info[nombre] = to_python_type(fila[col]) if col and col in fila.index else None
        return info

    # Limpiar planilla de precios
    df_precios_clean = df_precios.dropna(subset=[col_sku]).copy()
    df_precios_clean[col_sku] = df_precios_clean[col_sku].astype(str).str.strip()
    df_precios_idx = df_precios_clean.drop_duplicates(subset=[col_sku], keep="first").set_index(col_sku)

    # Preparar planilla GRT PIE
    df_pie = df_pie.copy()
    df_pie["SKU"] = df_pie["SKU"].astype(str).str.strip()
    df_pie["OR_num"] = pd.to_numeric(df_pie["Offer Rank"], errors="coerce")

    resumen = []

    for i, sku in enumerate(df_precios_idx.index):
        errores = []
        alertas = []
        comparaciones = []
        numero_fila = i + 4

        fila_precio = df_precios_idx.loc[sku]

        # Buscar filas del SKU en GRT PIE filtradas por OrderType PI o R, Sales Channel CAC, OR 2-16
        filas_sku = df_pie[df_pie["SKU"] == sku]

        if filas_sku.empty:
            errores.append(f"El SKU '{sku}' no existe en la planilla GRT PIE")
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    **extraer_info_fila(fila_precio),
                    "precio_base": None,
                    "comparaciones": comparaciones
                }
            })
            continue

        filas_filtradas = filas_sku[
            (filas_sku["OrderType"].astype(str).str.strip().str.upper().isin(["PI", "R"])) &
            (filas_sku["Sales Channel"].astype(str).str.strip().str.upper() == "CAC") &
            (filas_sku["OR_num"].between(2, 16))
        ].copy()

        filas_cac_sin_filtro_or = filas_sku[
            filas_sku["Sales Channel"].astype(str).str.strip().str.upper() == "CAC"
        ].copy()

        if filas_filtradas.empty:
            errores.append("No existen registros con OrderType PI/R, Sales Channel CAC y OR entre 2 y 16")
            resumen.append({
                "sku": sku,
                "nombre": str(sku),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    **extraer_info_fila(fila_precio),
                    "precio_base": None,
                    "comparaciones": comparaciones
                }
            })
            continue

        # Alertar OR obligatorios faltantes
        for order_type_check in ["P", "PI", "R"]:
            filas_ot = filas_cac_sin_filtro_or[
                filas_cac_sin_filtro_or["OrderType"].astype(str).str.strip().str.upper() == order_type_check
            ]
            if filas_ot.empty:
                continue
            or_presentes_ot = set(filas_ot["OR_num"].dropna().astype(int).tolist())
            or_faltantes_ot = OR_OBLIGATORIOS - or_presentes_ot
            if or_faltantes_ot:
                alertas.append(
                    f"OR obligatorios no encontrados (CAC, {order_type_check}, 2-16): {sorted(or_faltantes_ot)}"
                )

        # Comparar PVP s/IVA * 1.19 vs Pie según OrderType
        for _, fila_pie in filas_filtradas.iterrows():
            order_type = str(fila_pie["OrderType"]).strip().upper()
            pvp_sin_iva = fila_pie["PVP s/IVA"]
            or_val = to_python_type(fila_pie["OR_num"])

            pvp_con_iva = calcular_precio_con_iva(pvp_sin_iva) if pd.notna(pvp_sin_iva) else None

            if order_type == "PI":
                pie = fila_precio[col_pie_portabilidad]
                tipo_pie = "Pie Referencial Portabilidad"
            elif order_type == "R":
                pie = fila_precio[col_pie_recambio]
                tipo_pie = "Pie Recambio"
            else:
                continue

            # DESPUÉS:
            pie_int = None
            if pd.isna(pie):
                pie_int = None
            else:
                try:
                    pie_int = int(pie)
                except (ValueError, TypeError):
                    # El valor es texto (ej: 'No Disp'), agregar como alerta
                    nombre_col = tipo_pie  # ya tiene el nombre legible según order_type
                    alertas.append(
                        f"El precio en la celda {nombre_col} aparece como '{pie}', "
                        f"por lo que no se puede realizar la comparación con la columna PVP s/IVA de la planilla GRT PIE"
                    )

            if pvp_con_iva is not None and pie_int is not None and pvp_con_iva != pie_int:
                """ errores.append(
                    f"OR={or_val} ({order_type}): PVP s/IVA * 1.19 ({pvp_con_iva}) != {tipo_pie} ({pie_int}) (Regla 1)"
                ) """
                errores.append(
                    f"El SKU {sku} con OR = {or_val} y OrderType {order_type} no cumple la Regla 1 (revisar reglas mas arriba)"
                )
                comparaciones.append({
                    "regla": "Regla 1",
                    "descripcion": f"Offer Rank = {or_val} ({order_type}): PVP s/IVA * 1.19 vs {tipo_pie}",
                    "precio_base_iva": to_python_type(pvp_con_iva),
                    "precio_comp": to_python_type(pie_int),
                    "diferencia": to_python_type(pvp_con_iva - pie_int)
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
                    "precio_base": None,
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
        "tipo": "grt_pie",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }