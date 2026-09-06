import { readFile, writeFile, rename } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_FILE = path.join(SCRIPT_DIR, 'config-source.json');
const OUTPUT_FILE = path.join(SCRIPT_DIR, '..', 'eventos.json');
const TEMP_FILE = `${OUTPUT_FILE}.tmp`;

const config = JSON.parse(await readFile(CONFIG_FILE, 'utf8'));
const SOURCE_URL = String(config.source_url || '').trim();

if (!SOURCE_URL) {
  throw new Error('config-source.json tidak memiliki source_url.');
}

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
if (!text.trim()) throw new Error('Respons kosong. eventos.json lama tidak diubah.');

let source;
try {
  source = JSON.parse(text);
} catch (err) {
  throw new Error(`JSON sumber tidak valid: ${err.message}`);
}

if (!source || !Array.isArray(source.data)) {
  throw new Error('Format diaries.json tidak sesuai: properti \"data\" tidak ditemukan.');
}

if (new URL(SOURCE_URL).pathname.endsWith('/eventos.json')) {
  throw new Error('source_url tidak boleh menunjuk ke eventos.json hasil sinkronisasi. Gunakan diaries.json sebagai sumber utama.');
}

const TZ = {
  'Argentina':'America/Argentina/Buenos_Aires',
  'Bolivia':'America/La_Paz',
  'Brasil':'America/Sao_Paulo',
  'Brazil':'America/Sao_Paulo',
  'Chile':'America/Santiago',
  'Colombia':'America/Bogota',
  'Costa Rica':'America/Costa_Rica',
  'Ecuador':'America/Guayaquil',
  'España':'Europe/Madrid',
  'Spain':'Europe/Madrid',
  'Estados Unidos':'America/New_York',
  'USA':'America/New_York',
  'Inglaterra':'Europe/London',
  'México':'America/Mexico_City',
  'Mexico':'America/Mexico_City',
  'Panamá':'America/Panama',
  'Panama':'America/Panama',
  'Paraguay':'America/Asuncion',
  'Perú':'America/Lima',
  'Peru':'America/Lima',
  'Portugal':'Europe/Lisbon',
  'Uruguay':'America/Montevideo',
  'Venezuela':'America/Caracas',
  'Canadá':'America/Toronto',
  'Canada':'America/Toronto',
  'Italia':'Europe/Rome',
  'Italy':'Europe/Rome',
  'Francia':'Europe/Paris',
  'France':'Europe/Paris',
  'Alemania':'Europe/Berlin',
  'Germany':'Europe/Berlin',
  'Países Bajos':'Europe/Amsterdam',
  'Netherlands':'Europe/Amsterdam',
  'Japón':'Asia/Tokyo',
  'Japan':'Asia/Tokyo',
  'Australia':'Australia/Sydney'
};

function countryName(item) {
  return String(item?.attributes?.country?.data?.attributes?.name || '').trim();
}

function timezoneFor(country, attrs = {}) {
  const explicit = String(attrs.timezone || attrs.time_zone || attrs.tz || '').trim();
  if (explicit) return explicit;
  return TZ[country] || 'UTC';
}

function localToUtcIso(local, tz) {
  const m = String(local || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return null;
  const wanted = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, hourCycle: 'h23'
    });
    const parts = ms => {
      const out = {};
      for (const x of fmt.formatToParts(new Date(ms))) if (x.type !== 'literal') out[x.type] = Number(x.value);
      return out;
    };
    let guess = wanted;
    for (let i = 0; i < 6; i++) {
      const q = parts(guess);
      const actual = Date.UTC(q.year, q.month - 1, q.day, q.hour, q.minute, q.second);
      const diff = wanted - actual;
      guess += diff;
      if (diff === 0) break;
    }
    return new Date(guess).toISOString();
  } catch {
    return new Date(wanted).toISOString();
  }
}

function sportFor(description, league) {
  const s = `${description} ${league}`.toLowerCase();
  if (/(nba|wnba|basket|baloncesto|basketball)/i.test(s)) return { name:'Basketball', icon:'🏀' };
  if (/(mlb|baseball|béisbol|beisbol)/i.test(s)) return { name:'Baseball', icon:'⚾' };
  if (/(nfl|football americano|american football)/i.test(s)) return { name:'American Football', icon:'🏈' };
  if (/(nhl|hockey|hóckey)/i.test(s)) return { name:'Hockey', icon:'🏒' };
  if (/(tenis|tennis|atp|wta|us open|roland garros|wimbledon)/i.test(s)) return { name:'Tennis', icon:'🎾' };
  if (/(f1|formula 1|formula1|motogp|moto gp|indycar|nascar)/i.test(s)) return { name:'Motorsport', icon:'🏎️' };
  if (/(golf)/i.test(s)) return { name:'Golf', icon:'⛳' };
  return { name:'Football', icon:'⚽' };
}

