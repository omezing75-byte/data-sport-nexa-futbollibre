import { writeFile, rename } from 'node:fs/promises';

const SOURCE_URL = 'https://futbollibretv.org.pe/diaries.json';
const OUTPUT_FILE = 'agenda.json';
const TEMP_FILE = `${OUTPUT_FILE}.tmp`;
const DEFAULT_TIMEZONE = 'America/Lima';

function decodeBase64Url(value) {
  const raw = String(value || '');
  const marker = 'r=';
  const i = raw.indexOf(marker);
  if (i < 0) return '';
  const encoded = raw.slice(i + marker.length).split('&')[0];
  try {
    return Buffer.from(decodeURIComponent(encoded), 'base64').toString('utf8');
  } catch {
    try { return Buffer.from(encoded, 'base64').toString('utf8'); } catch { return ''; }
  }
}

function absoluteUrl(value) {
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return `https://futbollibretv.org.pe${value.startsWith('/') ? '' : '/'}${value}`;
}

function countryCode(name) {
  const map = {
    'Alemania': 'ale', 'Argentina': 'ar', 'Brasil': 'bra', 'Chile': 'ch',
    'Colombia': 'col', 'Ecuador': 'ecua', 'España': 'es', 'Inglaterra': 'eng',
    'Italia': 'it', 'México': 'mx', 'Mexico': 'mx', 'Perú': 'pe', 'Peru': 'pe',
    'Portugal': 'pt', 'Rusia': 'rus', 'Uruguay': 'uy', 'Estados Unidos': 'us',
    'Tennis': 'usopen', 'MLB': 'mlb', 'League Cup': 'ligacup'
  };
  return map[name] || '';
}

const response = await fetch(SOURCE_URL, {
  headers: {
    'User-Agent': 'data-sport-nexa-github-sync/2.0',
    'Accept': 'application/json'
  }
});

if (!response.ok) throw new Error(`Gagal mengambil sumber: HTTP ${response.status}`);
const text = await response.text();
if (!text.trim()) throw new Error('Respons kosong. agenda.json lama tidak diubah.');

let source;
try { source = JSON.parse(text); }
catch (err) { throw new Error(`JSON sumber tidak valid: ${err.message}`); }

if (!source || !Array.isArray(source.data)) {
  throw new Error('Format diaries.json tidak sesuai: properti data[] tidak ditemukan.');
}

const agenda = [];
for (const item of source.data) {
  const a = item?.attributes;
  if (!a?.date_diary || !a?.diary_hour) continue;

  const description = String(a.diary_description || '').trim();
  const lines = description.split(/\n+/).map(s => s.trim()).filter(Boolean);
  const title = lines.length > 1 ? lines[lines.length - 1] : (lines[0] || 'Agenda');
  const category = lines.length > 1 ? lines[0].replace(/:$/, '') : '';
  const country = a.country?.data?.attributes?.name || '';
  const flagPath = a.country?.data?.attributes?.image?.data?.attributes?.url || '';
  const flagCode = countryCode(country);

  const embeds = Array.isArray(a.embeds?.data) ? a.embeds.data : [];
  const servers = [];
  for (const embed of embeds) {
    const ea = embed?.attributes;
    if (!ea?.embed_name || !ea?.embed_iframe) continue;
    const url = decodeBase64Url(ea.embed_iframe);
    if (!url) continue;
    servers.push({ name: ea.embed_name, url, active: true });
  }

  // Only keep events that actually have a usable player link.
  if (!servers.length) continue;

  const id = String(item.id ?? '');
  const time = `${a.date_diary}T${String(a.diary_hour).slice(0, 8)}`;
  agenda.push({
    id,
    time,
    timezone: DEFAULT_TIMEZONE,
    title,
    category,
    country,
    flagCode,
    flagUrl: absoluteUrl(flagPath),
    servers,
    source: SOURCE_URL,
    updatedAt: a.updatedAt || a.publishedAt || null
  });
}

agenda.sort((a, b) => a.time.localeCompare(b.time));
if (!agenda.length) throw new Error('Tidak ditemukan event dengan link embed yang valid. agenda.json lama tidak diubah.');

await writeFile(TEMP_FILE, JSON.stringify(agenda, null, 2) + '\n', 'utf8');
await rename(TEMP_FILE, OUTPUT_FILE);

console.log(`Sinkronisasi berhasil: ${agenda.length} event.`);
console.log(`Sumber utama: ${SOURCE_URL}`);
console.log(`Output: ${OUTPUT_FILE}`);
