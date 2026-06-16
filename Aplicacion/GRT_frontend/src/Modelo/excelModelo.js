// Crea el estado de un archivo Excel con su nombre y hojas para el estado de React
export function crearExcelState(excel) {
  return {
    fileName: excel.fileName,
    sheets: excel.sheets
  }
}