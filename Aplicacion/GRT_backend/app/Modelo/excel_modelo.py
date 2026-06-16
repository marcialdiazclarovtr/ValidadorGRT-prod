import pandas as pd
import logging

COLUMNAS_FECHA_STR = ["EFFECTIVE_DATE", "EXPIRATION DATE", "EXPIRATION_DATE"]

logger = logging.getLogger("uvicorn")

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

def _leer_col_fechas_openpyxl(excel_path: str, sheet_index_or_name, header_row: int = 0) -> dict:
    df_str = pd.read_excel(
        excel_path,
        sheet_name=sheet_index_or_name,
        header=header_row,
        engine="openpyxl",
        dtype=str
    )
    resultado = {}
    for col in COLUMNAS_FECHA_STR:
        if col in df_str.columns:
            resultado[col] = df_str[col].str.strip().tolist()
    return resultado

def leer_primera_hoja_desde_path(excel_path: str):
    logger.info(f"Leyendo planilla en el path: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name=0, keep_default_na=False)
    fechas = _leer_col_fechas_openpyxl(excel_path, 0)
    for col, valores in fechas.items():
        if col in df.columns:
            df[col] = valores[:len(df)]
            # logger.info(f"[DEBUG FECHA COL] {col}: {df[col][:50]}")
    return df

def leer_hoja_desde_path(path: str, nombre_hoja: str, fila_header: int = 0, keep_default_na=False):
    logger.info(f"Leyendo planilla en el path: {path}")
    df = pd.read_excel(path, sheet_name=nombre_hoja, header=fila_header, keep_default_na=False)
    fechas = _leer_col_fechas_openpyxl(path, nombre_hoja, header_row=fila_header)
    for col, valores in fechas.items():
        if col in df.columns:
            df[col] = valores[:len(df)]
            # logger.info(f"[DEBUG FECHA COL] {col}: {df[col][:50]}")
    return df

def convert_to_serializable(obj):
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Timedelta):
        return str(obj)
    if pd.isna(obj):
        return None
    return obj

def procesar_excel(file):
    excel = pd.ExcelFile(file)
    sheets_data = []
    for sheet_name in excel.sheet_names:
        df = excel.parse(sheet_name)
        df = df.map(convert_to_serializable)
        sheets_data.append({
            "sheetName": sheet_name,
            "data": df.fillna("").to_dict(orient="records")
        })
    return sheets_data