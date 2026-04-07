// NBA Edge Model — Season Backtest Script
// Pulls games via BallDontLie, scores fatigue, outputs CSV of flagged games (score >= 5)
//
// Run in PowerShell:
//   $env:BDL_API_KEY="your_key"
//   node nba_backtest.js --start 2024-11-01 --end 2025-04-13 > output.csv
//   node nba_backtest.js > output.csv  (defaults to current season)

const API_KEY = process.env.BDL_API_KEY;
if(!API_KEY) { console.error('ERROR: BDL_API_KEY environment variable not set.\n  PowerShell: $env:BDL_API_KEY="your_key"'); process.exit(1); }

const BASE_URL = 'https://api.balldontlie.io/v1';

// ── CLI ARGS ──────────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { start: '2025-11-01', end: '2026-04-13' };  // current season defaults
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--start' && args[i+1]) opts.start = args[++i];
    if (args[i] === '--end' && args[i+1]) opts.end = args[++i];
  }
  return opts;
}

const { start: SEASON_START, end: SEASON_END } = parseArgs();
const FLAG_THRESHOLD = 5;

// ── ARENA DATA ──────────────────────────────────────────────────
const ARENAS = {
  ATL:{lat:33.7573,lon:-84.3963,tz:'America/New_York'},BOS:{lat:42.3662,lon:-71.0621,tz:'America/New_York'},
  BKN:{lat:40.6826,lon:-73.9754,tz:'America/New_York'},CHA:{lat:35.2251,lon:-80.8392,tz:'America/New_York'},
  CHI:{lat:41.8807,lon:-87.6742,tz:'America/Chicago'},CLE:{lat:41.4965,lon:-81.6882,tz:'America/New_York'},
  DAL:{lat:32.7905,lon:-96.8103,tz:'America/Chicago'},DEN:{lat:39.7487,lon:-105.0077,tz:'America/Denver'},
  DET:{lat:42.3410,lon:-83.0552,tz:'America/Detroit'},GSW:{lat:37.7680,lon:-122.3877,tz:'America/Los_Angeles'},
  HOU:{lat:29.7508,lon:-95.3621,tz:'America/Chicago'},IND:{lat:39.7640,lon:-86.1555,tz:'America/Indiana/Indianapolis'},
  LAC:{lat:33.8958,lon:-118.3386,tz:'America/Los_Angeles'},LAL:{lat:34.0430,lon:-118.2673,tz:'America/Los_Angeles'},
  MEM:{lat:35.1383,lon:-90.0505,tz:'America/Chicago'},MIA:{lat:25.7814,lon:-80.1870,tz:'America/New_York'},
  MIL:{lat:43.0450,lon:-87.9170,tz:'America/Chicago'},MIN:{lat:44.9795,lon:-93.2762,tz:'America/Chicago'},
  NOP:{lat:29.9490,lon:-90.0812,tz:'America/Chicago'},NYK:{lat:40.7505,lon:-73.9934,tz:'America/New_York'},
  OKC:{lat:35.4634,lon:-97.5151,tz:'America/Chicago'},ORL:{lat:28.5392,lon:-81.3839,tz:'America/New_York'},
  PHI:{lat:39.9012,lon:-75.1720,tz:'America/New_York'},PHX:{lat:33.4457,lon:-112.0712,tz:'America/Phoenix'},
  POR:{lat:45.5316,lon:-122.6668,tz:'America/Los_Angeles'},SAC:{lat:38.5802,lon:-121.4997,tz:'America/Los_Angeles'},
  SAS:{lat:29.4270,lon:-98.4375,tz:'America/Chicago'},TOR:{lat:43.6435,lon:-79.3791,tz:'America/Toronto'},
  UTA:{lat:40.7683,lon:-111.9011,tz:'America/Denver'},WAS:{lat:38.8981,lon:-77.0209,tz:'America/New_York'},
};

const ALTITUDE_TEAMS = new Set(['DEN', 'UTA']);

