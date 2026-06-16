const API_URL = window.location.origin

// Envía archivos Excel al backend y procesa la respuesta en streaming (Server-Sent Events)
export async function streamExcel(files, onExcel) {
  // Prepara los archivos en FormData para el envío
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))

  // Realiza la petición al endpoint de streaming
  const response = await fetch(
    `${API_URL}/upload-excel-stream`,
    { method: 'POST', body: formData }
  )

  // Configura el lector para procesar la respuesta en chunks
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  // Lee y procesa los datos a medida que llegan
  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    // Decodifica el chunk y lo agrega al buffer
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop()  // Guarda el evento incompleto en el buffer

    // Procesa cada evento SSE completo
    events.forEach(event => {
      if (event.startsWith('data: ')) {
        onExcel(JSON.parse(event.replace('data: ', '')))
      }
    })
  }
}

// Descarga la planilla de subsidios generada después de la validación
export async function descargarPlanillaSubsidios(planillaId) {
  const url = `${API_URL}/descargar-planilla-subsidios/${planillaId}`
  const response = await fetch(url, { method: 'GET' })
  const blob = await response.blob()
  const blobUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = 'planilla_subsidios.xlsx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(blobUrl)
}

// Función para comparar GRT llamando al endpoint del backend
export async function validarGRT(files) {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))

  const response = await fetch(
    `${API_URL}/validar-grt`,
    {
      method: 'POST',
      body: formData
    }
  )

  return await response.json()
}

// Obtiene una página del resumen de subsidios
export async function obtenerResumenSubsidios(resumenId, page = 1, pageSize = 500, soloErrores = false) {
  const response = await fetch(
    `${API_URL}/resumen-subsidios/${resumenId}?page=${page}&page_size=${pageSize}&solo_errores=${soloErrores}`,
    { method: 'GET' }
  )
  return await response.json()
}