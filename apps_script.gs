/**
 * Coderhouse — Postulaciones webhook
 *
 * 1. Crear un Google Sheet llamado "Postulaciones Profesores".
 * 2. Extensions → Apps Script → pegar este código.
 * 3. Implementar → Nueva implementación → Tipo: Web App.
 *    - Ejecutar como: Yo (tu cuenta)
 *    - Quién tiene acceso: Cualquier persona
 * 4. Copiar la URL del Web App y pegarla en index.html (const APPS_SCRIPT_URL).
 */

const SHEET_NAME = 'Postulaciones';
const HEADERS = ['Timestamp', 'Nombre', 'Email', 'Teléfono', 'LinkedIn', 'Pitch', 'Curso', 'N° Comisión', 'Horario', 'Inicio', 'Modalidad'];

function doPost(e) {
  try {
    const p = e.parameter || {};
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(HEADERS);
      sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
      sheet.setFrozenRows(1);
    }
    sheet.appendRow([
      new Date(),
      p.nombre || '',
      p.email || '',
      p.telefono || '',
      p.linkedin || '',
      p.pitch || '',
      p.curso || '',
      p.comisionId || '',
      p.horario || '',
      p.inicio || '',
      p.modality || ''
    ]);
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService.createTextOutput('Coderhouse postulaciones webhook — usar POST.');
}