function haversine(lat1,lon1,lat2,lon2) {
  const R=3959,dLat=(lat2-lat1)*Math.PI/180,dLon=(lon2-lon1)*Math.PI/180;
  const a=Math.sin(dLat/2)**2+Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
  return Math.round(R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a)));
}

function getDist(a,b) {
  if(a===b) return 0;
  if((a==='LAL'&&b==='LAC')||(a==='LAC'&&b==='LAL')) return 12;
  if((a==='NYK'&&b==='BKN')||(a==='BKN'&&b==='NYK')) return 8;
  if(!ARENAS[a]||!ARENAS[b]) return 0;
  return haversine(ARENAS[a].lat,ARENAS[a].lon,ARENAS[b].lat,ARENAS[b].lon);
}

function getUtcOffset(tzName, date) {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: tzName,
    timeZoneName: 'shortOffset',
  });
  const parts = formatter.formatToParts(date instanceof Date ? date : new Date(date));
  const tzPart = parts.find(p => p.type === 'timeZoneName');
  const match = tzPart.value.match(/GMT([+-]?\d+(?::\d+)?)/);
  if (!match) return -5;
  const val = match[1];
  if (val.includes(':')) {
    const [h, m] = val.split(':').map(Number);
    return h + (h < 0 ? -1 : 1) * m / 60;
  }
  return parseInt(val);
}

function parseTipET(datetimeStr) {
  if(!datetimeStr) return 19.5;
  const d = new Date(datetimeStr);
  const etOffset = getUtcOffset('America/New_York', d);
  const etHour = (d.getUTCHours() + etOffset + 24) % 24;
  return etHour + d.getUTCMinutes() / 60;
}

function estimateBTBSleep(fromArena, toArena, tonightTipET, prevTipDatetime, gameDate) {
  const dist = getDist(fromArena, toArena);
  const flightHrs = dist / 500;
  const gd = gameDate || new Date();
  const fromTZ = getUtcOffset(ARENAS[fromArena]?.tz ?? 'America/Chicago', gd);
  const toTZ   = getUtcOffset(ARENAS[toArena]?.tz   ?? 'America/Chicago', gd);
  const etOffset = getUtcOffset('America/New_York', gd);

  let prevTipLocal = 20.0;
  if (prevTipDatetime) {
    const prevDate = new Date(prevTipDatetime);
    const prevLocalOffset = getUtcOffset(ARENAS[fromArena]?.tz ?? 'America/Chicago', prevDate);
    prevTipLocal = (prevDate.getUTCHours() + prevLocalOffset + 24) % 24 + prevDate.getUTCMinutes() / 60;
  }

  const prevTipET = prevTipLocal - fromTZ + etOffset;
  const prevGameEndET = prevTipET + 2.5;
  const departureET   = prevGameEndET + 2.5;
  const landingET     = departureET + flightHrs;
  const hotelArrivalET = landingET + 0.75;
  const hotelArrivalLocal = hotelArrivalET + toTZ - etOffset;
  const tipLocal = tonightTipET + toTZ - etOffset;
  const wakeUpLocal = tipLocal - 3.0;
  const hotelSleepHrs = Math.max(0, wakeUpLocal - hotelArrivalLocal);
  const midnightDelta = hotelArrivalLocal - 24;
  const planeSleepHrs = midnightDelta > 0 ? Math.min(flightHrs * 0.6, midnightDelta) : 0;
  const totalEffectiveSleep = hotelSleepHrs + (planeSleepHrs * 0.5);
  return {
    dist, flightHrs: Math.round(flightHrs*10)/10,
    hotelSleepHrs: Math.round(hotelSleepHrs*10)/10,
    totalEffectiveSleep: Math.round(totalEffectiveSleep*10)/10,
    tzDelta: toTZ - fromTZ,
  };
}

