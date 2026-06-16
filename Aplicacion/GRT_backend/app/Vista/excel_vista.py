# Construye el payload para enviar al frontend con la estructura esperada

def construir_payload(nombre_archivo, sheets):
    return {
        "fileName": nombre_archivo,
        "sheets": sheets
    }