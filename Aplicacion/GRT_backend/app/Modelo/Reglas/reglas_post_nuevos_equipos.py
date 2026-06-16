# reglas_post_nuevos_equipos.py

import pandas as pd
import numpy as np
from typing import Dict, List, Any

# Módulo de validación de reglas para post nuevos equipos

# La validación se realiza con las planillas "20260128 Post Nuevos Equipos v1 transpuesta" y "20260128 W5 CR479 macro (envío) v1"

# Reglas a validar:

# Regla 1:

# Precio_base * 1.19 = Precio_comparación, donde el precio base es el precio de la columna Full Price de la primera planilla, y precio comparación es el precio de la columna valor full de la segunda planilla

# Regla 2:

# Si el valor en la columna Make no es Apple y el valor de Full Price con IVA es menor o igual a 250000, el valor de Equipment Rank Value debe ser 1.

# Regla 3:

# Si el valor en la columna Make no es Apple y el valor de Full Price con IVA es mayor a 250000, el valor de Equipment Rank Value debe ser 3.

# Regla 4: 

# Si el valor en la columna Make es Apple, entonces Equipment Rank Value debe ser 2.

# Regla 5:

# Si el valor en la columna Equipment Rank Value es 4, entonces Equipment Classification debe ser "MDM".

# Regla 6:

# Si el valor en la columna Equipment Classification es "MDM", entonces Use Category debe ser "DATOS"

# Regla 7:

# El nombre, color y modelo del equipo debe ser menor o igual a 30 caracteres.

# Regla 8:

# Los nombres, colores y modelos no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.

def to_python_type(value):
    """Convierte tipos de numpy/pandas a tipos nativos de Python"""
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def calcular_precio_con_iva(precio_base: float, tasa_iva: float = 0.19) -> int:
    """
    Calcula el precio con IVA aplicando redondeo.
    
    Args:
        precio_base: Precio sin IVA
        tasa_iva: Tasa de IVA (por defecto 19%)
    
    Returns:
        Precio con IVA redondeado
    """
    return int(np.floor(precio_base * (1 + tasa_iva) + 0.5))


def validar_columnas_requeridas(
    df_base: pd.DataFrame,
    df_comp: pd.DataFrame
) -> Dict[str, str] | None:
    """
    Valida que ambos dataframes tengan las columnas requeridas.
    
    Returns:
        Dict con error si falta alguna columna, None si todo está OK
    """

    # Columnas requeridas en ambas planillas para poder realizar la comparación

    columnas_base_requeridas = {
        "SKU",
        "Full Price",
        "Nombre",
        "Model",
        "Color",
        "Make",
        "Equipment Rank Value",
        "Equipment Classification"
    }
    columnas_comp_requeridas = {"EQUIPMENT_SKU", "valor full"}

    if columnas_base_requeridas - set(df_base.columns):
        return {"error": "La planilla base no tiene las columnas requeridas"}

    if columnas_comp_requeridas - set(df_comp.columns):
        return {"error": "La planilla de comparación no tiene las columnas requeridas"}
    
    return None

# Regla 7:

# El nombre, color y modelo del equipo debe ser menor o igual a 30 caracteres

def validar_largo_texto(valor: Any, max_len: int = 30) -> bool:
    """
    Retorna True si el texto supera el largo máximo permitido.
    """
    if pd.isna(valor):
        return False
    return len(str(valor).strip()) > max_len

# Regla 8:

# Los nombres, colores y modelos no deben contener caracteres no validos

def validar_caracteres_invalidos(valor: Any) -> bool:
    """
    Retorna lista de caracteres inválidos encontrados en el texto.
    Lista vacía si no hay caracteres inválidos.
    Caracteres inválidos: / * - # , . ( ) y otros símbolos especiales
    Se permiten: letras (incluyendo acentos), números y espacios.
    """
    if pd.isna(valor):
        return []
    
    texto = str(valor).strip()
    
    import re
    caracteres_invalidos = r'[/*\-#,.()[\]{}|\\<>_=+@!$%^&;:\'\"`~?]'
    
    # Encontrar todos los caracteres inválidos únicos
    matches = re.findall(caracteres_invalidos, texto)
    return list(set(matches))  # Elimina duplicados

# Función principal de validación