function computeFatigueScore(params) {
  const { scenario, effectiveSleep, tzDelta, isBTB, prevTipLocalHr, gamesIn4, gamesIn6, altitudePenalty } = params;

  if(!isBTB && scenario !== 'home-home') {
    let score = 0;
    if(gamesIn4 >= 3) score += gamesIn6 >= 4 ? 2 : 1;
    else if(gamesIn6 >= 4) score += 2;
    score += (altitudePenalty || 0);
    return Math.min(10, Math.max(0, score));
  }

  const BASE = { A:5, B:3, C:4, 'home-home':2 };
  let score = BASE[scenario] || 2;

  const sleep = effectiveSleep ?? 6;
  if(sleep < 4)        score += 4;
  else if(sleep < 6)   score += 2;
  else if(sleep < 7)   score += 1;

  if(tzDelta > 0) score += Math.min(tzDelta * 0.5, 1.5);
  if(prevTipLocalHr && prevTipLocalHr >= 21.5) score += 0.5;

  if(gamesIn4 >= 3) score += gamesIn6 >= 4 ? 2 : 1;
  else if(gamesIn6 >= 4) score += 2;

  score += (altitudePenalty || 0);

  return Math.min(10, Math.max(0, Math.round(score * 10) / 10));
}

function analyzeFatigue(teamAbbr, isHome, daysRest, prevArena, homeTeamAbbr, tipET, wasHomeLastGame, gamesIn4=1, gamesIn6=1, recentAltitudeVisit=false, prevTipDatetime=null, gameDate=null) {
  if(daysRest === null) return { tier:'good', score:0, isBTB:false, scenario:'unknown', detail:'Rest unknown' };

  const isBTB = daysRest === 0;
  const altitudePenalty = (!isHome && ALTITUDE_TEAMS.has(homeTeamAbbr) && !recentAltitudeVisit) ? 1.0 : 0;

  // Compute actual previous tip local hour from real datetime
  let prevTipLocalHr = 19.5;
  if (prevTipDatetime && prevArena && ARENAS[prevArena]) {
    const prevDate = new Date(prevTipDatetime);
    const prevLocalOffset = getUtcOffset(ARENAS[prevArena].tz, prevDate);
    prevTipLocalHr = (prevDate.getUTCHours() + prevLocalOffset + 24) % 24 + prevDate.getUTCMinutes() / 60;
  }

  if(!isBTB) {
    const score = computeFatigueScore({ scenario:'rest', effectiveSleep:99, tzDelta:0, isBTB:false, gamesIn4, gamesIn6, altitudePenalty });
    const tier = daysRest >= 2 ? 'full' : 'good';
    const dist = isHome ? 0 : getDist(prevArena || teamAbbr, homeTeamAbbr);
    const gd = gameDate || new Date();
    const homeTZ = getUtcOffset(ARENAS[homeTeamAbbr]?.tz ?? 'America/New_York', gd);
    const prevTZ = getUtcOffset(ARENAS[prevArena ?? teamAbbr]?.tz ?? 'America/Chicago', gd);
    const tzDelta = isHome ? 0 : homeTZ - prevTZ;
    const severeBodyClock = !isHome && daysRest === 1 && tzDelta >= 2 && dist > 1800;
    return {
      tier: severeBodyClock ? 'average' : tier,
      score, isBTB:false, scenario:'rest',
      detail: isHome ? 'Home' : `Road ${daysRest}d rest`,
    };
  }

  if(isHome) {
    if(!wasHomeLastGame) {
      const sleep = estimateBTBSleep(prevArena || teamAbbr, homeTeamAbbr, tipET, prevTipDatetime, gameDate);
      const adj = Math.round((sleep.totalEffectiveSleep + 1.5) * 10) / 10;
      const score = computeFatigueScore({ scenario:'C', effectiveSleep:adj, tzDelta:sleep.tzDelta, isBTB:true, prevTipLocalHr, gamesIn4, gamesIn6, altitudePenalty:0 });
      return { tier: adj>=7?'average':adj>=4?'poor':'critical', score, isBTB:true, scenario:'C', effectiveSleep:adj, detail:`BTB home (C) flew ${sleep.dist}mi home` };
    } else {
      const score = computeFatigueScore({ scenario:'home-home', effectiveSleep:6, tzDelta:0, isBTB:true, prevTipLocalHr, gamesIn4, gamesIn6, altitudePenalty:0 });
      return { tier:'average', score, isBTB:true, scenario:'home-home', effectiveSleep:6, detail:'BTB home-home' };
    }
  }

  if(wasHomeLastGame) {
    const dist = getDist(teamAbbr, homeTeamAbbr);
    const flightHrs = dist / 500;
    const gd = gameDate || new Date();
    const homeTZ = getUtcOffset(ARENAS[homeTeamAbbr]?.tz ?? 'America/New_York', gd);
    const teamTZ = getUtcOffset(ARENAS[teamAbbr]?.tz ?? 'America/New_York', gd);
    const tzDelta = homeTZ - teamTZ;
    const bodyClockPenalty = tzDelta > 0 ? tzDelta * 0.3 : 0;
    const adj = Math.round(Math.max(0, 7.0 - bodyClockPenalty) * 10) / 10;
    const score = computeFatigueScore({ scenario:'B', effectiveSleep:adj, tzDelta, isBTB:true, prevTipLocalHr, gamesIn4, gamesIn6, altitudePenalty });
    return { tier: adj>=7?'average':adj>=4?'poor':'critical', score, isBTB:true, scenario:'B', effectiveSleep:adj, detail:`BTB home→away (B) ${dist}mi` };
  }

  const fromArena = prevArena || teamAbbr;
  const sleep = estimateBTBSleep(fromArena, homeTeamAbbr, tipET, prevTipDatetime, gameDate);
  const adj = Math.max(0, sleep.totalEffectiveSleep);
  const score = computeFatigueScore({ scenario:'A', effectiveSleep:adj, tzDelta:sleep.tzDelta, isBTB:true, prevTipLocalHr, gamesIn4, gamesIn6, altitudePenalty });
  return { tier: adj>=7?'average':adj>=4?'poor':'critical', score, isBTB:true, scenario:'A', effectiveSleep:adj, detail:`BTB road (A) ${sleep.dist}mi` };
}

