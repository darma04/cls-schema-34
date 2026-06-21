

var SimkosExport = (function () {
    'use strict';

    
    function _formatRupiah(value) {
        var num = parseFloat(String(value).replace(/[^\d.-]/g, ''));
        if (isNaN(num)) return String(value); 
        return 'Rp ' + num.toLocaleString('id-ID', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    
    function _formatNumber(value) {
        var num = parseFloat(String(value).replace(/[^\d.-]/g, ''));
        if (isNaN(num)) return String(value);
        return num.toLocaleString('id-ID', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    
    function _isMoneyLike(str) {
        var s = String(str).trim();
        return /^(Rp[\s\.]?)?[\d.,]+$/.test(s) || s === '0';
    }

    
    function _isMoneyColumn(colIdx, moneyColumns) {
        if (!moneyColumns || !Array.isArray(moneyColumns)) return true; 
        return moneyColumns.indexOf(colIdx) !== -1;
    }

    
    function _formatFooterValue(rawVal, colIdx, moneyColumns) {
        var str = String(rawVal);
        if (_isMoneyColumn(colIdx, moneyColumns)) {
            return _isMoneyLike(str) ? _formatRupiah(rawVal) : str;
        } else {
            
            return _isMoneyLike(str) ? _formatNumber(rawVal) : str;
        }
    }

    
    function toggleColumns(tableId) {
        if (typeof $ === 'undefined' || typeof $.fn.dataTable === 'undefined') {
            console.error('SimkosExport: jQuery DataTables belum dimuat!');
            return;
        }
        try {
            var tableApi = new $.fn.dataTable.Api(tableId);
            document.querySelectorAll('.column-checkbox').forEach(function (cb) {
                tableApi.column(parseInt(cb.value)).visible(cb.checked);
            });
        } catch (e) {
            console.error('SimkosExport.toggleColumns error:', e);
        }
    }

    
    function _getVisibleColumns(tableId) {
        var tableApi = new $.fn.dataTable.Api(tableId);
        var cols = [];
        tableApi.columns().every(function (index) {
            var headerNode = this.header();
            var headerText = headerNode ? headerNode.textContent.trim() : '';
            var lowerText = headerText.toLowerCase();
            
            var isActionCol = (lowerText === 'aksi' || lowerText === 'action' || lowerText === 'tindakan' || lowerText === '');
            if (this.visible() && !isActionCol) {
                cols.push({ index: index, text: headerText });
            }
        });
        return cols;
    }

    
    function _buildSummaryRowExcel(visibleColumns, footerData, footerLabel, moneyColumns) {
        var cells = [];
        var labelPlaced = false;
        var ri = 0;

        while (ri < visibleColumns.length) {
            var colIdx = visibleColumns[ri].index;

            if (footerData && footerData[colIdx] !== undefined && footerData[colIdx] !== null && footerData[colIdx] !== '') {
                
                var rawVal = footerData[colIdx];
                var formatted = _formatFooterValue(rawVal, colIdx, moneyColumns);
                cells.push({ text: formatted, span: 1, align: 'right', isTotal: true });
                ri++;
            } else {
                
                var spanCount = 0;
                var si = ri;
                while (
                    si < visibleColumns.length &&
                    (!footerData || footerData[visibleColumns[si].index] === undefined ||
                        footerData[visibleColumns[si].index] === null ||
                        footerData[visibleColumns[si].index] === '')
                ) {
                    spanCount++;
                    si++;
                }
                var label = !labelPlaced ? (footerLabel || 'RINGKASAN') : '';
                if (!labelPlaced && label) labelPlaced = true;
                cells.push({ text: label, span: spanCount, align: 'left', isTotal: false });
                ri += spanCount;
            }
        }
        return cells;
    }

    
    function _buildSummaryRowPDF(visibleColumns, footerData, footerLabel, moneyColumns) {
        var summaryRow = [];
        var labelPlaced = false;
        var ri = 0;

        while (ri < visibleColumns.length) {
            var colIdx = visibleColumns[ri].index;

            if (footerData && footerData[colIdx] !== undefined && footerData[colIdx] !== null && footerData[colIdx] !== '') {
                var rawVal = footerData[colIdx];
                var formatted = _formatFooterValue(rawVal, colIdx, moneyColumns);
                summaryRow.push({
                    text: formatted,
                    bold: true,
                    fillColor: '#EEF0FF',
                    color: '#4B4EE6',
                    alignment: 'right'
                });
                ri++;
            } else {
                var spanCount = 0;
                var si = ri;
                while (
                    si < visibleColumns.length &&
                    (!footerData || footerData[visibleColumns[si].index] === undefined ||
                        footerData[visibleColumns[si].index] === null ||
                        footerData[visibleColumns[si].index] === '')
                ) {
                    spanCount++;
                    si++;
                }
                var label = !labelPlaced ? (footerLabel || 'RINGKASAN') : '';
                if (!labelPlaced && label) labelPlaced = true;

                var cell = {
                    text: label,
                    bold: true,
                    fillColor: '#EEF0FF',
                    color: '#5F61E6',
                    alignment: 'left'
                };
                if (spanCount > 1) {
                    cell.colSpan = spanCount;
                }
                summaryRow.push(cell);
                
                for (var k = 1; k < spanCount; k++) {
                    summaryRow.push({ text: '', fillColor: '#EEF0FF' });
                }
                ri += spanCount;
            }
        }
        return summaryRow;
    }

    
    function buildExcel(tableId, info, footerData, footerLabel, title, filename, moneyColumns) {
        try {
            var tableEl = document.querySelector(tableId);
            if (!tableEl) { alert('Tabel tidak ditemukan!'); return; }
            if (typeof $ === 'undefined' || typeof $.fn.dataTable === 'undefined') {
                alert('DataTables belum dimuat!'); return;
            }

            var visibleColumns = _getVisibleColumns(tableId);
            var tableApi = new $.fn.dataTable.Api(tableId);
            var colCount = visibleColumns.length;

            if (colCount === 0) { alert('Tidak ada kolom yang tersedia untuk di-export!'); return; }

            var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office"'
                + ' xmlns:x="urn:schemas-microsoft-com:office:excel"'
                + ' xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8">'
                + '<style>table{border-collapse:collapse;} th,td{font-family:Arial,sans-serif;font-size:9pt;}'
                + '.kop-judul{font-size:14pt;font-weight:bold;color:#5F61E6;}'
                + '.kop-info{font-size:9pt;color:#697A8D;}'
                + '.th-header{background-color:#52d123;color:#FFFFFF;font-weight:bold;padding:6px;}'
                + '.td-data{padding:4px 6px;}'
                + '.td-summary{background-color:#EEF0FF;font-weight:bold;padding:4px 6px;color:#4B4EE6;}'
                + '.td-label{background-color:#EEF0FF;font-weight:bold;padding:4px 6px;color:#5F61E6;}'
                + '</style></head><body>';

            
            html += '<table border="0" style="margin-bottom:8px;width:100%;">';
            html += '<tr><td colspan="' + colCount + '" style="text-align:center;font-size:16pt;font-weight:bold;color:#5F61E6;border:none;">' + (info.name || 'SIMKOS') + '</td></tr>';
            html += '<tr><td colspan="' + colCount + '" style="text-align:center;font-size:9pt;color:#697A8D;border:none;">' + (info.address || '') + '</td></tr>';
            html += '<tr><td colspan="' + colCount + '" style="text-align:center;font-size:9pt;color:#697A8D;border:none;">Telp: ' + (info.phone || '-') + ' | Email: ' + (info.email || '-') + '</td></tr>';
            html += '<tr><td colspan="' + colCount + '" style="border:none;">&nbsp;</td></tr>';
            html += '</table>';

            
            html += '<table border="0" style="margin-bottom:6px;">';
            html += '<tr><td colspan="' + colCount + '" style="font-size:12pt;font-weight:bold;color:#5F61E6;border:none;">' + (title || 'Laporan') + '</td></tr>';
            html += '<tr><td colspan="' + colCount + '" style="font-size:8pt;color:#697A8D;border:none;">Tanggal: '
                + new Date().toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' }) + '</td></tr>';
            html += '<tr><td colspan="' + colCount + '" style="border:none;">&nbsp;</td></tr>';
            html += '</table>';

            
            html += '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;width:100%;">';

            
            html += '<thead><tr>';
            visibleColumns.forEach(function (col) {
                html += '<th style="background-color:#52d123;color:#FFFFFF;font-weight:bold;padding:6px;white-space:nowrap;border:1px solid #DBDADE;">' + col.text + '</th>';
            });
            html += '</tr></thead><tbody>';

            
            tableApi.rows({ search: 'applied' }).every(function (rowIdx) {
                html += '<tr>';
                visibleColumns.forEach(function (col) {
                    var cellNode = tableApi.cell(rowIdx, col.index).node();
                    var text = cellNode ? cellNode.textContent.trim().replace(/\s+/g, ' ') : '';
                    var isRight = /^Rp[\s]/.test(text) || /^[\d.,]+$/.test(text);
                    html += '<td style="padding:4px 6px;border:1px solid #DBDADE;' + (isRight ? 'text-align:right;' : '') + '">' + text + '</td>';
                });
                html += '</tr>';
            });

            
            var hasFooter = footerData && Object.keys(footerData).length > 0;
            var summaryCells = _buildSummaryRowExcel(visibleColumns, hasFooter ? footerData : {}, footerLabel, moneyColumns);
            html += '<tr>';
            summaryCells.forEach(function (cell) {
                var style = cell.isTotal
                    ? 'background-color:#EEF0FF;font-weight:bold;color:#4B4EE6;text-align:right;padding:5px 6px;border:1px solid #DBDADE;'
                    : 'background-color:#EEF0FF;font-weight:bold;color:#5F61E6;text-align:left;padding:5px 6px;border:1px solid #DBDADE;';
                if (cell.span > 1) {
                    html += '<td colspan="' + cell.span + '" style="' + style + '">' + cell.text + '</td>';
                } else {
                    html += '<td style="' + style + '">' + cell.text + '</td>';
                }
            });
            html += '</tr>';

            html += '</tbody></table>';

            
            html += '<table border="0" style="margin-top:8px;width:100%;">';
            html += '<tr>';
            html += '<td style="font-size:8pt;color:#697A8D;border:none;">Dicetak pada: ' + new Date().toLocaleString('id-ID') + '</td>';
            html += '<td style="font-size:8pt;color:#697A8D;text-align:right;border:none;">' + (info.copyright || '') + '</td>';
            html += '</tr></table>';

            html += '</body></html>';

            var blob = new Blob(['\uFEFF' + html], { type: 'application/vnd.ms-excel;charset=utf-8' });
            var link = document.createElement('a');
            link.setAttribute('href', URL.createObjectURL(blob));
            link.setAttribute('download', (filename || 'Export') + '_' + new Date().toISOString().slice(0, 10) + '.xls');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (err) {
            console.error('SimkosExport.buildExcel error:', err);
            alert('Terjadi kesalahan saat export Excel: ' + err.message);
        }
    }

    
    function buildPDF(tableId, info, footerData, footerLabel, title, filename, moneyColumns) {
        try {
            if (typeof pdfMake === 'undefined') {
                alert('pdfMake library tidak tersedia! Pastikan pdfmake.min.js sudah dimuat.');
                return;
            }
            var tableEl = document.querySelector(tableId);
            if (!tableEl) { alert('Tabel tidak ditemukan!'); return; }

            var visibleColumns = _getVisibleColumns(tableId);
            var tableApi = new $.fn.dataTable.Api(tableId);
            var colCount = visibleColumns.length;

            if (colCount === 0) { alert('Tidak ada kolom yang tersedia untuk di-export!'); return; }

            
            var headers = visibleColumns.map(function (col) {
                return {
                    text: col.text,
                    style: 'tableHeader',
                    fillColor: '#52d123',
                    color: '#FFFFFF',
                    bold: true,
                    alignment: 'center'
                };
            });

            
            var body = [headers];
            tableApi.rows({ search: 'applied' }).every(function (rowIdx) {
                var row = [];
                visibleColumns.forEach(function (col) {
                    var cellNode = tableApi.cell(rowIdx, col.index).node();
                    var text = cellNode ? cellNode.textContent.trim().replace(/\s+/g, ' ') : '';
                    if (text.length > 80) { text = text.substring(0, 77) + '...'; }
                    
                    var isRightAlign = /^Rp[\s]/.test(text) || /^[\d.,]+$/.test(text);
                    row.push({ text: text, alignment: isRightAlign ? 'right' : 'left' });
                });
                if (row.length > 0) body.push(row);
            });

            
            var hasFooter = footerData && Object.keys(footerData).length > 0;
            var summaryRow = _buildSummaryRowPDF(visibleColumns, hasFooter ? footerData : {}, footerLabel, moneyColumns);
            if (summaryRow.length > 0) body.push(summaryRow);

            
            var colWidths = Array(colCount).fill('auto');

            var bodyLength = body.length;

            var docDefinition = {
                pageOrientation: 'landscape',
                pageSize: 'A4',
                pageMargins: [30, 110, 30, 55],

                
                header: function (currentPage) {
                    return {
                        margin: [30, 12, 30, 0],
                        table: {
                            widths: ['*', 80],
                            body: [[
                                {
                                    border: [false, false, false, true],
                                    stack: [
                                        { text: info.name || 'SIMKOS', style: 'companyName' },
                                        { text: info.address || '', style: 'companyInfo' },
                                        { text: 'Telp: ' + (info.phone || '-') + ' | Email: ' + (info.email || '-'), style: 'companyInfo' }
                                    ]
                                },
                                {
                                    border: [false, false, false, true],
                                    stack: [
                                        { text: 'Hal. ' + currentPage, style: 'pageNumber', alignment: 'right' }
                                    ]
                                }
                            ]]
                        },
                        layout: {
                            hLineWidth: function (i, node) { return (i === node.table.body.length) ? 1 : 0; },
                            vLineWidth: function () { return 0; },
                            hLineColor: function () { return '#52d123'; }
                        }
                    };
                },

                content: [
                    { text: title || 'Laporan', style: 'documentTitle', margin: [0, 0, 0, 2] },
                    {
                        text: 'Tanggal: ' + new Date().toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' }),
                        style: 'dateText',
                        margin: [0, 0, 0, 10]
                    },
                    {
                        table: {
                            headerRows: 1,
                            dontBreakRows: true,
                            widths: colWidths,
                            body: body
                        },
                        layout: {
                            fillColor: function (rowIndex) {
                                if (rowIndex === 0) return '#52d123';            
                                if (rowIndex === bodyLength - 1) return '#EEF0FF'; 
                                return (rowIndex % 2 === 0) ? '#F5F5F9' : null;    
                            },
                            hLineWidth: function () { return 0.5; },
                            vLineWidth: function () { return 0.5; },
                            hLineColor: function () { return '#DBDADE'; },
                            vLineColor: function () { return '#DBDADE'; },
                            paddingLeft: function () { return 4; },
                            paddingRight: function () { return 4; },
                            paddingTop: function () { return 3; },
                            paddingBottom: function () { return 3; }
                        }
                    }
                ],

                
                footer: function (currentPage, pageCount) {
                    return {
                        margin: [30, 8, 30, 0],
                        columns: [
                            { text: 'Dicetak pada: ' + new Date().toLocaleString('id-ID'), style: 'footerText' },
                            {
                                text: (info.copyright || '') + '  |  Halaman ' + currentPage + ' dari ' + pageCount,
                                style: 'footerText',
                                alignment: 'right'
                            }
                        ]
                    };
                },

                styles: {
                    companyName:   { fontSize: 13, bold: true, color: '#5F61E6' },
                    companyInfo:   { fontSize: 8,  color: '#697A8D' },
                    pageNumber:    { fontSize: 8,  color: '#697A8D' },
                    documentTitle: { fontSize: 14, bold: true, color: '#5F61E6' },
                    dateText:      { fontSize: 9,  color: '#697A8D' },
                    tableHeader:   { bold: true, fontSize: 8, color: '#FFFFFF' },
                    footerText:    { fontSize: 7,  color: '#697A8D' }
                },
                defaultStyle: { fontSize: 7 }
            };

            pdfMake.createPdf(docDefinition).download((filename || 'Export') + '_' + new Date().toISOString().slice(0, 10) + '.pdf');

        } catch (err) {
            console.error('SimkosExport.buildPDF error:', err);
            alert('Terjadi kesalahan saat export PDF: ' + err.message);
        }
    }

    
    return {
        toggleColumns: toggleColumns,
        buildExcel:    buildExcel,
        buildPDF:      buildPDF,
        formatRupiah:  _formatRupiah   
    };

})();
