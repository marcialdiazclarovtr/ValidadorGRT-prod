import * as XLSX from 'xlsx'
import jsPDF from 'jspdf'
import { autoTable } from 'jspdf-autotable'

const API_URL = window.location.origin

// ================================================================
// Funciones para generar el nombre del archivo export
// ================================================================

async function obtenerResumenCompleto(resumenId) {
  let page = 1
  let allFilas = []
  while (true) {
    const res = await fetch(`${API_URL}/resumen-subsidios/${resumenId}?page=${page}&page_size=500`)
    const data = await res.json()
    allFilas = [...allFilas, ...data.filas]
    if (page >= data.total_pages) break
    page++
  }
  return allFilas
}

function generarNombreDinamico() {
  const ahora = new Date();
  
  // Fecha: DD-MM-YYYY
  const dia = String(ahora.getDate()).padStart(2, '0');
  const mes = String(ahora.getMonth() + 1).padStart(2, '0');
  const anio = ahora.getFullYear();
  
  // Hora: HH:MM (Usaremos punto o guion porque ":" no es válido en nombres de archivo en Windows)
  const horas = String(ahora.getHours()).padStart(2, '0');
  const minutos = String(ahora.getMinutes()).padStart(2, '0');
  
  // Formato: Validacion_GRT_DD-MM-YYYY_HH-MM
  const fechaHora = `${dia}-${mes}-${anio}_${horas}-${minutos}`;

  return `Validacion_GRT_${fechaHora}`;
}

// ================================================================
// Helpers compartidos
// ================================================================

// Construye las filas de datos de una validación para exportar
function construirFilas(resultado) {
  if (!resultado.resumen) return []
  return resultado.resumen.map(row => {
    const detalle = row.detalle_error || {}
    
    // 1. Extraer errores de texto (Reglas 2 a 8)
    const listaErroresBackend = detalle.errores || []
    
    // 2. Extraer alertas
    const listaAlertas = row.alertas || []
    
    // 3. Procesar 'comparaciones' (Regla 1 / Precios)
    const comparacionesTexto = (detalle.comparaciones || []).map(c => {
      const regla = c.descripcion || c.regla || "Validación";
      if (c.precio_base_iva !== undefined && c.precio_base_iva !== null) {
        return `• ${regla}: Base=${c.precio_base_iva} | Comp=${c.precio_comp} | Diff=${c.diferencia}`;
      }
      return `• ${regla}`;
    });

    // 4. UNIFICACIÓN: Juntamos todo para que no se pierda nada
    const todasLineasError = [...listaErroresBackend, ...comparacionesTexto];

    return {
      numero_fila: row.numero_fila,
      sku: row.sku,
      nombre: row.nombre || "Sin Nombre",
      estado: row.estado,
      
      // Formato con doble salto para que en Excel/PDF se vea ordenado
      alertas: listaAlertas.length ? '• ' + listaAlertas.join('\n\n• ') : '',
      errores: todasLineasError.length ? '• ' + todasLineasError.join('\n\n• ') : '',
      
      // MAPEO DE CAMPOS (Sincronizado con el Python)
      nombre_detalle: detalle.nombre ?? '',
      modelo: detalle.model ?? '', // <-- Python envía 'model'
      color: detalle.color ?? '',
      make: detalle.make ?? '',
      equipment_rank: detalle.equipment_rank_value ?? '', // <-- Python envía 'equipment_rank_value'
      use_category: detalle.use_category ?? '',
      equipment_classification: detalle.equipment_classification ?? '',
      precio_base: detalle.precio_base ?? '',
      
      comparaciones: comparacionesTexto.join('\n\n')
    }
  })
}

// ================================================================
// Funcion para crear la tabla de resultados
// ================================================================

function construirResumenValidaciones(validaciones) {
  return validaciones
    .filter(v => v.resultado)
    .map(v => {
      const errores = v.resultado.total_error ?? 0

      return {
        validacion: v.resultado.tipo,
        errores,
        estado: errores > 0 ? 'Rechazado' : 'Aprobado'
      }
    })
}

// ================================================================
// Exportar a Excel
// ================================================================