function calcRest(games, teamId, targetDate) {
  const played = games
    .filter(g => g.status === 'Final' && (g.home_team.id === teamId || g.visitor_team.id === teamId))
    .sort((a,b) => new Date(b.date) - new Date(a.date));

  if(!played.length) return { daysRest:null, prevLocation:null, lastGame:null, wasHomeLastGame:null, gamesIn4:0, gamesIn6:0, recentAltitudeVisit:false, prevTipDatetime:null };

  const last = played[0];
  const [ty,tm,td] = targetDate.split('-').map(Number);
  const [ly,lm,ld] = last.date.split('-').map(Number);
  const diffDays = Math.round((Date.UTC(ty,tm-1,td) - Date.UTC(ly,lm-1,ld)) / 86400000);
  const daysRest = Math.max(0, diffDays - 1);
  const wasHome = last.home_team.id === teamId;
  const prevArena = last.home_team.abbreviation;

  const targetMs = Date.UTC(ty,tm-1,td);
  const gamesIn3 = played.filter(g => { const [gy,gm,gd]=g.date.split('-').map(Number); const diff=Math.round((targetMs-Date.UTC(gy,gm-1,gd))/86400000); return diff>=1&&diff<=3; }).length;
  const gamesIn5 = played.filter(g => { const [gy,gm,gd]=g.date.split('-').map(Number); const diff=Math.round((targetMs-Date.UTC(gy,gm-1,gd))/86400000); return diff>=1&&diff<=5; }).length;

  const recentAltitudeVisit = played.some(g => {
    const [gy,gm,gd]=g.date.split('-').map(Number);
    const diff=Math.round((targetMs-Date.UTC(gy,gm-1,gd))/86400000);
    if(diff<1||diff>7) return false;
    return ALTITUDE_TEAMS.has(g.home_team.abbreviation);
  });

  return { daysRest, prevLocation:prevArena, lastGame:last, wasHomeLastGame:wasHome, gamesIn4:gamesIn3+1, gamesIn6:gamesIn5+1, recentAltitudeVisit, prevTipDatetime: last.datetime || null };
}

