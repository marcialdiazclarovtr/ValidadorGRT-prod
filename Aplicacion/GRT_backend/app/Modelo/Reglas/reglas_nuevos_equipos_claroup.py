# Reglas validación nuevos equipos claroup

# Para realizar esta validación se usan 2 planillas:
# - "Nuevos Equipos ClaroUp W11.xlsx"
# - "20260128 W5 CR479 macro (envío) v1.xlsx"

# Reglas a validar:

# Regla 1: Verificar que para un mismo SKU existan exactamente 3 nombres con el patrón:
#   ClaroUp {modelo}, ClaroUp PI {modelo}, ClaroUp FIDE {modelo}
#   El nombre del modelo debe ser idéntico en los 3.

# Regla 2: Verificar que los valores de Equipment Rank Value sean consecutivos:
#   - A nivel de toda la columna (sin saltos entre filas)
#   - Dentro de cada SKU (los 3 valores del mismo SKU deben ser consecutivos entre sí)

# Regla 3: Si el nombre contiene "ClaroUp", Equipment Classification debe ser "EUP"

# Regla 4: FINAL S/Iva * 1.19 == valor full de la planilla macro

# Regla 5: Nombre, Color y Model deben tener <= 30 caracteres

# Regla 6: Nombre, Color y Model no deben contener caracteres inválidos
#   Inválidos: / * - # , . ( ) y otros símbolos especiales
#   Permitidos: letras (incluyendo acentos), números y espacios

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger("uvicorn")

# ---------------------------------
# Flags para activar/desactivar validaciones
# ---------------------------------
VALIDAR_REGLA_1 = True   # Patrón de nombres ClaroUp / ClaroUp PI / ClaroUp FIDE
VALIDAR_REGLA_2 = True   # Consecutividad de Equipment Rank Value
VALIDAR_REGLA_3 = True   # Equipment Classification = EUP si nombre contiene ClaroUp
VALIDAR_REGLA_4 = True   # FINAL S/Iva * 1.19 == valor full macro
VALIDAR_REGLA_5 = True   # Largo <= 30 caracteres
VALIDAR_REGLA_6 = True   # Sin caracteres inválidos


# ---------------------------------
# Utilidades
# ---------------------------------
def to_python_type(value):
    """Convierte tipos numpy/pandas a tipos nativos de Python para serialización JSON."""
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


def calcular_precio_con_iva(precio_base: float, tasa_iva: float = 0.19) -> int:
    """Calcula precio con IVA usando redondeo half-up."""
    return int(np.floor(precio_base * (1 + tasa_iva) + 0.5))


def validar_largo_texto(valor: Any, max_len: int = 30) -> bool:
    """Retorna True si el texto supera el largo máximo."""
    if pd.isna(valor):
        return False
    return len(str(valor).strip()) > max_len


def validar_caracteres_invalidos(valor: Any) -> list:
    """Retorna lista de caracteres inválidos encontrados. Lista vacía si no hay."""
    if pd.isna(valor):
        return []
    texto = str(valor).strip()
    caracteres_invalidos = r'[/*\-#,.()[\]{}|\\<>_=+@!$%^&;:\'\"`~?]'
    matches = re.findall(caracteres_invalidos, texto)
    return list(set(matches))


# ---------------------------------
# Validación de columnas requeridas
# ---------------------------------
def validar_columnas_requeridas(
    df_base: pd.DataFrame,
    df_comp: pd.DataFrame
) -> Optional[Dict]:
    columnas_base_requeridas = {
        "Nombre", "SKU", "Make", "Model", "Color",
        "FINAL S/Iva", "Use Category", "Equipment Classification",
        "Equipment Rank Value"
    }
    columnas_comp_requeridas = {"EQUIPMENT_SKU", "valor full"}

    faltantes_base = columnas_base_requeridas - set(df_base.columns)
    if faltantes_base:
        return {"error": f"A la planilla base le faltan columnas: {', '.join(sorted(faltantes_base))}"}

    faltantes_comp = columnas_comp_requeridas - set(df_comp.columns)
    if faltantes_comp:
        return {"error": f"A la planilla macro le faltan columnas: {', '.join(sorted(faltantes_comp))}"}

    return None