export async function exportarExcel(validaciones, explicacionesPorTipo) {
  for (const v of validaciones) {
    if (!v.resultado.resumen && v.resultado.resumen_id) {
      v.resultado.resumen = await obtenerResumenCompleto(v.resultado.resumen_id)
    }
  }
  const wb = XLSX.utils.book_new();
  
  // Generamos el nombre basado en los archivos que vienen en el array
  const nombreFinal = generarNombreDinamico();

  // Bloque para generar la tabla de resultados
  const resumenValidaciones = construirResumenValidaciones(validaciones)

  // Hoja global resumen
  const resumenHeaders = ['Validación', 'Errores', 'Estado']
  const resumenRows = resumenValidaciones.map(r => [
    (r.validacion || '').toUpperCase(),
    r.errores,
    r.estado
  ])

  const wsResumenGlobal = XLSX.utils.aoa_to_sheet([
    resumenHeaders,
    ...resumenRows
  ])

  const range = XLSX.utils.decode_range(wsResumenGlobal['!ref'])

  // Formato excel tabla resumen
  for (let R = range.s.r; R <= range.e.r; ++R) {
    for (let C = range.s.c; C <= range.e.c; ++C) {
      const cellRef = XLSX.utils.encode_cell({ r: R, c: C })
      const cell = wsResumenGlobal[cellRef]
      if (!cell) continue

      // Inicializar estilos
      cell.s = {
        border: {
          top: { style: 'thin', color: { rgb: '000000' } },
          bottom: { style: 'thin', color: { rgb: '000000' } },
          left: { style: 'thin', color: { rgb: '000000' } },
          right: { style: 'thin', color: { rgb: '000000' } }
        },
        alignment: { horizontal: 'center', vertical: 'center' }
      }

      // HEADER
      if (R === 0) {
        if (C === 0) {
          // Validación (gris)
          cell.s.fill = { fgColor: { rgb: '808080' } }
          cell.s.font = { bold: true, color: { rgb: 'FFFFFF' } }
        } else {
          // Errores y Estado (rojo)
          cell.s.fill = { fgColor: { rgb: 'C0392B' } }
          cell.s.font = { bold: true, color: { rgb: 'FFFFFF' } }
        }
      }

      // BODY
      if (R > 0) {
        if (C === 0) {
          // Nombre validación → rojo
          cell.s.fill = { fgColor: { rgb: 'DC3545' } }
          cell.s.font = { bold: true, color: { rgb: 'FFFFFF' } }
        }

        if (C === 1) {
          // Cantidad errores → fondo blanco
          cell.s.fill = { fgColor: { rgb: 'FFFFFF' } }
        }

        if (C === 2) {
          // Estado → verde o rojo
          const estado = cell.v
          if (estado === 'Aprobado') {
            cell.s.fill = { fgColor: { rgb: '28A745' } }
            cell.s.font = { bold: true, color: { rgb: 'FFFFFF' } }
          } else {
            cell.s.fill = { fgColor: { rgb: 'DC3545' } }
            cell.s.font = { bold: true, color: { rgb: 'FFFFFF' } }
          }
        }
      }
    }
  }

  XLSX.utils.book_append_sheet(wb, wsResumenGlobal, 'Resumen Validaciones')

  validaciones.forEach((validacion, index) => {
    const resultado = validacion.resultado
    if (resultado.error) return

    const totalFilas = resultado.total_filas ?? resultado.total_skus_base
    const filas = construirFilas(resultado)
    
    // Obtenemos las reglas según el tipo de validación
    const infoReglas = explicacionesPorTipo ? explicacionesPorTipo[resultado.tipo] : null;

    // Hoja 1: Resumen
    const resumenData = [
      ['Archivo', validacion.archivo],
      ['Total filas/SKUs', totalFilas],
      ['OK', resultado.total_ok],
      ['Con error', resultado.total_error],
    ]
    const wsResumen = XLSX.utils.aoa_to_sheet(resumenData)

    // --- NUEVA HOJA: Reglas ---
    const reglasData = [['# Regla', 'Descripción de la Validación']];
    if (infoReglas && infoReglas.reglas) {
      Object.entries(infoReglas.reglas).forEach(([num, desc]) => {
        reglasData.push([`Regla ${num}`, desc]);
      });
    }
    const wsReglas = XLSX.utils.aoa_to_sheet(reglasData);
    wsReglas['!cols'] = [{ wch: 12 }, { wch: 100 }]; // Ancho de columnas

    // Hoja 3: Detalle de errores (Tu código actual)
    const soloErrores = filas.filter(f => f.estado === 'Con error')
    const erroresHeaders = ['Fila', 'SKU', 'Nombre', 'Errores', 'Nombre', 'Modelo', 'Color', 'Make', 'Eq. Rank', 'Use Category', 'Eq. Classification', 'Precio Base', 'Comparaciones']
    const erroresRows = soloErrores.map(f => [f.numero_fila, f.sku, f.nombre, f.errores, f.nombre_detalle, f.modelo, f.color, f.make, f.equipment_rank, f.use_category, f.equipment_classification, f.precio_base, f.comparaciones])
    const wsErrores = XLSX.utils.aoa_to_sheet([erroresHeaders, ...erroresRows])

    // Hoja 4: Todas las filas
    const todasHeaders = ['Fila', 'SKU', 'Nombre', 'Estado', 'Errores']
    const todasRows = filas.map(f => [f.numero_fila, f.sku, f.nombre, f.estado, f.errores])
    const wsTodas = XLSX.utils.aoa_to_sheet([todasHeaders, ...todasRows])

    const idUnico = index + 1;
    const nombreLimpio = validacion.archivo.replace(/[:\\/?*[\]]/g, '').slice(0, 15);
    
    // Nombres de hojas actualizados
    XLSX.utils.book_append_sheet(wb, wsResumen, `${idUnico}-${nombreLimpio}_Res`.slice(0, 31));
    XLSX.utils.book_append_sheet(wb, wsReglas, `${idUnico}-${nombreLimpio}_Reg`.slice(0, 31)); // Inserción de reglas
    XLSX.utils.book_append_sheet(wb, wsErrores, `${idUnico}-${nombreLimpio}_Err`.slice(0, 31));
    XLSX.utils.book_append_sheet(wb, wsTodas, `${idUnico}-${nombreLimpio}_Tod`.slice(0, 31));
  })

  XLSX.writeFile(wb, `${nombreFinal}.xlsx`);
}

