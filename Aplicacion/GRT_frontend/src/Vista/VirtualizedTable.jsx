import { TableVirtuoso } from 'react-virtuoso'

const VirtualizedTable = ({ data, maxHeight = 600 }) => {
  if (!data || data.length === 0) {
    return <p>Hoja vacía</p>
  }

  const columns = Object.keys(data[0])

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '4px', overflow: 'hidden' }}>
      <TableVirtuoso
        style={{ height: maxHeight }}
        data={data}
        fixedHeaderContent={() => (
          <tr style={{ backgroundColor: '#f5f5f5' }}>
            {columns.map((col, i) => (
              <th key={i} style={{ 
                padding: '8px', 
                borderRight: '1px solid #ddd',
                textAlign: 'left',
                position: 'sticky',
                top: 0,
                backgroundColor: '#f5f5f5'
              }}>
                {col}
              </th>
            ))}
          </tr>
        )}
        itemContent={(index, row) => (
          <>
            {columns.map((col, j) => (
              <td key={j} style={{ 
                padding: '8px', 
                borderRight: '1px solid #ddd',
                borderBottom: '1px solid #ddd'
              }}>
                {String(row[col] ?? '')}
              </td>
            ))}
          </>
        )}
      />
      
      <div style={{ padding: '8px', backgroundColor: '#f9f9f9', textAlign: 'center' }}>
        Total de filas: {data.length}
      </div>
    </div>
  )
}

export default VirtualizedTable