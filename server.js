// server.js - Railway Backend für SERGAJ Optimizer
// npm install express

const express = require('express');
const app = express();
app.use(express.json());

// ============================================================
// KEYS DATENBANK - hier deine Keys eintragen
// Format: 'KEY': { active: true, days: 30, hwid: null }
// hwid: null = noch nicht gebunden, wird beim ersten Login gesetzt
// ============================================================
const keys = {
  'SERGAJ-TESTKEY1': { active: true, days: 30,  hwid: null },
  'SERGAJ-TESTKEY2': { active: true, days: 7,   hwid: null },
  'SERGAJ-LIFETIME': { active: true, days: 9999, hwid: null },
  // Weitere Keys hier eintragen...
};

// ============================================================
// VALIDATE ENDPOINT
// ============================================================
app.post('/validate', (req, res) => {
  const { key, hwid } = req.body;

  if (!key) {
    return res.json({ valid: false, reason: 'No key provided' });
  }

  const entry = keys[key.toUpperCase().trim()];

  if (!entry) {
    return res.json({ valid: false, reason: 'Invalid key' });
  }

  if (!entry.active) {
    return res.json({ valid: false, reason: 'Key deactivated' });
  }

  // HWID Lock Logik
  if (hwid) {
    if (entry.hwid === null) {
      // Erster Login: HWID binden
      entry.hwid = hwid;
      console.log(`Key ${key} bound to HWID: ${hwid}`);
    } else if (entry.hwid !== hwid) {
      // Anderer PC versucht den Key zu nutzen
      console.log(`HWID mismatch for key ${key}. Expected: ${entry.hwid}, Got: ${hwid}`);
      return res.json({ valid: false, reason: 'Key already used on another PC' });
    }
  }

  return res.json({
    valid: true,
    reason: 'Activated',
    days_left: entry.days
  });
});

// ============================================================
// ADMIN ENDPOINTS (optional - zum Key verwalten)
// ============================================================

// Key resetten (HWID loeschen) - z.B. wenn Kunde PC wechselt
// GET /admin/reset?key=SERGAJ-TESTKEY1&secret=DEIN_GEHEIMES_PASSWORT
app.get('/admin/reset', (req, res) => {
  const { key, secret } = req.query;
  
  if (secret !== process.env.ADMIN_SECRET) {
    return res.json({ success: false, reason: 'Unauthorized' });
  }

  const k = key?.toUpperCase().trim();
  if (!keys[k]) {
    return res.json({ success: false, reason: 'Key not found' });
  }

  keys[k].hwid = null;
  console.log(`HWID reset for key: ${k}`);
  return res.json({ success: true, reason: 'HWID reset' });
});

// Key deaktivieren
// GET /admin/deactivate?key=SERGAJ-TESTKEY1&secret=DEIN_GEHEIMES_PASSWORT
app.get('/admin/deactivate', (req, res) => {
  const { key, secret } = req.query;

  if (secret !== process.env.ADMIN_SECRET) {
    return res.json({ success: false, reason: 'Unauthorized' });
  }

  const k = key?.toUpperCase().trim();
  if (!keys[k]) {
    return res.json({ success: false, reason: 'Key not found' });
  }

  keys[k].active = false;
  console.log(`Key deactivated: ${k}`);
  return res.json({ success: true, reason: 'Key deactivated' });
});

// Alle Keys anzeigen
// GET /admin/list?secret=DEIN_GEHEIMES_PASSWORT
app.get('/admin/list', (req, res) => {
  const { secret } = req.query;
  if (secret !== process.env.ADMIN_SECRET) {
    return res.json({ success: false, reason: 'Unauthorized' });
  }
  return res.json(keys);
});

// Health check
app.get('/', (req, res) => res.send('SERGAJ Backend running'));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