export function exportarExcelUna(validacion, explicacionesPorTipo, nombreTipoValidacion) {
  exportarExcel([validacion], explicacionesPorTipo, nombreTipoValidacion);
}

// ================================================================
// Exportar a PDF
// ================================================================

function agregarSeccionPDF(doc, validacion, explicacionesPorTipo, esUltima) {
  const resultado = validacion.resultado;
  if (resultado.error) return;

  const totalFilas = resultado.total_filas ?? resultado.total_skus_base;
  const filas = construirFilas(resultado);
  const infoReglas = explicacionesPorTipo ? explicacionesPorTipo[resultado.tipo] : null;

  // Punto de partida Y
  const baseY = (doc.lastAutoTable?.finalY ?? 0) + 15;

  // Título del archivo
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(218, 41, 28);
  doc.text(validacion.archivo, 14, baseY);

  let nextY = baseY + 8;

  // Tabla de reglas
  if (infoReglas && infoReglas.reglas) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(0, 0, 0);
    doc.text(`Reglas aplicadas — ${infoReglas.titulo || ''}  |  Planillas: ${infoReglas.planillas || ''}`, 14, nextY);

    autoTable(doc, {
      startY: nextY + 5,
      head: [['Regla', 'Descripción']],
      body: Object.entries(infoReglas.reglas).map(([num, desc]) => [`Regla ${num}`, desc]),
      theme: 'grid',
      headStyles: { fillColor: [80, 80, 80], textColor: 255, fontStyle: 'bold' },
      columnStyles: {
        0: { cellWidth: 20, fontStyle: 'bold' },
        1: { cellWidth: 249 }
      },
      styles: { fontSize: 8, overflow: 'linebreak', cellPadding: 3 },
      margin: { left: 14, right: 14 }
    });

    nextY = doc.lastAutoTable.finalY + 8;
  }

  // Tabla resumen numérico
  autoTable(doc, {
    startY: nextY,
    head: [['Total filas/SKUs', 'OK', 'Con error']],
    body: [[totalFilas, resultado.total_ok, resultado.total_error]],
    theme: 'grid',
    headStyles: { fillColor: [41, 128, 185] },
    margin: { left: 14, right: 14 }
  });

  // Detalle de errores
  const soloErrores = filas.filter(f => (f.errores && f.errores.length > 0) || (f.alertas && f.alertas.length > 0));
  if (soloErrores.length > 0) {
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(0, 0, 0);
    doc.text('Detalle de errores', 14, doc.lastAutoTable.finalY + 10);

    autoTable(doc, {
      startY: doc.lastAutoTable.finalY + 15,
      head: [['Fila', 'SKU', 'Nombre', 'Errores', 'Alertas', 'Comparaciones']],
      body: soloErrores.map(f => [f.numero_fila, f.sku, f.nombre, f.errores, f.alertas, f.comparaciones]),
      theme: 'striped',
      headStyles: { fillColor: [192, 57, 43] },
      columnStyles: {
        0: { cellWidth: 12 },
        1: { cellWidth: 30 },
        2: { cellWidth: 40 },
        3: { cellWidth: 85 },
        4: { cellWidth: 50 },
        5: { cellWidth: 50 }
      },
      styles: { fontSize: 9, overflow: 'linebreak' },
      margin: { left: 14, right: 14 }
    });
  }

  if (!esUltima) {
    doc.addPage();
    doc.lastAutoTable = { finalY: 0 };
  }
}