function flagCode(country, league, description) {
  const map = {
    'Alemania':'ALE','Argentina':'AR','Brasil':'BRA','Brazil':'BRA',
    'Chile':'CH','Colombia':'COL','Ecuador':'ECUA','Inglaterra':'ENG',
    'Italia':'IT','Paraguay':'LIGAPY','Rusia':'RUS','Uruguay':'URU',
    'Estados Unidos':'USOPEN','USA':'USOPEN','México':'LEAGUESCUP',
    'Mexico':'LEAGUESCUP'
  };
  if (map[country]) return map[country];
  const s=`${league} ${description}`.toUpperCase();
  if (s.includes('MLB')) return 'MLB';
  if (s.includes('CICLISMO') || s.includes('CYCLING')) return 'CICLISMO';
  return '';
}

function decodeBase64Url(value) {
  try {
    const m = String(value || '').match(/[?&]r=([^&]+)/);
    if (!m) return null;
    return Buffer.from(decodeURIComponent(m[1]), 'base64').toString('utf8');
  } catch {
    return null;
  }
}

function absoluteEmbedUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try { return new URL(raw, new URL(SOURCE_URL).origin).href; }
  catch { return raw; }
}

const sportsMap = new Map();
let eventCount = 0;
let serverCount = 0;

for (const item of source.data) {
  const a = item?.attributes;
  if (!a) continue;

  const description = String(a.diary_description || '').trim();
  const date = String(a.date_diary || '').trim();
  const hour = String(a.diary_hour || '').trim();

  if (!description || !date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}/.test(hour)) continue;

  const lines = description.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const leagueName = lines.length > 1 ? lines[0].replace(/:\s*$/, '') : '';
  const title = lines.length > 1 ? lines.slice(1).join(' ') : lines[0].replace(/:\s*$/, '');
  const country = countryName(item);
  const sport = sportFor(description, leagueName);
  const sportKey = sport.name;

  if (!sportsMap.has(sportKey)) {
    sportsMap.set(sportKey, {
      name: sport.name,
      icon: sport.icon,
      leagues: new Map()
    });
  }

  const sportObj = sportsMap.get(sportKey);
  const leagueKey = `${country}|${leagueName || 'General'}`;
  if (!sportObj.leagues.has(leagueKey)) {
    sportObj.leagues.set(leagueKey, {
      name: leagueName || 'General',
      country,
      events: []
    });
  }

  const servers = [];
  const embeds = a.embeds?.data;
  if (Array.isArray(embeds)) {
    for (const emb of embeds) {
      const ea = emb?.attributes;
      if (!ea) continue;
      const name = String(ea.embed_name || 'Link TV').trim();
      const iframe = absoluteEmbedUrl(ea.embed_iframe);
      const decoded = decodeBase64Url(iframe);
      const url = decoded || iframe;
      if (!url) continue;
      servers.push({ name, url, active:true });
      serverCount++;
    }
  }

  const localTime = `${date}T${hour}`;
  const tz = timezoneFor(country, a);
  const utcTime = localToUtcIso(localTime, tz);
  const event = {
    id: String(item.id ?? `${date}-${hour}-${title}`),
    title,
    time: localTime,
    timezone: tz,
    utcTime,
    flagCode: flagCode(country, leagueName, description),
    servers
  };

  sportObj.leagues.get(leagueKey).events.push(event);
  eventCount++;
}

if (eventCount === 0) {
  throw new Error('Sumber berhasil dibaca tetapi tidak memiliki event valid. eventos.json lama tidak diubah.');
}

const sports = [...sportsMap.values()].map(s => ({
  name: s.name,
  icon: s.icon,
  leagues: [...s.leagues.values()].map(l => ({
    name: l.name,
    country: l.country,
    events: l.events
  }))
}));

const output = {
  generatedAt: new Date().toISOString(),
  source: SOURCE_URL,
  sports
};

await writeFile(TEMP_FILE, JSON.stringify(output, null, 2) + '\n', 'utf8');
await rename(TEMP_FILE, OUTPUT_FILE);

const leagueCount = sports.reduce((n,s)=>n+s.leagues.length,0);
console.log(`Sinkronisasi berhasil: ${sports.length} olahraga, ${leagueCount} liga, ${eventCount} event, ${serverCount} link.`);
console.log(`Sumber: ${SOURCE_URL}`);