def validar_grt(
    df_base: pd.DataFrame,
    df_comp: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validación de GRT.
    Valida las siguientes reglas: 
    
    # Regla 1:

    # Precio_base * 1.19 = Precio_comparación, donde el precio base es el precio de la columna Full Price de la primera planilla, y precio comparación es el precio de la columna valor full de la segunda planilla

    # Regla 2:

    # Si el valor en la columna Make no es Apple y el valor de Full Price con IVA es menor o igual a 250000, el valor de Equipment Rank Value debe ser 1.

    # Regla 3:

    # Si el valor en la columna Make no es Apple y el valor de Full Price con IVA es mayor a 250000, el valor de Equipment Rank Value debe ser 3.

    # Regla 4: 

    # Si el valor en la columna Make es Apple, entonces Equipment Rank Value debe ser 2.

    # Regla 5:

    # Si el valor en la columna Equipment Rank Value es 4, entonces Equipment Classification debe ser "MDM".

    # Regla 7:

    # El nombre, color y modelo del equipo debe ser menor o igual a 30 caracteres.

    # Regla 8:

    # Los nombres, colores y modelos no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.
    
    Args:
        df_base: DataFrame con columnas SKU, Full Price, Nombre
        df_comp: DataFrame con columnas EQUIPMENT_SKU, valor full
    
    Returns:
        Diccionario con resumen de la comparación
    """
    # Validar columnas

    error_validacion = validar_columnas_requeridas(df_base, df_comp)
    if error_validacion:
        return error_validacion
    
    # Preparar datos de comparación

    df_comp_unico = df_comp.drop_duplicates(
        subset=["EQUIPMENT_SKU"],
        keep="first"
    )
    comp_index = df_comp_unico.set_index("EQUIPMENT_SKU")
    
    resumen = []

    # Iterar sobre cada SKU de la planilla base

    df_base = df_base.reset_index(drop=True)

    for idx, base_row in df_base.iterrows():
        equipment_classification = base_row["Equipment Classification"]
        use_category = base_row["Use Category"]

        sku = base_row["SKU"]
        nombre = base_row["Nombre"]
        precio_base = base_row["Full Price"]
        precio_base_iva = calcular_precio_con_iva(precio_base)

        nombre = base_row["Nombre"]
        modelo = base_row["Model"]
        color = base_row["Color"]

        make = base_row["Make"]
        # Normalizar make para comparación case-insensitive
        make_normalizado = str(make).strip().lower() if pd.notna(make) else ""
        equipment_rank_value = base_row["Equipment Rank Value"]

        errores = []

        # Regla 4: Si Make = Apple, entonces Equipment Rank Value debe ser 2

        rank = int(equipment_rank_value) if pd.notna(equipment_rank_value) else None

        if make_normalizado == "apple" and rank != 2:
            # errores.append("Make es Apple pero Equipment Rank Value no es 2 (Regla 4)")
            
            errores.append(f"El SKU '{sku}' no cumple la regla 3 (revisar reglas mas arriba)")

        # Regla 2 y 3: Validar Equipment Rank Value según Make y Precio

        if make_normalizado != "apple":  # Solo aplica cuando NO es Apple
            if precio_base_iva <= 250000:
                # Regla 2: Precio ≤ 250k → Rank debe ser 1
                if rank != 1:
                    """ errores.append(
                        f"Make no es Apple y precio con IVA (${precio_base_iva}) es ≤ 250,000, "
                        f"pero Equipment Rank Value es {rank} (debería ser 1) (Regla 2)"
                    ) """
            
                    errores.append(f"El SKU '{sku}' no cumple la regla 2 (revisar reglas mas arriba)")
            else:
                # Regla 3: Precio > 250k → Rank debe ser 3
                if rank != 3:
                    """ errores.append(
                        f"Make no es Apple y precio con IVA (${precio_base_iva}) es > 250,000, "
                        f"pero Equipment Rank Value es {rank} (debería ser 3) (Regla 3)"
                    ) """
            
                    errores.append(f"El SKU '{sku}' no cumple la regla 3 (revisar reglas mas arriba)")

        # Regla 5: Equipment Rank Value = 4 => Equipment Classification = "MDM"

        if rank == 4 and equipment_classification != "MDM":
            """ errores.append(
                "Equipment Rank Value es 4 pero Equipment Classification no es MDM (Regla 5)"
            ) """
            
            errores.append(f"El SKU '{sku}' no cumple la regla 5 (revisar reglas mas arriba)")

        # Regla 6: Si el valor en la columna Equipment Classification es "MDM", entonces Use Category debe ser "DATOS"

        if equipment_classification == "MDM" and "DATOS" not in use_category:
            """ errores.append(
                "Equipment Classification es MDM pero Use Category no es DATOS (Regla 6)"
            ) """
            
            errores.append(f"El SKU '{sku}' no cumple la regla 6 (revisar reglas mas arriba)")

        # Regla 7: El nombre, color y modelo del equipo debe ser menor o igual a 30 caracteres

        if validar_largo_texto(nombre):
            errores.append(f"Nombre supera 30 caracteres (revisar Regla 7 mas arriba) para el SKU '{sku}'")

        if validar_largo_texto(modelo):
            errores.append(f"Model supera 30 caracteres (revisar Regla 7 mas arriba) para el SKU '{sku}'")

        if validar_largo_texto(color):
            errores.append(f"Color supera 30 caracteres (revisar Regla 7 mas arriba) para el SKU '{sku}'")

        # Regla 8: Los nombres, colores y modelos no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales. Se permiten: letras (incluyendo acentos), números y espacios.

        chars_invalidos_nombre = validar_caracteres_invalidos(nombre)
        if chars_invalidos_nombre:
            errores.append(f"Nombre tiene caracteres inválidos: {', '.join(chars_invalidos_nombre)} (revisar Regla 8 mas arriba) para el SKU '{sku}'")

        chars_invalidos_modelo = validar_caracteres_invalidos(modelo)
        if chars_invalidos_modelo:
            errores.append(f"Modelo tiene caracteres inválidos: {', '.join(chars_invalidos_modelo)} (revisar Regla 8 mas arriba) para el SKU '{sku}'")

        chars_invalidos_color = validar_caracteres_invalidos(color)
        if chars_invalidos_color:
            errores.append(f"Color tiene caracteres inválidos: {', '.join(chars_invalidos_color)} (revisar Regla 8 mas arriba) para el SKU '{sku}'")

        precio_comp = None
        diferencia = None

        # Cataloga como error si no se encuentra el SKU de una fila de la primera planilla en la segunda planilla
        if sku not in comp_index.index:
            errores.append(f"El SKU '{sku}' no existe en planilla de comparación")
        else:
            # Regla 1: Precio_base (primera planilla) * 1.19 = Precio_comparación (segunda planilla)
            comp_row = comp_index.loc[sku]
            precio_comp = comp_row["valor full"]
            diferencia = precio_comp - precio_base_iva

            if diferencia != 0:
                errores.append(f"El SKU '{sku}' no cumple la Regla 1 (revisar reglas mas arriba)")

        # Construir comparaciones
        comparaciones = []

        if sku not in comp_index.index:
            comparaciones.append({
                "regla": "SKU no encontrado",
                "descripcion": "SKU no existe en planilla de comparación",
                "precio_base_iva": None,
                "precio_comp": None,
                "diferencia": None
            })
        elif diferencia != 0:
            comparaciones.append({
                "regla": "Regla 1",
                "descripcion": "Full Price * 1.19 vs valor full macro",
                "precio_base_iva": to_python_type(precio_base_iva),
                "precio_comp": to_python_type(precio_comp),
                "diferencia": to_python_type(diferencia)
            })

        if errores:
            resumen.append({
                "sku": str(sku),
                "indice_original": idx,
                "numero_fila": idx + 2,
                "nombre": nombre,
                "estado": "Con error",
                "detalle_error": {
                    "errores": errores,
                    "nombre": nombre,
                    "model": modelo,
                    "color": color,
                    "equipment_classification": to_python_type(equipment_classification),
                    "use_category": to_python_type(use_category),
                    "make": to_python_type(make),
                    "equipment_rank_value": to_python_type(equipment_rank_value),
                    "precio_base": to_python_type(precio_base),
                    "comparaciones": comparaciones
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

    # Construir resultado final
    resultado = {
        "tipo": "post_nuevos_equipos",
        "total_skus_base": to_python_type(len(df_base)),
        "total_skus_comp": to_python_type(df_comp_unico["EQUIPMENT_SKU"].nunique()),
        "total_ok": sum(1 for r in resumen if r["estado"] == "OK"),
        "total_error": sum(1 for r in resumen if r["estado"] == "Con error"),
        "resumen": resumen
    }

    return resultado