async function apiFetch(endpoint) {
  const res = await fetch(`${BASE_URL}${endpoint}`, { headers:{ Authorization: API_KEY } });
  if(!res.ok) throw new Error(`API ${res.status}: ${endpoint}`);
  return res.json();
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function dateRange(start, end) {
  const dates = [];
  const cur = new Date(start + 'T12:00:00Z');
  const fin = new Date(end + 'T12:00:00Z');
  while(cur <= fin) {
    dates.push(cur.toISOString().slice(0,10));
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return dates;
}

async function main() {
  const dates = dateRange(SEASON_START, SEASON_END);
  console.error(`Processing ${dates.length} dates from ${SEASON_START} to ${SEASON_END}...`);

  const teamRecords = {};  // { teamId: { wins: 0, losses: 0 } }

  function getWpct(teamId) {
    const r = teamRecords[teamId];
    if (!r) return null;
    const gp = r.wins + r.losses;
    return gp >= 15 ? r.wins / gp : null;  // null if < 15 games played (min threshold)
  }

  const flagged = [];
  let totalGames = 0;
  let datesWithGames = 0;
  let apiCalls = 0;
  let lastCallTime = 0;

  async function rateLimitedFetch(endpoint) {
    const now = Date.now();
    const elapsed = now - lastCallTime;
    if(elapsed < 20000) await sleep(20000 - elapsed);
    lastCallTime = Date.now();
    apiCalls++;
    return apiFetch(endpoint);
  }

  for(let i = 0; i < dates.length; i++) {
    const date = dates[i];

    let gamesResp;
    try {
      gamesResp = await rateLimitedFetch(`/games?dates[]=${date}&per_page=100`);
    } catch(e) {
      console.error(`Error fetching games for ${date}: ${e.message}`);
      continue;
    }

    const games = (gamesResp.data || []).filter(g => g.status === 'Final');
    if(!games.length) continue;

    datesWithGames++;
    totalGames += games.length;
    process.stderr.write(`\r[${i+1}/${dates.length}] ${date} — ${games.length} final games (${totalGames} total, ${flagged.length} flagged)`);

    const teamIds = [...new Set([...games.map(g=>g.home_team.id), ...games.map(g=>g.visitor_team.id)])];
    const [y,m,d] = date.split('-').map(Number);
    const endDt = new Date(y,m-1,d-1,12);
    const startDt = new Date(y,m-1,d-21,12);
    const endStr = endDt.toLocaleDateString('en-CA');
    const startStr = startDt.toLocaleDateString('en-CA');
    const teamParam = teamIds.map(id=>`team_ids[]=${id}`).join('&');

    let history = [];
    try {
      const histResp = await rateLimitedFetch(`/games?${teamParam}&start_date=${startStr}&end_date=${endStr}&per_page=100`);
      history = histResp.data || [];
      let cursor = histResp.meta?.next_cursor;
      while(cursor && history.length < 200) {
        const page = await rateLimitedFetch(`/games?${teamParam}&start_date=${startStr}&end_date=${endStr}&per_page=100&cursor=${cursor}`);
        history = history.concat(page.data || []);
        cursor = page.meta?.next_cursor;
      }
    } catch(e) {
      console.error(`\nError fetching history for ${date}: ${e.message}`);
    }

    for(const game of games) {
      const away = game.visitor_team.abbreviation;
      const home = game.home_team.abbreviation;
      const tipET = parseTipET(game.datetime);

      const awayRest = calcRest(history, game.visitor_team.id, date);
      const homeRest = calcRest(history, game.home_team.id, date);

      const gameDate = new Date(game.datetime || date + 'T19:00:00Z');

      const awayF = analyzeFatigue(away, false, awayRest.daysRest, awayRest.prevLocation, home, tipET, awayRest.wasHomeLastGame, awayRest.gamesIn4, awayRest.gamesIn6, awayRest.recentAltitudeVisit, awayRest.prevTipDatetime, gameDate);
      const homeF = analyzeFatigue(home, true, homeRest.daysRest, homeRest.prevLocation, home, tipET, homeRest.wasHomeLastGame, homeRest.gamesIn4, homeRest.gamesIn6, homeRest.recentAltitudeVisit, homeRest.prevTipDatetime, gameDate);

      const maxScore = Math.max(awayF.score, homeF.score);
      if(maxScore < FLAG_THRESHOLD) continue;

      const flaggedTeam = awayF.score >= homeF.score ? away : home;
      const flaggedScore = Math.max(awayF.score, homeF.score);
      const edgeSide = awayF.score > homeF.score ? 'HOME EDGE' : awayF.score < homeF.score ? 'AWAY EDGE' : 'EVEN';

      const edgeTeamId = edgeSide === 'HOME EDGE'
        ? game.home_team.id
        : edgeSide === 'AWAY EDGE'
          ? game.visitor_team.id
          : null;
      const edgeTeamWpct = edgeTeamId ? getWpct(edgeTeamId) : null;

      flagged.push({
        date,
        matchup: `${away} @ ${home}`,
        away, home,
        awayScore: awayF.score,
        homeScore: homeF.score,
        maxScore: flaggedScore,
        flaggedTeam,
        awayScenario: awayF.scenario,
        homeScenario: homeF.scenario,
        awayDaysRest: awayRest.daysRest,
        homeDaysRest: homeRest.daysRest,
        awaySleep: awayF.effectiveSleep ?? '',
        homeSleep: homeF.effectiveSleep ?? '',
        awayDetail: awayF.detail,
        homeDetail: homeF.detail,
        edgeSide,
        edgeTeamWpct: edgeTeamWpct !== null ? edgeTeamWpct.toFixed(3) : '',
        coversUrl: `https://www.covers.com/sports/nba/matchups?selectedDate=${date}`,
      });
    }

    // Update running W-L records AFTER processing this date's games
    for (const game of games) {
      if (game.status !== 'Final') continue;
      const homeId = game.home_team.id;
      const awayId = game.visitor_team.id;
      if (!teamRecords[homeId]) teamRecords[homeId] = { wins: 0, losses: 0 };
      if (!teamRecords[awayId]) teamRecords[awayId] = { wins: 0, losses: 0 };
      if (game.home_team_score > game.visitor_team_score) {
        teamRecords[homeId].wins++;
        teamRecords[awayId].losses++;
      } else {
        teamRecords[awayId].wins++;
        teamRecords[homeId].losses++;
      }
    }
  }

  console.error(`\n\nDone. ${totalGames} games across ${datesWithGames} dates. ${flagged.length} flagged games (score >= ${FLAG_THRESHOLD}).`);
  console.error(`Total API calls: ${apiCalls}`);

  flagged.sort((a,b) => a.date.localeCompare(b.date) || b.maxScore - a.maxScore);

  const header = ['Date','Matchup','Away','Home','Away Fatigue','Home Fatigue','Max Fatigue','Flagged Team','Edge Side','Away Scenario','Home Scenario','Away Days Rest','Home Days Rest','Away Est Sleep','Home Est Sleep','Away Detail','Home Detail','Edge Team Wpct','Covers URL'];
  const rows = flagged.map(f => [
    f.date, f.matchup, f.away, f.home,
    f.awayScore, f.homeScore, f.maxScore,
    f.flaggedTeam, f.edgeSide,
    f.awayScenario, f.homeScenario,
    f.awayDaysRest, f.homeDaysRest,
    f.awaySleep, f.homeSleep,
    `"${f.awayDetail}"`, `"${f.homeDetail}"`,
    f.edgeTeamWpct,
    f.coversUrl,
  ]);

  console.log(header.join(','));
  rows.forEach(r => console.log(r.join(',')));
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