export async function exportarPDF(validaciones, nombreTipoValidacion, explicacionesPorTipo, duracionSegundos = null, nombreArchivo = 'resultados_grt') {
  for (const v of validaciones) {
    if (!v.resultado.resumen && v.resultado.resumen_id) {
      v.resultado.resumen = await obtenerResumenCompleto(v.resultado.resumen_id)
    }
  }

  const doc = new jsPDF({ orientation: 'landscape' })
  const nombreFinal = generarNombreDinamico();

  // ── PORTADA ──────────────────────────────────────────────────────
  const ahora = new Date()
  const dia = String(ahora.getDate()).padStart(2, '0')
  const mes = String(ahora.getMonth() + 1).padStart(2, '0')
  const anio = ahora.getFullYear()
  const horas = String(ahora.getHours()).padStart(2, '0')
  const minutos = String(ahora.getMinutes()).padStart(2, '0')
  const fechaStr = `${dia}-${mes}-${anio}`
  const horaStr = `${horas}:${minutos}`

  const pageW = doc.internal.pageSize.getWidth()
  const pageH = doc.internal.pageSize.getHeight()

  // Banda roja superior
  doc.setFillColor(218, 41, 28)
  doc.rect(0, 0, pageW, 28, 'F')

  // Banda roja inferior
  doc.setFillColor(218, 41, 28)
  doc.rect(0, pageH - 18, pageW, 18, 'F')

  // Línea gris decorativa horizontal
  doc.setDrawColor(200, 200, 200)
  doc.setLineWidth(0.4)
  doc.line(14, 50, pageW - 14, 50)

  // Título principal
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(26)
  doc.setTextColor(218, 41, 28)
  doc.text(`Validación GRT ${fechaStr}`, 14, 45)

  let yActual = 58

  // Duración
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(11)
  doc.setTextColor(44, 62, 80)
  if (duracionSegundos !== null) {
    const mins = Math.floor(duracionSegundos / 60)
    const segs = Math.round(duracionSegundos % 60)
    const durStr = mins > 0 ? `${mins} min ${segs} s` : `${segs} s`
    doc.text(`Duración de la validación: ${durStr}`, 14, yActual)
    yActual += 8
  }

  // Hora de validación
  doc.text(`Hora de validación: ${horaStr}`, 14, yActual)
  yActual += 18  // ← más espacio antes de "Validaciones:"

  // Sección "Validaciones:" (ahora va primero)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(12)
  doc.setTextColor(44, 62, 80)
  doc.text('Validaciones:', 14, yActual)
  yActual += 8

  // Lista de validaciones (sin estado al costado)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  validaciones.forEach(v => {
    const tipo = nombreTipoValidacion[v.resultado?.tipo] ?? v.resultado?.tipo ?? '—'

    doc.setTextColor(60, 60, 60)
    doc.text(`${v.archivo}  —  Validación ${tipo}`, 18, yActual)
    yActual += 7
  })

  yActual += 4

  // Planillas aprobadas / rechazadas (ahora va después)
  const totalAprobadas = validaciones.filter(v => (v.resultado?.total_error ?? 0) === 0).length
  const totalRechazadas = validaciones.filter(v => (v.resultado?.total_error ?? 0) > 0).length

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.setTextColor(39, 174, 96)
  doc.text(`Planillas aprobadas: ${totalAprobadas}`, 14, yActual)

  doc.setTextColor(218, 41, 28)
  doc.text(`Planillas rechazadas: ${totalRechazadas}`, 80, yActual)
  yActual += 10

  // Texto inferior en banda roja
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(255, 255, 255)
  doc.text('Claro Chile — Área QA — Uso interno', 14, pageH - 6)
  doc.text('v2.0', pageW - 20, pageH - 6)

  // ── TABLA RESUMEN EN MISMA PÁGINA (o nueva si no cabe) ────────────
  const resumenValidaciones = construirResumenValidaciones(validaciones)
  const alturaTabla = resumenValidaciones.length * 10 + 20
  const espacioRestante = pageH - 18 - yActual

  if (espacioRestante < alturaTabla + 20) {
    doc.addPage()
    doc.lastAutoTable = { finalY: 0 }
    yActual = 14
  }

  // Título "Resultados Comparativa GRT"
  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(0, 0, 0)
  doc.text('Resultados Comparativa GRT', 14, yActual + 8)

  autoTable(doc, {
    startY: yActual + 13,
    head: [['|', 'CANTIDAD DE ERRORES', 'ESTADO']],
    body: resumenValidaciones.map(r => [
      nombreTipoValidacion[r.validacion] ?? r.validacion,
      `${r.errores} •`,
      r.estado
    ]),
    theme: 'plain',
    styles: { fontSize: 9, cellPadding: 4, valign: 'middle' },
    headStyles: { fillColor: [192, 57, 43], textColor: 255, halign: 'center', fontStyle: 'bold' },
    tableWidth: 189,
    columnStyles: {
      0: { cellWidth: 90 },
      1: { halign: 'center', cellWidth: 55 },
      2: { halign: 'center', cellWidth: 44 }
    },
    didParseCell: function (data) {
      const row = data.row.index
      const estado = resumenValidaciones[row]?.estado
      if (data.column.index === 0 && data.section === 'body') {
        data.cell.styles.fillColor = [220, 53, 69]
        data.cell.styles.textColor = 255
        data.cell.styles.fontStyle = 'bold'
      }
      if (data.column.index === 1 && data.section === 'body') {
        data.cell.styles.textColor = estado === 'Aprobado' ? [40, 167, 69] : [220, 53, 69]
        data.cell.styles.fontStyle = 'bold'
      }
      if (data.column.index === 2 && data.section === 'body') {
        data.cell.styles.textColor = estado === 'Aprobado' ? [40, 167, 69] : [220, 53, 69]
        data.cell.styles.fontStyle = 'bold'
      }
      if (data.column.index === 0 && data.section === 'head') {
        data.cell.styles.fillColor = [0, 0, 0]
      }
    },
    margin: { left: 14, right: 14 }
  })

  // ── FIN PORTADA + RESUMEN ─────────────────────────────────────────
  doc.addPage()
  doc.lastAutoTable = { finalY: 0 }

  validaciones.forEach((validacion, i) => {
    agregarSeccionPDF(doc, validacion, explicacionesPorTipo, i === validaciones.length - 1)
  })

  doc.save(`${nombreFinal}.pdf`)
}

export function exportarPDFUna(validacion, nombreTipoValidacion, explicacionesPorTipo, duracion = null) {
  exportarPDF([validacion], nombreTipoValidacion, explicacionesPorTipo, duracion)
}