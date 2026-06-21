

function exportTableToExcel(tableId, filename) {
    try {
        
        const table = document.getElementById(tableId);
        if (!table) {
            alert('Tabel tidak ditemukan!');
            return;
        }

        
        let csv = [];

        
        const headerRow = table.querySelector('thead tr');
        if (headerRow) {
            const headers = [];
            headerRow.querySelectorAll('th').forEach(th => {
                
                
                headers.push('"' + th.textContent.trim().replace(/"/g, '""') + '"');
            });
            csv.push(headers.join(','));  
        }

        
        const tbody = table.querySelector('tbody');
        if (tbody) {
            tbody.querySelectorAll('tr').forEach(tr => {
                const cells = tr.querySelectorAll('td');
                if (cells.length === 0) return;  

                
                if (cells.length === 1 && cells[0].colSpan > 1) return;

                const row = [];
                cells.forEach(td => {
                    
                    let text = td.textContent.trim();
                    text = text.replace(/\s+/g, ' ').replace(/"/g, '""');
                    row.push('"' + text + '"');
                });
                csv.push(row.join(','));  
            });
        }

        
        const csvContent = csv.join('\n');

        
        const BOM = '\uFEFF';

        
        const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });

        
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);  

        link.setAttribute('href', url);
        link.setAttribute('download', filename + '.csv');  
        link.style.visibility = 'hidden';                  
        document.body.appendChild(link);                    
        link.click();                                       
        document.body.removeChild(link);                    

    } catch (error) {
        console.error('Export Excel error:', error);
        alert('Terjadi kesalahan saat export Excel: ' + error.message);
    }
}


function exportTableToPDF(tableId, filename, title, orientation = 'landscape') {
    try {
        
        
        if (typeof pdfMake === 'undefined') {
            alert('pdfMake library tidak tersedia. Export PDF dibatalkan.');
            return;
        }

        
        const table = document.getElementById(tableId);
        if (!table) {
            alert('Tabel tidak ditemukan!');
            return;
        }

        
        const headers = [];
        const headerRow = table.querySelector('thead tr');
        if (headerRow) {
            headerRow.querySelectorAll('th').forEach(th => {
                headers.push({
                    text: th.textContent.trim(),
                    style: 'tableHeader',           
                    fillColor: '#52d123',           
                    color: '#FFFFFF',               
                    bold: true                      
                });
            });
        }

        
        const body = [headers];
        const tbody = table.querySelector('tbody');
        if (tbody) {
            tbody.querySelectorAll('tr').forEach(tr => {
                const cells = tr.querySelectorAll('td');
                if (cells.length === 0) return;

                
                if (cells.length === 1 && cells[0].colSpan > 1) return;

                const row = [];
                cells.forEach(td => {
                    let text = td.textContent.trim();
                    text = text.replace(/\s+/g, ' ');

                    
                    if (text.length > 100) {
                        text = text.substring(0, 97) + '...';
                    }

                    row.push(text);
                });
                body.push(row);
            });
        }

        
        const docDefinition = {
            pageOrientation: orientation,          
            pageMargins: [40, 60, 40, 60],         

            
            content: [
                
                {
                    text: title,
                    style: 'header',
                    margin: [0, 0, 0, 20]      
                },
                
                {
                    table: {
                        headerRows: 1,                                  
                        widths: Array(headers.length).fill('auto'),     
                        body: body                                      
                    },
                    layout: {
                        
                        fillColor: function (rowIndex) {
                            return (rowIndex === 0) ? '#52d123' : ((rowIndex % 2 === 0) ? '#F5F5F9' : null);
                        },
                        
                        hLineWidth: function () { return 0.5; },
                        vLineWidth: function () { return 0.5; },
                        hLineColor: function () { return '#DBDADE'; },
                        vLineColor: function () { return '#DBDADE'; },
                    }
                },
                
                {
                    text: 'Dicetak pada: ' + new Date().toLocaleString('id-ID'),
                    style: 'footer',
                    margin: [0, 20, 0, 0]      
                }
            ],

            
            styles: {
                header: {
                    fontSize: 18,
                    bold: true,
                    color: '#5F61E6'           
                },
                tableHeader: {
                    bold: true,
                    fontSize: 11,
                    color: '#FFFFFF'            
                },
                footer: {
                    fontSize: 9,
                    italics: true,
                    color: '#697A8D'            
                }
            },

            
            defaultStyle: {
                fontSize: 9                     
            }
        };

        
        pdfMake.createPdf(docDefinition).download(filename + '.pdf');

    } catch (error) {
        console.error('Export PDF error:', error);
        alert('Terjadi kesalahan saat export PDF: ' + error.message);
    }
}