# ---------------------------------
# Regla 1: Patrón de nombres por SKU
# ---------------------------------
def extraer_nombre_modelo(nombre: str) -> Optional[str]:
    nombre = str(nombre).strip()
    nombre_lower = nombre.lower()
    if nombre_lower.startswith("claroup fide"):
        return nombre[len("claroup fide "):] if nombre_lower.startswith("claroup fide ") else nombre[len("claroup fide"):]
    elif nombre_lower.startswith("claroup pi"):
        return nombre[len("claroup pi "):] if nombre_lower.startswith("claroup pi ") else nombre[len("claroup pi"):]
    elif nombre_lower.startswith("claroup "):
        return nombre[len("claroup "):]
    return None


def validar_patron_nombres_sku(nombres: List[str], sku: str) -> List[str]:
    errores = []

    if len(nombres) != 3:
        errores.append(f"Se esperaban 3 filas para el SKU {sku} pero se encontraron {len(nombres)} (revisar regla 1)")
        return errores

    prefijos_esperados = ["claroup ", "claroup pi ", "claroup fide "]
    prefijos_encontrados = {p: None for p in prefijos_esperados}

    for nombre in nombres:
        nombre_str = str(nombre).strip()
        nombre_lower = nombre_str.lower()

        if nombre_lower.startswith("claroup fide"):
            prefijo_detectado = "claroup fide "
        elif nombre_lower.startswith("claroup pi"):
            prefijo_detectado = "claroup pi "
        elif nombre_lower.startswith("claroup "):
            prefijo_detectado = "claroup "
        else:
            errores.append(f"El nombre '{nombre_str}' para el SKU {sku} no sigue ningún patrón ClaroUp esperado (revisar regla 1)")
            continue

        if prefijos_encontrados[prefijo_detectado] is not None:
            errores.append(
                f"El prefijo '{prefijo_detectado.strip()}' para el SKU {sku} aparece más de una vez: "
                f"'{prefijos_encontrados[prefijo_detectado]}' y '{nombre_str}' (revisar regla 1)"
            )
        else:
            prefijos_encontrados[prefijo_detectado] = nombre_str

    for prefijo, valor in prefijos_encontrados.items():
        if valor is None:
            errores.append(f"Falta el nombre con prefijo '{prefijo.strip()}' para el SKU {sku} (revisar regla 1 mas arriba)")

    if errores:
        return errores

    """ modelos = [extraer_nombre_modelo(n) for n in prefijos_encontrados.values()]
    if len(set(modelos)) > 1:
        errores.append(f"El nombre del modelo difiere entre las 3 filas: {modelos} para el SKU {sku} (revisar regla 1)") """

    return errores


# ---------------------------------
# Regla 2: Consecutividad de Equipment Rank Value
# ---------------------------------
def validar_consecutividad(df_base: pd.DataFrame) -> List[Dict]:
    """
    Valida que Equipment Rank Value sea consecutivo:
    1. A nivel de toda la columna (sin saltos)
    2. Dentro de cada SKU (los 3 valores deben ser consecutivos entre sí)

    Retorna lista de dicts con {numero_fila, sku, error}
    """
    errores = []

    ranks = df_base["Equipment Rank Value"].tolist()
    skus = df_base["SKU"].tolist()

    # Validación a nivel de columna completa
    for i in range(1, len(ranks)):
        rank_actual = ranks[i]
        rank_anterior = ranks[i - 1]

        try:
            rank_actual_int = int(rank_actual)
        except (ValueError, TypeError):
            errores.append({
                "numero_fila": i + 2,
                "sku": str(skus[i]),
                "error": f"Equipment Rank Value '{rank_actual}' no es un número válido (revisar regla 2)"
            })
            continue

        try:
            rank_anterior_int = int(rank_anterior)
        except (ValueError, TypeError):
            continue

        if rank_actual_int != rank_anterior_int + 1:
            errores.append({
                "numero_fila": i + 2,
                "sku": str(skus[i]),
                "error": (
                    f"Equipment Rank Value {rank_actual_int} no es consecutivo al anterior "
                    f"({rank_anterior_int}) a nivel de columna (revisar regla 2)"
                )
            })

    # Validación dentro de cada SKU
    grupos = df_base.groupby("SKU", sort=False)
    for sku, grupo in grupos:
        ranks_sku = grupo["Equipment Rank Value"].tolist()
        filas_sku = (grupo.index + 2).tolist()  # número de fila en Excel

        try:
            ranks_sku_int = [int(r) for r in ranks_sku]
        except (ValueError, TypeError):
            for j, r in enumerate(ranks_sku):
                try:
                    int(r)
                except (ValueError, TypeError):
                    errores.append({
                        "numero_fila": filas_sku[j],
                        "sku": str(sku),
                        "error": f"Equipment Rank Value '{r}' no es un número válido (revisar regla 2)"
                    })
            continue

        for i in range(1, len(ranks_sku_int)):
            if ranks_sku_int[i] != ranks_sku_int[i - 1] + 1:
                errores.append({
                    "numero_fila": filas_sku[i],
                    "sku": str(sku),
                    "error": (
                        f"Equipment Rank Value {ranks_sku_int[i]} no es consecutivo al anterior "
                        f"({ranks_sku_int[i - 1]}) dentro del SKU {sku} (revisar regla 2)"
                    )
                })

    return errores


