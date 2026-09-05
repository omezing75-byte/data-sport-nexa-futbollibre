import { writeFile, rename } from 'node:fs/promises';

const CONFIG_PATH = new URL('./config-source.json', import.meta.url);
const SOURCE_CONFIG = JSON.parse(await (await fetch(CONFIG_PATH)).text());
const SOURCE_URL = SOURCE_CONFIG.source_url;


const OUTPUT_FILE = '../eventos.json';
const TEMP_FILE = `${OUTPUT_FILE}.tmp`;

const response = await fetch(SOURCE_URL, {
  headers: {
    'User-Agent': 'data-sport-nexa-github-sync/2.0',
    'Accept': 'application/json'
  }
});

if (!response.ok) {
  throw new Error(`Gagal mengambil sumber: HTTP ${response.status}`);
}

const text = await response.text();
if (!text.trim()) throw new Error('Respons kosong. File GitHub tidak diubah.');

let source;
try {
  source = JSON.parse(text);
} catch (err) {
  throw new Error(`JSON sumber tidak valid: ${err.message}`);
}

if (!source || typeof source !== 'object' || !Array.isArray(source.data)) {
  throw new Error('Format diaries.json tidak sesuai: properti "data" tidak ditemukan.');
}

const tzByCountry = {
  Colombia: 'America/Bogota',
  Peru: 'America/Lima',
  Ecuador: 'America/Guayaquil',
  'Costa Rica': 'America/Costa_Rica',
  Panama: 'America/Panama',
  Guatemala: 'America/Guatemala',
  Honduras: 'America/Tegucigalpa',
  Nicaragua: 'America/Managua',
  'El Salvador': 'America/El_Salvador',
  Mexico: 'America/Mexico_City',
  Brazil: 'America/Sao_Paulo',
  Argentina: 'America/Argentina/Buenos_Aires',
  Uruguay: 'America/Montevideo',
  Paraguay: 'America/Asuncion',
  Chile: 'America/Santiago',
  Bolivia: 'America/La_Paz',
  Venezuela: 'America/Caracas',
  Spain: 'Europe/Madrid',
  Italy: 'Europe/Rome',
  Germany: 'Europe/Berlin',
  France: 'Europe/Paris',
  England: 'Europe/London',
  'United Kingdom': 'Europe/London',
  USA: 'America/New_York',
  'United States': 'America/New_York'
};

function clean(v) {
  return String(v ?? '').trim();
}

function decodeBase64(value) {
  const s = clean(value);
  if (!s) return '';
  try {
    return Buffer.from(s, 'base64').toString('utf8');
  } catch {
    return '';
  }
}

function absoluteUrl(value) {
  const s = clean(value);
  if (!s) return '';
  try {
    return new URL(s, SOURCE_URL).href;
  } catch {
    return '';
  }
}

function extractEmbedUrl(iframe) {
  const absolute = absoluteUrl(iframe);
  if (!absolute) return '';

  try {
    const u = new URL(absolute);
    const encoded = u.searchParams.get('r');
    if (encoded) {
      const decoded = decodeBase64(encoded);
      if (decoded) return decoded;
    }
  } catch {}

  return absolute;
}

function countryInfo(attrs) {
  const country = attrs?.country?.data?.attributes || {};
  const name = clean(country.name);
  const image = country?.image?.data?.attributes || {};
  return {
    name,
    flagUrl: absoluteUrl(image.url)
  };
}

const sports = new Map();

for (const item of source.data) {
  const attrs = item?.attributes;
  if (!attrs || typeof attrs !== 'object') continue;

  const description = clean(attrs.diary_description);
  const date = clean(attrs.date_diary);
  const hour = clean(attrs.diary_hour);

  if (!description || !date || !hour) continue;

  // diary_description biasanya berbentuk "Liga: Tim A vs Tim B".
  const parts = description.split(/\\n|\\r\\n/).map(clean).filter(Boolean);
  const first = parts[0] || description;
  const colon = first.indexOf(':');
  const leagueName = colon > 0 ? clean(first.slice(0, colon)) : 'Agenda';
  const title = colon > 0 ? clean(first.slice(colon + 1)) : first;

  const country = countryInfo(attrs);
  const timezone = tzByCountry[country.name] || 'America/Bogota';

  const sportName = 'Agenda';
  if (!sports.has(sportName)) {
    sports.set(sportName, {
      name: sportName,
      icon: '🏆',
      leagues: new Map()
    });
  }

  const sport = sports.get(sportName);
  if (!sport.leagues.has(leagueName)) {
    sport.leagues.set(leagueName, {
      name: leagueName,
      events: []
    });
  }

  const embeds = Array.isArray(attrs?.embeds?.data) ? attrs.embeds.data : [];
  const servers = [];

  for (const embed of embeds) {
    const ea = embed?.attributes;
    if (!ea) continue;

    const url = extractEmbedUrl(ea.embed_iframe);
    if (!url) continue;

    servers.push({
      name: clean(ea.embed_name) || 'Link TV',
      url,
      active: true
    });
  }

  sport.leagues.get(leagueName).events.push({
    id: item.id,
    title,
    time: `${date}T${hour}`,
    timezone,
    flagCode: country.name,
    country: country.name,
    flagUrl: country.flagUrl,
    servers,
    agendaOrder: Number(item.id) || 999999
  });
}

const normalized = {
  source: SOURCE_URL,
  updatedAt: new Date().toISOString(),
  sports: Array.from(sports.values()).map(s => ({
    name: s.name,
    icon: s.icon,
    leagues: Array.from(s.leagues.values())
  }))
});

const eventCount = normalized.sports.reduce(
  (sum, sport) => sum + sport.leagues.reduce((n, league) => n + league.events.length, 0),
  0
);

if (eventCount === 0) {
  throw new Error('diaries.json berhasil dibaca tetapi tidak memiliki event yang valid. File GitHub tidak diubah.');
}

await writeFile(TEMP_FILE, JSON.stringify(normalized, null, 2) + '\n', 'utf8');
await rename(TEMP_FILE, OUTPUT_FILE);

console.log(`Sinkronisasi berhasil: ${eventCount} event.`);
console.log(`Sumber utama: ${SOURCE_URL}`);
