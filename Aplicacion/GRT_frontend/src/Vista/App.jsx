import React, { useRef, useState, useEffect } from 'react'
import './App.css'
import fondo from './assets/fondo_claro.jpeg'
import VirtualizedTable from './VirtualizedTable'
import { validarGRT, streamExcel, descargarPlanillaSubsidios, obtenerResumenSubsidios } from '../Controlador/excelControlador'
import { exportarExcel, exportarExcelUna, exportarPDF, exportarPDFUna } from '../Controlador/exportControlador'

function App() {
  // Bloquear el comportamiento por defecto del navegador para drag & drop
  useEffect(() => {
    const preventDefault = (e) => {
      e.preventDefault()
      e.stopPropagation()
    }

    window.addEventListener('dragover', preventDefault)
    window.addEventListener('drop', preventDefault)

    return () => {
      window.removeEventListener('dragover', preventDefault)
      window.removeEventListener('drop', preventDefault)
    }
  }, [])

  // Bandera para activar/desactivar la carga de los archivos excel en el front end
  const ENABLE_EXCEL_LOAD = false

  // Duración del flujo
  const [duracionValidacion, setDuracionValidacion] = useState(null)

  // Alertas globales para validación de subsidios
  const [mostrarAlertasGlobales, setMostrarAlertasGlobales] = useState({})

  // Estado para el limite de filas
  const [limitFilas, setLimitFilas] = useState(50)

  // Referencia al input file oculto para abrirlo programáticamente
  const fileInputRef = useRef(null)
  
  // Estado para almacenar los archivos seleccionados por el usuario
  const [files, setFiles] = useState([])

  // Estado para rastrear qué archivos están seleccionados para procesar
  const [selectedFiles, setSelectedFiles] = useState([])
  
  // Estado para almacenar los datos de Excel procesados que se reciben del backend
  const [excelData, setExcelData] = useState([])

  // Estado para la comparación de las planillas
  const [grtResult, setGrtResult] = useState(null)
  const [grtError, setGrtError] = useState(null)

  // Estado para expandir filas
  const [expandedFila, setExpandedFila] = useState(null)

  // Estado para mostrar mensaje "procesando planillas"
  const [loading, setLoading] = useState(false)

  // Estados para la paginación
  const [subsidiosResumen, setSubsidiosResumen] = useState({}) // { resumenId: { filas, page, totalPages, loadingPage } }


  const handleButtonClick = () => {
    fileInputRef.current.click()
  }

  const handleFileChange = (event) => {
    const selectedFiles = Array.from(event.target.files)
    setFiles(prev => [...prev, ...selectedFiles])
  }

  const handleDrop = (event) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(false)
    const droppedFiles = Array.from(event.dataTransfer.files).filter(
      f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
    )
    if (droppedFiles.length > 0) {
      setFiles(prev => [...prev, ...droppedFiles])
    }
  }

  const handleDragOver = (event) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (event) => {
    event.preventDefault()
    setIsDragging(false)
  }

  // Estado para arrastrar las planillas
  const [isDragging, setIsDragging] = useState(false)

  // Maneja la selección/deselección de archivos
  const handleFileSelection = (index) => {
    setSelectedFiles(prev => {
      if (prev.includes(index)) {
        // Si ya está seleccionado, lo quita
        return prev.filter(i => i !== index)
      } else {
        // Si no está seleccionado, lo agrega
        return [...prev, index]
      }
    })
  }

  // Maneja la selección/deselección de todos los archivos
  const handleSelectAll = () => {
    if (selectedFiles.length === files.length) {
      // Si todos están seleccionados, deselecciona todos
      setSelectedFiles([])
    } else {
      // Si no todos están seleccionados, selecciona todos
      setSelectedFiles(files.map((_, index) => index))
    }
  }

  // Cargar página subsidios
  const cargarPaginaSubsidios = async (resumenId, page) => {
    console.log('filtrarOK al cargar página:', filtrarOK)
    setSubsidiosResumen(prev => ({
      ...prev,
      [resumenId]: { ...prev[resumenId], loadingPage: true }
    }))
    const data = await obtenerResumenSubsidios(resumenId, page, 500, filtrarOK)
    setSubsidiosResumen(prev => ({
      ...prev,
      [resumenId]: {
        filas: data.filas,
        page: data.page,
        totalPages: data.total_pages,
        loadingPage: false
      }
    }))
  }
  // Procesa los archivos y recibe los datos en streaming
  const handleGenerateVenta = async () => {
    // No hace nada si está desactivada la carga de los archivos en el front
    if (!ENABLE_EXCEL_LOAD) {
      console.log('Carga de archivos desactivada')
      return
    }

    setExcelData([])  // Limpia los datos anteriores
    await streamExcel(files, excel =>
      setExcelData(prev => [...prev, excel])  // Agrega cada archivo a medida que llega
    )
  }

  // Envía dos planillas al backend, y muestra información de cada una
  const handleInfoGRT = async () => {
    const selected = selectedFiles.map(i => files[i])

    if (selected.length < 1) {
      setGrtError('Debes seleccionar al menos 1 planilla')
      setGrtResult(null)
      return
    }

    setGrtError(null)
    setGrtResult(null)
    setLoading(true)

    try {
      const result = await validarGRT(selected)
      console.log('result completo:', JSON.stringify(result, null, 2))

      if (result.error) {
        setGrtError(result.error)
        setGrtResult(null)
        return
      }

      setGrtResult(result)
      if (result.duracion_segundos !== undefined) {
        setDuracionValidacion(result.duracion_segundos)
      }

      // Cargar primera página de subsidios si existe
      result.validaciones.forEach(v => {
        if (v.resultado.resumen_id) {
          cargarPaginaSubsidios(v.resultado.resumen_id, 1)
        }
      })
    } catch (error) {
      console.log('Error capturado:', error)
      setGrtError('Error interno del servidor. Por favor revisa los archivos e intenta de nuevo.')
      setGrtResult(null)
    } finally {
      setLoading(false)
    }
  }

  // Borrar planillas subidas
  const handleDeleteSelected = () => {
    const newFiles = files.filter((_, index) => !selectedFiles.includes(index))
    setFiles(newFiles)
    setSelectedFiles([])
    setGrtResult(null)
    setGrtError(null)
  }

  // Función para renderizar texto con los primeros 30 caracteres en negrita
  const renderTextoConLimite = (texto, tieneError) => {
    if (!tieneError || !texto || texto === '—') {
      return texto ?? '—'
    }
    
    const textoStr = String(texto)
    
    if (textoStr.length <= 30) {
      return <strong>{textoStr}</strong>
    }
    
    return (
      <>
        <strong>{textoStr.slice(0, 30)}</strong>
        {textoStr.slice(30)}
      </>
    )
  }

  // Mapeo de colores por regla
  const coloresPorRegla = {
    0: '#dc3545',  // Rojo
    1: '#fd7e14',  // Naranja
    2: '#ffc107',  // Amarillo
    3: '#20c997',  // Verde azulado
    4: '#0dcaf0',  // Cyan
    5: '#6f42c1',  // Púrpura
    6: '#d63384',  // Rosa
    7: '#6c757d'   // Gris
  }

  // Mapeo del nombre de validación

  const nombreTipoValidacion = {
    'financiamiento': 'Financiamiento',
    'grt_pie': 'GRT PIE',
    'precios_full': 'Precios Full',
    'equipos_accesorios': 'Equipos Accesorios',
    'equipos_standalone': 'Equipos Standalone',
    'cargos_claroup': 'Cargos ClaroUp',
    'post_nuevos_equipos': 'Post Nuevos Equipos',
    'subsidios_claroup': 'Subsidios ClaroUp',
    'nuevos_equipos_claroup': 'Nuevos Equipos ClaroUp',
  }

  // Explicación de cada regla para cada tipo de validación
  const explicacionesPorTipo = {
    precios_full: {
      titulo: 'Validación Precios Full',
      planillas: 'Precios Full y Macro',
      reglas: {
        1: 'Para un SKU determinado, el precio que aparece en la columna FINAL S/IVA de la planilla de Precios Full, multiplicado por 1.19 (con IVA) , debe ser igual al precio que aparece en la columna C/iva de la misma planilla.',
        2: 'Para un SKU determinado, el valor de la columna "valor full" en la planilla Macro debe tener el mismo precio que el de la columna C/iva en la planilla de Precios Full.',
        3: 'Para un SKU determinado, si el nombre en la columna "Nombre" de la planilla de Precios Full contiene la palabra “ClaroUp”, deben haber 3 repeticiones de ese SKU.'
      }
    },

    equipos_accesorios: {
      titulo: 'Validación Equipos Accesorios',
      planillas: 'Carga Equipos Accesorios y Planilla de Precios (nueva)',
      reglas: {
        1: 'La longitud de los valores de las columnas nombre, color y modelo de la planilla Equipos Accesorios debe ser menor o igual a 30 caracteres.',
        2: 'Los valores de las columnas nombre, color y modelo de la planilla Equipos Accesorios no deben contener caracteres inválidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten letras (incluyendo acentos), números y espacios.',
        3: 'Para un SKU determinado, el precio en la columna FULL PRICE de la planilla de Equipos Accesorios multiplicado por 1,19 (con IVA) debe ser igual al precio de la columna Precio Oferta, en la hoja "Accesorios + IOT + BAM" de la Planilla de Precios.'
      }
    },

    equipos_standalone: {
      titulo: 'Validación Equipos Standalone',
      planillas: 'Carga equipos SKU Único y Planilla de Precios (nueva)',
      reglas: {
        1: 'Para un SKU determinado, el precio de la columna Full Price de la planilla Carga Equipos SKU Único multiplicado por 1,19 (con IVA) debe ser igual al precio que tiene dicho SKU en la planilla Planilla de Precios (nueva). La columna de la Planilla de Precios donde está el precio depende de si el nombre del producto en la planilla de precios comienza con "EP", "FIDE", o "PRE" de la siguiente forma: si el nombre comienza con "PRE" el precio está en "Precio Liberado / Prepago", si el nombre comienza con "EP" el precio está en "Precio Equipo + Plan Contado", si el nombre comienza con "FIDE" el precio está en "Precio Recambio Contado".',
        2: 'Los nombres, colores y modelos (columnas Nombre, COLOR y Model de la planilla Carga equipos SKU Único) no deben contener caracteres inválidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.',
        3: 'El nombre, color y modelo (columnas Nombre, COLOR y Model de la planilla Carga equipos SKU Único) del equipo debe ser menor o igual a 30 caracteres.'
      }
    },

    cargos_claroup: {
      titulo: 'Validación Cargos ClaroUP',
      planillas: 'Cargos ClaroUp',
      reglas: {
        1: 'Las columnas numéricas CONCAT, SKU, OFFER_RANK, EQUIPMENT_RANK, EQU_COMMITMENT_DURATION, NUM_OF_MONTH_START_RANGE, NUM_OF_MONTH_END_RANGE de la planilla Cargos ClaroUp deben tener solo números enteros sin decimales ni valores no numéricos, y las columnas LEASING_CHARGE, Valor Cuota, PURCHASE_CHARGE deben tener solo números sin valores no numéricos (pueden tener decimales).',
        2: 'La columna “PLAN_MARKET” solo puede tener los valores “PERSONA” y “PYME Y EMPRESAS”.',
        3: 'La columna “EQU_COMMITMENT_DURATION” solo puede tener el valor 24.',
        4: 'La columna “NUM_OF_MONTH_START_RANGE” solo puede tener valores enteros desde el 0 al 24.',
        5: 'La columna “NUM_OF_MONTH_END_RANGE” solo puede tener valores enteros desde el 1 al 99.',
        6: 'Las fechas de la columna EXPIRATION_DATE deben ser posteriores a el 31 de diciembre del año actual.'
      }
    },

    subsidios_claroup: {
      titulo: 'Validación Subsidios',
      planillas: 'Subsidio ClaroUp, Planilla de Precios (nueva), Macro',
      reglas: {
        1: 'Las fechas de las columnas deben seguir el siguiente formato: Planilla macro: Columna “EFFECTIVE_DATE”: AAAA-MM-DD 00:00:00, Columna “EXPIRATION DATE“: DD-MM-AAAA 00:00:00. Planilla subsidio claroup: Columna “EFFECTIVE_DATE”: DD-MM-AAAA 00:00:00, Columna “EXPIRATION_DATE”: DD-MM-AAAA 00:00:00',
        2: 'El valor de la columna "Resultado" (Total - Cargo Activación) debe ser 0 al final de la validación (Resultado = Total - Cargo Activación). El valor de resultado se obtiene de la siguiente forma: Cargo Activación = "Pie + 12 Cuotas" de la planilla de precios según OR, Subsidio Claro Up = DISCOUNT_RATE de la planilla de subsidios, Subsidio 2 GRT = columna "Subs 2" de la macro, Valor Full = columna "valor full" de la macro, Valor full sin iva = Valor Full / 1.19, Total sin iva = Valor full sin iva - Subsidio 2 GRT - Subsidio Claro Up, Total = Total sin iva * 1.19 (redondeado a entero), Resultado = Total - Cargo Activación.',
        3: 'Las fechas de expiración de las columnas "EXPIRATION DATE" (planilla macro) y "EXPIRATION_DATE" (planilla de subsidios) deben ser iguales o posteriores a la fecha actual pero sumándole un año.'
      }
    },

    nuevos_equipos_claroup: {
      titulo: 'Validación Nuevos Equipos ClaroUP',
      planillas: 'Nuevos Equipos ClaroUp y Macro',
      reglas: {
        1: 'Verificar que para un SKU determinado existan exactamente 3 nombres con el patrón "ClaroUp {modelo del equipo}", "ClaroUp PI {modelo}", "ClaroUp FIDE {modelo}" en la planilla Nuevos Equipos ClaroUp.',
        2: 'Para un SKU determinado los valores de Equipment Rank Value deben ser números consecutivos (en la planilla Nuevos Equipos ClaroUp).',
        3: 'Si el nombre contiene "ClaroUp" para un SKU determinado, Equipment Classification debe ser "EUP" (en la planilla Nuevos Equipos ClaroUp).',
        4: 'Para un SKU determinado el valor de la columna FINAL S/Iva en la planilla Nuevos Equipos ClaroUp multiplicado por 1.19 (con IVA) debe ser igual al valor full de la planilla macro.',
        5: 'Los valores de las columnas Nombre, Color y Model (planilla Nuevos Equipos ClaroUp) deben tener como máximo una longitud de 30 caracteres.',
        6: 'Los valores de las columnas Nombre, Color y Model (planilla Nuevos Equipos ClaroUp) no deben contener caracteres inválidos como / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.'
      }
    },

    financiamiento: {
      titulo: 'Validación Financiamiento',
      planillas: 'Planilla de precios y Macro',
      reglas: {
        1: 'El valor de la columna “Valor Full Contado” (debajo de “Canales Masivos (Tarjeta de Crédito, Débito y Efectivo)”) para un SKU determinado debe ser igual al de la columna “valor full” de la planilla Macro para dicho SKU.',
        2: 'El valor de la columna "Total QA” para un SKU determinado en la planilla de precios (debajo de "Portabilidad" o "Financiamiento", dependiendo de si “ORDER_ACTIVITY” es "PI" o "R" en la tabla macro) debe ser igual al valor de la columna “C.A.” en la planilla macro para dicho SKU.'
      }
    },

    grt_pie: {
      titulo: 'Validación GRT Pie',
      planillas: 'Planilla de Precios (nueva) y GRT PIE',
      reglas: {
        1: 'Para un SKU determinado, el precio de la columna "PVP s/IVA" (multiplicado por 1,19 (con IVA)) de la planilla GRT PIE debe ser igual al que está en la planilla de precios. La columna que tiene el precio en la planilla de precios depende del valor de la columna "OrderType" para dicho SKU en la planilla GRT PIE. Si el valor de "OrderType" es "PI", el precio está en la columna "Pie" de la planilla de precios (debajo de "Portabilidad"), en cambio si el valor de "OrderType" es "R", el precio está en la columna "Pie" de la planilla de precios (debajo de "Recambio").'
      }
    },

    post_nuevos_equipos: {
      titulo: 'Validación Post Nuevos Equipos',
      planillas: 'Post Nuevos Equipos transpuesta y Macro',
      reglas: {
        1: 'Para un SKU determinado, el precio "Full Price" de la planilla Post Nuevos Equipos multiplicado por 1.19 (con IVA) debe ser igual al precio "valor full" de la planilla macro.',
        2: 'Para un SKU determinado, si Make no es Apple y el valor de Full Price con IVA es menor o igual a 250000, el valor de Equipment Rank Value debe ser 1.',
        3: 'Para un SKU determinado, si Make no es Apple y el valor de Full Price con IVA es mayor a 250000, el valor de Equipment Rank Value debe ser 3.',
        4: 'Para un SKU determinado, si el valor en la columna Make es Apple, entonces Equipment Rank Value debe ser 2.',
        5: 'Para un SKU determinado, si el valor en la columna Equipment Rank Value es 4, entonces Equipment Classification debe ser "MDM".',
        6: 'Para un SKU determinado, si el valor en la columna Equipment Classification es "MDM", entonces Use Category debe ser "DATOS".',
        7: 'La longitud de los valores de las columnas nombre, color y modelo del equipo en la planilla Post Nuevos Equipos debe ser menor o igual a 30 caracteres.',
        8: 'La longitud de los valores de las columnas nombre, color y modelo en la planilla Post Nuevos Equipos no deben contener caracteres inválidos como / * - # , . ( ) y otros símbolos especiales, se permiten: letras (incluyendo acentos), números y espacios.'
      }
    }
  }

  const obtenerExplicaciones = (tipo) => {
    return explicacionesPorTipo[tipo] || {}
  }

  // Función para obtener el número de regla del mensaje de error
  const obtenerNumeroRegla = (error) => {
    const match = error.match(/\(Regla (\d+)\)/)
    return match ? parseInt(match[1]) : null
  }

  // Función para obtener color del error
  const obtenerColorError = (error) => {
    const regla = obtenerNumeroRegla(error)
    return regla !== null ? coloresPorRegla[regla] : '#000'
  }
  
  // Función para obtener el color de un atributo si tiene error
  const obtenerColorAtributo = (errores, nombreAtributo) => {
    const erroresRelacionados = errores.filter(e =>
      e.toLowerCase().includes(nombreAtributo.toLowerCase())
    )

    if (erroresRelacionados.length === 0) return null
    return obtenerColorError(erroresRelacionados[0])
  }

  // Función para descargar la planilla después de la validación de subsidios

  const handleDescargarPlanillaSubsidios = (planillaId) => {
    descargarPlanillaSubsidios(planillaId)
  }

  // Función para filtrar los resultados de la validación al exportar a PDF

  const construirValidacionesFiltradas = () => {
    return grtResult.validaciones.map(v => {
      const r = v.resultado
      if (r.error || !filtrarOK) return v
      return {
        ...v,
        resultado: {
          ...r,
          resumen: r.resumen.filter(row =>
            row.estado === 'Con error' || row.alertas?.length > 0
          )
        }
      }
    })
  }

  // Calcular si el total de filas de todas las planillas supera el límite
  const filtrarOK = grtResult
    ? grtResult.validaciones.reduce((acc, v) => {
        const r = v.resultado
        if (r.error) return acc
        return acc + (r.total_filas ?? r.total_skus_base ?? 0)
      }, 0) > limitFilas
    : false

  return (
    <div
      className={`app ${excelData.length > 0 ? 'app-with-data' : ''}`}
      style={{ backgroundImage: `url(${fondo})` }}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <div className="content">
        <div className="upload-container">
          <h1 className="title">Comparativa GRT</h1>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '10px', fontSize: '0.9rem' }}>
            <label htmlFor="limitFilas">Mostrar solo filas con errores y alertas si el total de filas de las planillas supera las:</label>
            <input
              id="limitFilas"
              type="number"
              min={1}
              value={limitFilas}
              onChange={e => setLimitFilas(parseInt(e.target.value) || 1)}
              style={{ width: '70px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #ccc' }}
            />
            <span>filas</span>
          </div>
          <div className="main-content">
            <div className={`upload-area ${isDragging ? 'drag-over' : ''}`}>
              <div className={`buttons-container ${
                files.length > 0 && selectedFiles.length > 0 ? 'four-buttons' : ''
              }`}>
                {/* Botón Subir planillas */}
                <div className="button-group">
                  <div className="upload-icon">
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#4A90E2" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <button
                    className="browse-button"
                    onClick={handleButtonClick}
                  >
                    Subir planillas
                  </button>
                </div>

                {/* Botón Mostrar planillas en front (oculto)  */}
                {false && files.length > 0 && (
                  <div className="button-group">
                    <div className="upload-icon">
                      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#28a745" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                        <polyline points="10 9 9 9 8 9" />
                      </svg>
                    </div>
                    <button
                      className="generate-button"
                      onClick={handleGenerateVenta}
                    >
                      Mostrar planillas en front
                    </button>
                  </div>
                )}

                {/* Botón Mostrar información de las planillas */}
                {files.length > 0 && (
                  <div className="button-group">
                    <div className="upload-icon">
                      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#28a745" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                        <polyline points="10 9 9 9 8 9" />
                      </svg>
                    </div>
                    <button
                      className="generate-button"
                      onClick={handleInfoGRT}
                    >
                      Comparativa GRT
                    </button>
                  </div>
                )}

                

                {/* Botón Borrar seleccionadas */}
                {selectedFiles.length > 0 && (
                  <div className="button-group">
                    <div className="upload-icon">
                      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#6c757d" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <path d="M10 11v6" />
                        <path d="M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </div>
                    <button
                      className="browse-button"
                      style={{ backgroundColor: '#6c757d', color: 'white', borderColor: '#6c757d' }}
                      onClick={handleDeleteSelected}
                    >
                      Borrar seleccionadas
                    </button>
                  </div>
                )}

                {/* Botón Limpiar todo */}
                {files.length > 0 && (
                  <div className="button-group">
                    <div className="upload-icon">
                      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke='#dc3545' strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <path d="M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </div>
                    <button
                      className="browse-button"
                      style={{ backgroundColor: '#dc3545', color: 'white', borderColor: '#dc3545' }}
                      onClick={() => {
                        setFiles([])
                        setSelectedFiles([])
                        setGrtResult(null)
                        setGrtError(null)
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                    >
                      Limpiar todo
                    </button>
                  </div>
                )}
              </div>

              {/* Input oculto */}
              <input
                type="file"
                accept=".xls,.xlsx"
                multiple
                ref={fileInputRef}
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
            </div>

            <div className="files-section">
              <div className="files-title-container">
                {files.length > 0 && (
                  <label className="checkbox-container checkbox-all">
                    <input
                      type="checkbox"
                      checked={files.length > 0 && selectedFiles.length === files.length}
                      onChange={handleSelectAll}
                      className="file-checkbox"
                    />
                    <span className="checkbox-custom"></span>
                  </label>
                )}
                <h3 className="files-title">Archivos subidos:</h3>
              </div>

              <div className="files-list">
                {files.length === 0 ? (
                  <p className="no-files">No se han subido archivos</p>
                ) : (
                  <ul>
                    {files.map((file, index) => (
                      <li key={index} className="file-item">
                        <label className="checkbox-container">
                          <input
                            type="checkbox"
                            checked={selectedFiles.includes(index)}
                            onChange={() => handleFileSelection(index)}
                            className="file-checkbox"
                          />
                          <span className="checkbox-custom"></span>
                          <span className="file-name">{file.name}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Mensaje de carga */}
        {loading && (
          <div className="excel-content">
            <p style={{ fontWeight: '600', textAlign: 'center' }}>
              ⏳ Procesando planillas...
            </p>
          </div>
        )}

        {/* Muestra de resultados de comparativa */}
        {grtResult && (
          <div className="excel-content">
            <h2>Resultado comparación GRT</h2>

            {/* 🔽 TABLA RESUMEN GLOBAL */}
            <table className="resumen-global">
            <thead>
              <tr>
                <th style={{ width: '40%', color: 'white' }}>|</th>
                <th style={{ backgroundColor: '#c0392b', color: 'white' }}>CANTIDAD DE ERRORES</th>
                <th style={{ backgroundColor: '#c0392b', color: 'white' }}>ESTADO</th>
              </tr>
            </thead>
            <tbody>
              {grtResult.validaciones.map((v, i) => {
                const errores = v.resultado?.total_error ?? 0
                const estado = errores > 0 ? 'Rechazado' : 'Aprobado'

                return (
                  <tr key={i}>
                    <td>
                      {nombreTipoValidacion[v.resultado?.tipo] ?? v.resultado?.tipo ?? v.archivo}
                    </td>
                    <td>
                      <span style={{ color: errores === 0 ? '#28a745' : '#dc3545', fontWeight: 600 }}>
                        {errores}
                      </span>
                      <span
                        style={{
                          display: 'inline-block',
                          marginLeft: '8px',
                          width: '12px',
                          height: '12px',
                          borderRadius: '50%',
                          backgroundColor: estado === 'Aprobado' ? '#28a745' : '#dc3545'
                        }}
                      />
                    </td>
                    <td>{estado}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
            {console.log("grtResult completo:", JSON.stringify(grtResult, null, 2))}

            {/* Botones de exportar global */}
            <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
              <button
                className="generate-button"
                onClick={() => exportarExcel(construirValidacionesFiltradas(), explicacionesPorTipo, nombreTipoValidacion)}
              >
                📥 Exportar todo a Excel
              </button>
              <button
                className="generate-button"
                style={{ backgroundColor: '#dc3545' }}
                onClick={() => exportarPDF(construirValidacionesFiltradas(), nombreTipoValidacion, explicacionesPorTipo, duracionValidacion)}
              >
                📄 Exportar todo a PDF
              </button>
            </div>

            {grtResult.validaciones.map((validacion, vi) => {
              const resultado = validacion.resultado
              const explicacion = obtenerExplicaciones(resultado.tipo)

              if (resultado.error) {
                return (
                  <div key={vi} style={{ marginBottom: '30px' }}>
                    <h3>{validacion.archivo}</h3>
                    {resultado.tipo && (
                      <p style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: '#6c757d' }}>
                        Validación de tipo: <strong>{nombreTipoValidacion[resultado.tipo] ?? resultado.tipo}</strong>
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                      <button
                        className="generate-button"
                        style={{ fontSize: '0.85rem', padding: '4px 10px' }}
                        onClick={() => exportarExcelUna(validacion, explicacionesPorTipo, nombreTipoValidacion)}
                      >
                        📥 Excel
                      </button>
                      <button
                        className="generate-button"
                        style={{ fontSize: '0.85rem', padding: '4px 10px', backgroundColor: '#dc3545' }}
                        onClick={() => exportarPDFUna(validacion, nombreTipoValidacion, explicacionesPorTipo, duracionValidacion)}
                      >
                        📄 PDF
                      </button>
                    </div>
                    <p style={{ color: 'red' }}>❌ {resultado.error}</p>
                  </div>
                )
              }

              return (
                <div key={vi} style={{ marginBottom: '40px' }}>
                  <h3>{validacion.archivo}</h3>

                  {/* Botones de exportar por planilla */}
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                    <button
                      className="generate-button"
                      style={{ fontSize: '0.85rem', padding: '4px 10px' }}
                      onClick={() => exportarExcelUna(validacion, explicacionesPorTipo, nombreTipoValidacion)}
                    >
                      📥 Excel
                    </button>
                    <button
                      className="generate-button"
                      style={{ fontSize: '0.85rem', padding: '4px 10px', backgroundColor: '#dc3545' }}
                      onClick={() => exportarPDFUna(validacion, nombreTipoValidacion, explicacionesPorTipo, duracionValidacion)}
                    >
                      📄 PDF
                    </button>
                  </div>

                  {resultado.tipo && (
                    <p style={{ margin: '2px 0 15px 0', fontSize: '0.9rem', color: '#6c757d' }}>
                      Validación de tipo: <strong>{nombreTipoValidacion[resultado.tipo] ?? resultado.tipo}</strong>
                    </p>
                  )}

                  {/* Resumen */}
                  <div style={{ marginBottom: '15px' }}>
                    <p>Total filas/SKUs: {resultado.total_filas ?? resultado.total_skus_base}</p>
                    <p>OK: {resultado.total_ok}</p>
                    <p>Con error: {resultado.total_error}</p>
                  </div>

                  {/* Alertas globales (subsidios) */}
                  {resultado.alertas_globales?.length > 0 && (
                  <div style={{ marginBottom: '15px' }}>
                    <button
                      onClick={() => setMostrarAlertasGlobales(prev => ({ ...prev, [vi]: !prev[vi] }))}
                      style={{ fontSize: '0.85rem', padding: '4px 10px', marginBottom: '6px' }}
                    >
                      {mostrarAlertasGlobales[vi] ? '▲ Esconder' : '▼ Mostrar'} alertas globales ({resultado.alertas_globales.length})
                    </button>
                    {mostrarAlertasGlobales[vi] && (
                      <div style={{ padding: '10px', background: '#fff3cd', borderRadius: '5px', fontSize: '0.85rem' }}>
                        <ul style={{ margin: 0, paddingLeft: '16px' }}>
                          {resultado.alertas_globales.map((alerta, i) => (
                            <li key={i} style={{ color: '#856404' }}>{alerta}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                  {/* Leyenda */}
                  <div style={{ marginBottom: '15px', padding: '10px', background: '#fff', borderRadius: '5px' }}>
                    <p style={{ margin: '0 0 8px 0', fontWeight: 'bold' }}>Color de cada regla:</p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '0.85rem' }}>
                      {resultado.tipo === 'precios_full' ? (
                        <>
                          <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                          <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                          <span><strong style={{ color: coloresPorRegla[3] }}>●</strong> Regla 3</span>
                        </>
                      ) : resultado.tipo === 'equipos_accesorios' ? (
                        <>
                          <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                          <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                          <span><strong style={{ color: coloresPorRegla[3] }}>●</strong> Regla 3</span>
                        </>
                      ) : resultado.tipo === 'equipos_standalone' ? (
                        <>
                          <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                          <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                          <span><strong style={{ color: coloresPorRegla[3] }}>●</strong> Regla 3</span>
                        </>
                            ) : resultado.tipo === 'financiamiento' || resultado.tipo === 'grt_pie' || resultado.tipo === 'subsidios_claroup' ? (
                              <>
                                <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                                <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                              </>
                            ) : resultado.tipo === 'nuevos_equipos_claroup' ? (
                              <>
                                <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                                <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                                <span><strong style={{ color: coloresPorRegla[3] }}>●</strong> Regla 3</span>
                                <span><strong style={{ color: coloresPorRegla[4] }}>●</strong> Regla 4</span>
                                <span><strong style={{ color: coloresPorRegla[5] }}>●</strong> Regla 5</span>
                                <span><strong style={{ color: coloresPorRegla[6] }}>●</strong> Regla 6</span>
                              </>
                            ) : (
                        <>
                          <span><strong style={{ color: coloresPorRegla[0] }}>●</strong> Regla 0</span>
                          <span><strong style={{ color: coloresPorRegla[1] }}>●</strong> Regla 1</span>
                          <span><strong style={{ color: coloresPorRegla[2] }}>●</strong> Regla 2</span>
                          <span><strong style={{ color: coloresPorRegla[3] }}>●</strong> Regla 3</span>
                          <span><strong style={{ color: coloresPorRegla[4] }}>●</strong> Regla 4</span>
                          <span><strong style={{ color: coloresPorRegla[5] }}>●</strong> Regla 5</span>
                          <span><strong style={{ color: coloresPorRegla[6] }}>●</strong> Regla 6</span>
                          <span><strong style={{ color: coloresPorRegla[7] }}>●</strong> Regla 7</span>
                        </>
                      )}
                    </div>

                    {/* Explicación de reglas */}
                    <div style={{ marginTop: '10px', fontSize: '0.85rem' }}>
                      <p style={{ margin: '0 0 6px 0', fontWeight: 'bold' }}>Reglas:</p>
                      <ol style={{ margin: 0, paddingLeft: '18px' }}>

                        {explicacion.reglas && Object.entries(explicacion.reglas).map(([num, texto]) => (
                          <li key={num}>
                            <span style={{ color: coloresPorRegla[num], fontWeight: 'bold' }}>
                              
                            </span>{' '}
                            {texto}
                          </li>
                        ))}
                      </ol>
                    </div>

                    {/* Mensaje de reglas condicionales por tipo CREACIÓN */}
                    {(resultado.tipo === 'equipos_accesorios' || resultado.tipo === 'equipos_standalone') && (
                      <div style={{ marginTop: '10px', fontSize: '0.85rem', color: '#6c757d', fontStyle: 'italic' }}>
                        <p style={{ margin: '0 0 6px 0' }}>
                          ⚠️ Las reglas de caracteres solo se validan para equipos cuyo tipo fue especificado como <strong>CREACIÓN</strong>.
                        </p>
                        <p style={{ margin: '0 0 6px 0' }}>
                          <strong>Regla de caracteres inválidos:</strong> Los nombres, colores y modelos (columnas Nombre, COLOR y Model) no deben contener caracteres no válidos, donde los caracteres inválidos son / * - # , . ( ) y otros símbolos especiales. Se permiten: letras (incluyendo acentos), números y espacios.
                        </p>
                        <p style={{ margin: '0' }}>
                          <strong>Regla de largo:</strong> El nombre, color y modelo (columnas Nombre, COLOR y Model) del equipo debe ser menor o igual a 30 caracteres.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Tabla */}
                  {resultado.tipo === 'subsidios_claroup' ? (() => {
                    const filas = resultado.resumen || []
                    const filasMostradas = filtrarOK
                      ? filas.filter(row => row.estado === 'Con error' || row.alertas?.length > 0)
                      : filas

                    return (
                      <>
                        <table className="grt-table">
                          <thead>
                            <tr>
                              <th>Fila</th><th>SKU</th><th>Nombre</th><th>Estado</th><th>Acción</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filasMostradas.map((row, rowIdx) => {
                              const filaKey = `${vi}-${rowIdx}`
                              return (
                                <React.Fragment key={filaKey}>
                                  <tr>
                                    <td>{row.numero_fila}</td>
                                    <td>{row.sku}</td>
                                    <td>{row.nombre}</td>
                                    <td style={{ color: row.estado === 'OK' ? '#28a745' : '#dc3545', fontWeight: 600 }}>
                                      {row.estado}
                                    </td>
                                    <td>
                                      {(row.estado === 'Con error' || row.alertas?.length > 0) && (
                                        <button onClick={() => setExpandedFila(expandedFila === filaKey ? null : filaKey)}>
                                          Ver detalle
                                        </button>
                                      )}
                                    </td>
                                  </tr>
                                  {expandedFila === filaKey && row.detalle_error && (
                                    <tr>
                                      <td colSpan={5}>
                                        <div style={{ padding: '10px', background: '#f8f9fa' }}>
                                          <p><strong>Errores:</strong></p>
                                          <ul>
                                            {row.detalle_error.errores.map((err, i) => (
                                              <li key={i} style={{ color: obtenerColorError(err), fontWeight: 'bold' }}>{err}</li>
                                            ))}
                                          </ul>
                                          {row.detalle_error.total_ocurrencias > 1 && (
                                            <p style={{ marginTop: '8px', fontSize: '0.85rem', color: '#856404', fontStyle: 'italic' }}>
                                              ⚠️ Hay {row.detalle_error.total_ocurrencias - 1} registros más en la planilla {row.detalle_error.planilla} que rompen esta regla.
                                            </p>
                                          )}
                                          {row.detalle_error.datos_planilla && (
                                            <div style={{ marginTop: '10px', fontSize: '0.85rem' }}>
                                              <p style={{ margin: '0 0 6px 0', fontWeight: 'bold' }}>Datos planilla de precios:</p>
                                              <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.8rem' }}>
                                                <tbody>
                                                  {[
                                                    ['Generación',        row.detalle_error.datos_planilla.generacion],
                                                    ['UP',                row.detalle_error.datos_planilla.up],
                                                    ['Phone Protect',     row.detalle_error.datos_planilla.phone_protect],
                                                    ['Segmento',          row.detalle_error.datos_planilla.segmento],
                                                    ['Status',            row.detalle_error.datos_planilla.status],
                                                    ['SKU',               row.detalle_error.datos_planilla.sku],
                                                    ['Marca',             row.detalle_error.datos_planilla.marca],
                                                    ['Modelo Master',     row.detalle_error.datos_planilla.modelo_master],
                                                    ['Modelo Técnico',    row.detalle_error.datos_planilla.modelo_tecnico],
                                                    ['Modelo Comercial',  row.detalle_error.datos_planilla.modelo_comercial],
                                                    ['Valor Full (plan)', row.detalle_error.datos_planilla.valor_full_plan],
                                                    ['Pie + 12 Cuotas',   row.detalle_error.pie_12_cuotas],
                                                  ].map(([label, val]) => (
                                                    <tr key={label}>
                                                      <td style={{ padding: '2px 8px', fontWeight: 600, whiteSpace: 'nowrap', color: '#495057' }}>{label}</td>
                                                      <td style={{ padding: '2px 8px' }}>{val ?? '—'}</td>
                                                    </tr>
                                                  ))}
                                                </tbody>
                                              </table>
                                            </div>
                                          )}
                                        </div>
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              )
                            })}
                          </tbody>
                        </table>

                        {resultado.planilla_subsidios_id && resultado.total_error > 0 && (
                          <div style={{ marginTop: '15px' }}>
                            <button
                              className="generate-button"
                              style={{ backgroundColor: '#198754' }}
                              onClick={() => handleDescargarPlanillaSubsidios(resultado.planilla_subsidios_id)}
                            >
                              📊 Descargar Planilla de Evidencia
                            </button>
                          </div>
                        )}
                      </>
                    )
                  })() : (
                    // Tabla original para otros tipos
                    <>
                      {/* Aviso cuando se filtran las filas OK */}
                      {filtrarOK && (
                        <p style={{ fontSize: '0.85rem', color: '#6c757d', fontStyle: 'italic', marginBottom: '8px' }}>
                          ⚠️ Se superaron {limitFilas} filas — mostrando solo filas con errores o alertas ({resultado.total_error} errores, {resultado.resumen?.filter(r => r.alertas?.length > 0).length} alertas, de {resultado.total_filas ?? resultado.total_skus_base} totales).
                        </p>
                      )}
                      <table className="grt-table">
                        <thead>
                          <tr>
                            <th>Fila</th><th>SKU</th><th>Nombre</th><th>Estado</th><th>Acción</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                            const filasFiltradas = filtrarOK
                              ? resultado.resumen.filter(row => row.estado === 'Con error' || row.alertas?.length > 0)
                              : resultado.resumen
                            return filasFiltradas.map(row => {
                              const errores = row.detalle_error?.errores || []
                              const filaKey = `${vi}-${row.sku}-${row.numero_fila}`
                              const Label = ({ bold, children }) => (
                                <span style={{ fontWeight: bold ? 700 : 400 }}>{children}</span>
                              )
                              const errorNombre = errores.some(e => e.includes('Nombre'))
                              const errorModelo = errores.some(e => e.includes('Model'))
                              const errorColor = errores.some(e => e.includes('Color'))
                              const errorPrecio = errores.some(e => e.includes('Precio'))
                              const errorMake = errores.some(e => e.includes('Make'))
                              const errorEquipmentRank = errores.some(e => e.includes('Equipment Rank'))
                              const errorUseCategory = errores.some(e => e.includes('Use Category'))
                              const errorEquipmentClassification = errores.some(e => e.includes('Equipment Classification'))
                              return (
                                <>
                                  <tr key={filaKey}>
                                    <td>{row.numero_fila}</td>
                                    <td>{row.sku}</td>
                                    <td>{row.nombre}</td>
                                    <td style={{ color: row.estado === 'OK' ? '#28a745' : '#dc3545', fontWeight: 600 }}>
                                      {row.estado}
                                      {row.alertas?.length > 0 && (
                                        <span style={{ marginLeft: '6px', color: '#856404' }} title={row.alertas.join('\n')}>⚠️</span>
                                      )}
                                    </td>
                                    <td>
                                      {(row.estado === 'Con error' || row.alertas?.length > 0) && (
                                        <button onClick={() => setExpandedFila(expandedFila === filaKey ? null : filaKey)}>
                                          Ver detalle
                                        </button>
                                      )}
                                    </td>
                                  </tr>
                                  {expandedFila === filaKey && (row.detalle_error || row.alertas?.length > 0) && (
                                    <tr key={filaKey + '-detalle'}>
                                      <td colSpan={4}>
                                        <div style={{ padding: '10px', background: '#f8f9fa' }}>
                                          {row.alertas?.length > 0 && (
                                            <div style={{ marginBottom: '8px', padding: '6px 10px', background: '#fff3cd', borderRadius: '4px', fontSize: '0.85rem' }}>
                                              <p style={{ margin: '0 0 4px 0', fontWeight: 'bold', color: '#856404' }}>⚠️ Alertas de validación:</p>
                                              <ul style={{ margin: 0, paddingLeft: '16px' }}>
                                                {row.alertas.map((alerta, i) => (
                                                  <li key={i} style={{ color: '#856404' }}>{alerta}</li>
                                                ))}
                                              </ul>
                                            </div>
                                          )}
                                          {row.detalle_error && (
                                            <>
                                              <p><strong>Errores:</strong></p>
                                              <ul>
                                                {row.detalle_error.errores.map((err, index) => (
                                                  <li key={index} style={{ color: obtenerColorError(err), fontWeight: 'bold' }}>{err}</li>
                                                ))}
                                              </ul>
                                              <p><Label bold={errorNombre}>Nombre:</Label> {renderTextoConLimite(row.detalle_error.nombre, errorNombre)}</p>
                                              <p><Label bold={errorModelo}>Modelo:</Label> {renderTextoConLimite(row.detalle_error.model, errorModelo)}</p>
                                              <p><Label bold={errorColor}>Color:</Label> {renderTextoConLimite(row.detalle_error.color, errorColor)}</p>
                                              <p><Label bold={errorPrecio}>Precio Base:</Label> <Label bold={errorPrecio}>{row.detalle_error.precio_base}</Label></p>
                                              {(row.detalle_error.comparaciones || []).map((comp, i) => (
                                                <div key={i}>
                                                  <p><Label bold={true}>Precio Base + IVA:</Label> <Label bold={true}>{comp.precio_base_iva ?? '—'}</Label></p>
                                                  <p><Label bold={true}>Precio Comparación:</Label> <Label bold={true}>{comp.precio_comp ?? '—'}</Label></p>
                                                  <p><Label bold={true}>Diferencia:</Label> <Label bold={true}>{comp.diferencia ?? '—'}</Label></p>
                                                </div>
                                              ))}
                                              <p><Label bold={errorMake}>Make:</Label> <Label bold={errorMake}>{row.detalle_error.make ?? '—'}</Label></p>
                                              <p><Label bold={errorEquipmentRank}>Equipment Rank Value:</Label> <Label bold={errorEquipmentRank}>{row.detalle_error.equipment_rank_value ?? '—'}</Label></p>
                                              <p><Label bold={errorUseCategory}>Use Category:</Label> <Label bold={errorUseCategory}>{row.detalle_error.use_category ?? '—'}</Label></p>
                                              <p><Label bold={errorEquipmentClassification}>Equipment Classification:</Label> <Label bold={errorEquipmentClassification}>{row.detalle_error.equipment_classification ?? '—'}</Label></p>
                                            </>
                                          )}
                                        </div>
                                      </td>
                                    </tr>
                                  )}
                                </>
                              )
                            })
                          })()}
                        </tbody>
                      </table>
                      {/* Botón descarga planilla subsidios - no aplica para otros tipos */}
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Muestra errores de la comparativa */}
        {grtError && (
          <div className="excel-content">
            <p style={{ color: 'red', fontWeight: '600', whiteSpace: 'pre-line' }}>
              ❌ {grtError}
            </p>
          </div>
        )}

        {/* Renderiza cada archivo Excel procesado */}
        {excelData.length > 0 && (
          <div className="excel-content">
            {excelData.map((file, fileIndex) => (
              <div key={fileIndex} className="file-content">
                <h2 style={{ textAlign: 'center' }}>
                  Contenido del archivo "{file.fileName}":
                </h2>

                {/* Renderiza cada hoja del archivo con virtualización */}
                {file.sheets.map((sheet, sheetIndex) => (
                  <div key={sheetIndex} className="sheet-content">
                    <h3>
                      Hoja "{sheet.sheetName}"
                    </h3>

                    <VirtualizedTable data={sheet.data} maxHeight={600} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default App