# ---------------------------------
# Función principal de validación
# ---------------------------------
def validar_nuevos_equipos_claroup(
    df_base: pd.DataFrame,
    df_comp: pd.DataFrame
) -> Dict[str, Any]:
    """
    Valida la planilla de Nuevos Equipos ClaroUp contra la macro.

    Args:
        df_base: DataFrame de "Nuevos Equipos ClaroUp"
        df_comp: DataFrame de la macro (envío)

    Returns:
        Diccionario con resumen de validación
    """

    # Validar columnas requeridas
    error_cols = validar_columnas_requeridas(df_base, df_comp)
    if error_cols:
        return error_cols

    # Preparar índice de macro por SKU
    df_comp_unico = df_comp.drop_duplicates(subset=["EQUIPMENT_SKU"], keep="first")
    df_comp_unico = df_comp_unico.copy()
    df_comp_unico["EQUIPMENT_SKU"] = df_comp_unico["EQUIPMENT_SKU"].astype(str).str.strip()
    comp_index = df_comp_unico.set_index("EQUIPMENT_SKU")

    df_base = df_base.reset_index(drop=True)

    # Acumular errores por fila (indexados por posición)
    errores_por_fila: Dict[int, List[str]] = {i: [] for i in range(len(df_base))}

    # ---------------------------
    # Regla 1: Patrón de nombres
    # ---------------------------
    if VALIDAR_REGLA_1:
        grupos_sku = df_base.groupby("SKU", sort=False)
        for sku, grupo in grupos_sku:
            nombres = grupo["Nombre"].tolist()
            indices = grupo.index.tolist()
            errores_r1 = validar_patron_nombres_sku(nombres, sku)
            if errores_r1:
                # Asignar los errores a la primera fila del grupo
                errores_por_fila[indices[0]].extend(errores_r1)
    else:
        logger.info("[DEBUG] Validación Regla 1 (patrón nombres) desactivada")

    # ---------------------------
    # Regla 2: Consecutividad
    # ---------------------------
    if VALIDAR_REGLA_2:
        errores_consecutividad = validar_consecutividad(df_base)
        for e in errores_consecutividad:
            # numero_fila es fila Excel (idx + 2), convertir a idx
            idx = e["numero_fila"] - 2
            if 0 <= idx < len(df_base):
                errores_por_fila[idx].append(e["error"])
    else:
        logger.info("[DEBUG] Validación Regla 2 (consecutividad) desactivada")

    # ---------------------------
    # Validación fila por fila (Reglas 3, 4, 5, 6)
    # ---------------------------
    resumen = []

    for idx, row in df_base.iterrows():
        nombre = row["Nombre"]
        sku = row["SKU"]
        modelo = row["Model"]
        color = row["Color"]
        equipment_classification = row["Equipment Classification"]
        equipment_rank_value = row["Equipment Rank Value"]
        precio_sin_iva = row["FINAL S/Iva"]

        errores = list(errores_por_fila[idx])

        # Regla 3: Si nombre contiene "ClaroUp", Equipment Classification debe ser "EUP"
        if VALIDAR_REGLA_3:
            nombre_str = str(nombre).strip()
            if "claroup" in nombre_str.lower() and equipment_classification != "EUP":
                errores.append(
                    f"El SKU {sku} no cumple la regla 3 (revisar reglas mas arriba)"
                )

        # Regla 4: FINAL S/Iva * 1.19 == valor full macro
        precio_comp = None
        diferencia = None

        if VALIDAR_REGLA_4:
            try:
                precio_sin_iva_float = float(
                    str(precio_sin_iva).replace(",", ".").replace("$", "").strip()
                )
                precio_con_iva = calcular_precio_con_iva(precio_sin_iva_float)
            except (ValueError, TypeError):
                errores.append(f"No se pudo convertir FINAL S/Iva '{precio_sin_iva}' a número para el SKU {sku} (revisar regla 4 mas arriba)")
                precio_con_iva = None

            if precio_con_iva is not None:
                sku_str = str(sku).strip()
                if sku_str not in comp_index.index:
                    errores.append(f"El SKU {sku} no existe en planilla macro (revisar regla 4 mas arriba)")
                else:
                    precio_comp = comp_index.loc[sku_str, "valor full"]
                    diferencia = precio_comp - precio_con_iva
                    if diferencia != 0:
                        errores.append(
                            f"El SKU {sku} no cumple con la regla 4 (revisar reglas mas arriba)"
                        )

        # Regla 5: Largo <= 30 caracteres
        if VALIDAR_REGLA_5:
            if validar_largo_texto(nombre):
                errores.append("Nombre supera 30 caracteres (Revisar regla 5 mas arriba)")
            if validar_largo_texto(modelo):
                errores.append("Model supera 30 caracteres (Revisar regla 5 mas arriba)")
            if validar_largo_texto(color):
                errores.append("Color supera 30 caracteres (Revisar regla 5 mas arriba)")

        # Regla 6: Sin caracteres inválidos
        if VALIDAR_REGLA_6:
            chars_nombre = validar_caracteres_invalidos(nombre)
            if chars_nombre:
                errores.append(f"Nombre tiene caracteres inválidos: {', '.join(chars_nombre)} (Revisar regla 6 mas arriba)")

            chars_modelo = validar_caracteres_invalidos(modelo)
            if chars_modelo:
                errores.append(f"Model tiene caracteres inválidos: {', '.join(chars_modelo)} (Revisar regla 6 mas arriba)")

            chars_color = validar_caracteres_invalidos(color)
            if chars_color:
                errores.append(f"Color tiene caracteres inválidos: {', '.join(chars_color)} (Revisar regla 6 mas arriba)")

        # Construir entrada del resumen
        if errores:
            resumen.append({
                "sku": str(sku),
                "nombre": nombre,
                "indice_original": idx,
                "numero_fila": idx + 2,
                "estado": "Con error",
                "detalle_error": {
                    "errores": errores,
                    "nombre": nombre,
                    "model": modelo,
                    "color": color,
                    "equipment_classification": to_python_type(equipment_classification),
                    "equipment_rank_value": to_python_type(equipment_rank_value),
                    "precio_sin_iva": to_python_type(precio_sin_iva),
                    "precio_con_iva": to_python_type(precio_con_iva) if VALIDAR_REGLA_4 else None,
                    "precio_comp": to_python_type(precio_comp),
                    "diferencia": to_python_type(diferencia),
                }
            })
        else:
            resumen.append({
                "sku": str(sku),
                "nombre": nombre,
                "indice_original": idx,
                "numero_fila": idx + 2,
                "estado": "OK",
                "detalle_error": None
            })

    return {
        "tipo": "nuevos_equipos_claroup",
        "total_skus_base": to_python_type(len(df_base)),
        "total_skus_comp": to_python_type(df_comp_unico["EQUIPMENT_SKU"].nunique()),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }