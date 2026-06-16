# reglas_cargos_claroup.py
#sdsasdksks

# Reglas para la planilla “20260128 Cargos ClaroUp v1.xlsx”:

# Primero hay que detectar si el nombre de la planilla tiene la subcadena “Cargos ClaroUp”

# Luego hay que validar que se cumplan las siguientes reglas:

# 1) Que las columnas numéricas CONCAT, SKU, OFFER_RANK, EQUIPMENT_RANK, EQU_COMMITMENT_DURATION, NUM_OF_MONTH_START_RANGE, NUM_OF_MONTH_END_RANGE sean números enteros sin decimales ni valores no numéricos, y que las columnas LEASING_CHARGE, Valor Cuota, PURCHASE_CHARGE sean números sin valores no numéricos (pueden tener decimales)

# 2) Que la columna “PLAN_MARKET” solo tenga valores “PERSONA” y “PYME Y EMPRESAS”

# 3) Que la columna “EQU_COMMITMENT_DURATION” solo tenga el valor 24

# 4) Que la columna “NUM_OF_MONTH_START_RANGE” tenga valores enteros desde el 0 al 24.

# 5) Que la columna “NUM_OF_MONTH_END_RANGE” tenga valores enteros desde el 1 al 99.

# 6) Validar que la fecha de la columna EXPIRATION_DATE está después que el 31 de diciembre del año actual

import pandas as pd
import numpy as np
from typing import Dict, Any
from datetime import date
import logging

logger = logging.getLogger("uvicorn")

COLUMNAS_ENTERAS = [
    "SKU", "EQUIPMENT_RANK", "CONCAT", "OFFER_RANK",
    "EQU_COMMITMENT_DURATION", "NUM_OF_MONTH_START_RANGE", "NUM_OF_MONTH_END_RANGE"
]

COLUMNAS_NUMERICAS_CON_DECIMAL = [
    "LEASING_CHARGE", "Valor Cuota", "PURCHASE_CHARGE"
]

COLUMNAS_NUMERICAS = COLUMNAS_ENTERAS + COLUMNAS_NUMERICAS_CON_DECIMAL

VALORES_PLAN_MARKET = {"PERSONA", "PYME Y EMPRESAS"}


def to_python_type(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def es_entero(value) -> bool:
    """Retorna True si el valor es un entero (no decimal, no texto)."""
    if pd.isna(value):
        return False
    if isinstance(value, (int, np.integer)):
        return True
    if isinstance(value, (float, np.floating)):
        return value == int(value)
    # Intenta parsear strings
    try:
        f = float(str(value).strip())
        return f == int(f)
    except (ValueError, TypeError):
        return False
    
def es_numerico(value) -> bool:
    """Retorna True si el valor es un número (puede tener decimales)."""
    if pd.isna(value):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return True
    try:
        float(str(value).strip())
        return True
    except (ValueError, TypeError):
        return False

def validar_columnas_requeridas(df: pd.DataFrame) -> Dict[str, str] | None:
    columnas_requeridas = set(COLUMNAS_NUMERICAS) | {
        "PLAN_MARKET",
        "EXPIRATION_DATE"
    }
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        return {"error": f"A la planilla le faltan columnas: {', '.join(sorted(faltantes))}"}
    return None

def validar_cargos_claroup(df: pd.DataFrame) -> Dict[str, Any]:
    error_cols = validar_columnas_requeridas(df)
    if error_cols:
        return error_cols

    anio_actual = date.today().year
    fecha_limite = date(anio_actual, 12, 31)

    resumen = []

    for i, (_, fila) in enumerate(df.iterrows()):
        numero_fila = i + 2  # Asume fila 1 = header
        errores = []
        alertas = []

        # --- Regla 1: Columnas enteras ---
        for col in COLUMNAS_ENTERAS:
            if col not in df.columns:
                continue
            valor = fila[col]
            if pd.isna(valor):
                errores.append(f"La columna '{col}' de la planilla Cargos ClaroUp tiene un valor vacío (revisar Regla 1 mas arriba)")
            elif not es_entero(valor):
                errores.append(f"La columna '{col}' de la planilla Cargos ClaroUp tiene un valor no entero o no numérico: '{valor}' (revisar Regla 1 mas arriba)")

        # --- Regla 1: Columnas numéricas con decimal ---
        for col in COLUMNAS_NUMERICAS_CON_DECIMAL:
            if col not in df.columns:
                continue
            valor = fila[col]
            if pd.isna(valor):
                errores.append(f"La columna '{col}' de la planilla Cargos ClaroUp tiene un valor vacío (revisar Regla 1 mas arriba)")
            elif not es_numerico(valor):
                errores.append(f"La columna '{col}' de la planilla Cargos ClaroUp tiene un valor no numérico: '{valor}' (revisar Regla 1 mas arriba)")

        # --- Regla 2: PLAN_MARKET solo "PERSONA" o "PYME Y EMPRESAS" ---
        plan_market = fila.get("PLAN_MARKET")
        if pd.isna(plan_market) or str(plan_market).strip() == "":
            errores.append("La columna 'PLAN_MARKET' de la planilla Cargos ClaroUp tiene valores vacíos (revisar Regla 2 mas arriba)")
        elif str(plan_market).strip().upper() not in VALORES_PLAN_MARKET:
            errores.append(
                f"La columna 'PLAN_MARKET' de la planilla Cargos ClaroUp tiene un valor no permitido: '{plan_market}'. "
                f"Solo se permiten: {', '.join(sorted(VALORES_PLAN_MARKET))} (revisar Regla 2 mas arriba)"
            )

        # --- Regla 3: EQU_COMMITMENT_DURATION debe ser 24 ---
        ecd = fila.get("EQU_COMMITMENT_DURATION")
        if not pd.isna(ecd) and es_entero(ecd) and int(float(ecd)) != 24:
            errores.append(
                f"La columna 'EQU_COMMITMENT_DURATION' tiene un valor '{int(float(ecd))}' que incumple la regla 3 (revisar reglas mas arriba)"
            )

        # --- Regla 4: NUM_OF_MONTH_START_RANGE entre 0 y 24 ---
        start_range = fila.get("NUM_OF_MONTH_START_RANGE")
        if not pd.isna(start_range) and es_entero(start_range):
            val = int(float(start_range))
            if not (0 <= val <= 24):
                errores.append(
                    f"La columna 'NUM_OF_MONTH_START_RANGE' de la planilla Cargos ClaroUp tiene un valor '{val}' que no cumple la regla 4 (revisar reglas mas arriba)"
                )

        # --- Regla 5: NUM_OF_MONTH_END_RANGE entre 1 y 99 ---
        end_range = fila.get("NUM_OF_MONTH_END_RANGE")
        if not pd.isna(end_range) and es_entero(end_range):
            val = int(float(end_range))
            if not (1 <= val <= 99):
                errores.append(
                    f"La columna 'NUM_OF_MONTH_END_RANGE' de la planilla Cargos ClaroUp tiene un valor '{val}' que no cumple la regla 5 (revisar reglas mas arriba)"
                )

        # --- Regla 6: EXPIRATION_DATE debe ser posterior al 31/12 del año actual ---
        exp_date_raw = fila.get("EXPIRATION_DATE")
        if pd.isna(exp_date_raw) or str(exp_date_raw).strip() == "":
            errores.append("La columna 'EXPIRATION_DATE' tiene valores vacios (revisar Regla 6 mas arriba)")
        else:
            try:
                if isinstance(exp_date_raw, (pd.Timestamp, np.datetime64)):
                    exp_date = pd.Timestamp(exp_date_raw).date()
                else:
                    exp_date = pd.to_datetime(str(exp_date_raw).strip()).date()

                if exp_date <= fecha_limite:
                    errores.append(
                        f"La columna 'EXPIRATION_DATE' ({exp_date.strftime('%d/%m/%Y')}) "
                        f"debe ser posterior al 31/12/{anio_actual} (revisar Regla 6 mas arriba)"
                    )
            except Exception:
                errores.append(
                    f"La columna 'EXPIRATION_DATE' tiene un valor de fecha inválido: '{exp_date_raw}' (revisar Regla 6 mas arriba)"
                )

        # Identificador de fila: usar SKU si está disponible
        sku_val = to_python_type(fila.get("SKU")) if es_entero(fila.get("SKU", None)) else str(fila.get("SKU", "—"))

        if errores:
            resumen.append({
                "sku": sku_val,
                "nombre": str(sku_val),
                "numero_fila": numero_fila,
                "estado": "Con error",
                "alertas": alertas,
                "detalle_error": {
                    "errores": errores,
                    "sku": sku_val,
                    "plan_market": to_python_type(fila.get("PLAN_MARKET")),
                    "equ_commitment_duration": to_python_type(fila.get("EQU_COMMITMENT_DURATION")),
                    "num_of_month_start_range": to_python_type(fila.get("NUM_OF_MONTH_START_RANGE")),
                    "num_of_month_end_range": to_python_type(fila.get("NUM_OF_MONTH_END_RANGE")),
                    "expiration_date": str(fila.get("EXPIRATION_DATE")) if not pd.isna(fila.get("EXPIRATION_DATE", np.nan)) else None,
                    "precio_base": to_python_type(fila.get("LEASING_CHARGE")),
                    "comparaciones": []
                }
            })
        else:
            resumen.append({
                "sku": sku_val,
                "nombre": str(sku_val),
                "numero_fila": numero_fila,
                "estado": "OK",
                "alertas": alertas,
                "detalle_error": None
            })

    return {
        "tipo": "cargos_claroup",
        "total_filas": len(resumen),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }