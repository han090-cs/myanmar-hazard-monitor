#!/usr/bin/env python3
"""Fetch real, source-attributed disaster observations for Myanmar.

Sources:
- USGS earthquake catalog (public GeoJSON; no key)
- GDACS public RSS feed (global alerts filtered to Myanmar / nearby Bay of Bengal)
- NASA FIRMS VIIRS active-fire API (optional; requires NASA_FIRMS_MAP_KEY secret)

This creates observed/reported events, not a model that predicts earthquakes or confirms ground impact.
"""
from __future__ import annotations
import argparse, csv, io, json, logging, os, re, hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'disaster_events.json'
USER_AGENT = 'MyanmarHazardMonitor/2.1 (open-data humanitarian monitor)'
TIMEOUT = 25
# Geographic envelope intentionally includes Myanmar and the immediate Bay of Bengal approach.
BBOX = (92.0, 9.0, 102.0, 29.5)  # west, south, east, north
LOG = logging.getLogger('disaster-events')
SOURCES = {
  'usgs': {'name':'USGS Earthquake Catalog', 'url':'https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php', 'type':'observed'},
  'gdacs': {'name':'Global Disaster Alert and Coordination System (GDACS)', 'url':'https://www.gdacs.org/xml/rss.xml', 'type':'reported_alert'},
  'firms': {'name':'NASA FIRMS VIIRS active-fire detections', 'url':'https://firms.modaps.eosdis.nasa.gov/active_fire/', 'type':'satellite_detection'},
  'weather_forecast': {'name':'Open-Meteo forecast-based hazard screening', 'url':'https://open-meteo.com/en/docs', 'type':'model_forecast_screening'}
}
WEATHER_API = 'https://api.open-meteo.com/v1/forecast'
WEATHER_CITIES = [
  ('Yangon','ရန်ကုန်',16.8661,96.1951),('Mandalay','မန္တလေး',21.9588,96.0891),
  ('Nay Pyi Taw','နေပြည်တော်',19.7633,96.0785),('Taunggyi','တောင်ကြီး',20.7892,97.0378),
  ('Mawlamyine','မော်လမြိုင်',16.4905,97.6283),('Sittwe','စစ်တွေ',20.1500,92.9000),
  ('Pathein','ပုသိမ်',16.7792,94.7321),('Monywa','မုံရွာ',22.1086,95.1358),
  ('Myitkyina','မြစ်ကြီးနား',25.3833,97.4000),('Hpa-An','ဘားအံ',16.8890,97.6340),
  ('Dawei','ထားဝယ်',14.0823,98.1959),('Bago','ပဲခူး',17.3367,96.4797),
  ('Lashio','လားရှိုး',22.9359,97.7498),('Hakha','ဟားခါး',22.6500,93.6167),
  ('Kyaing Tong','ကျိုင်းတုံ',21.3000,99.6000),('Kawthoung','ကော့သောင်း',9.9824,98.5503),
  ('Magway','မကွေး',20.1496,94.9325),('Pyay','ပြည်',18.8240,95.2221),
  ('Hinthada','ဟင်္သာတ',17.6494,95.4571),('Kalay','ကလေး',23.1880,94.0629),
]


def now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def inside(lat: float, lon: float) -> bool:
  w,s,e,n = BBOX
  return s <= lat <= n and w <= lon <= e

def get(url: str, params: dict[str, Any] | None = None) -> requests.Response:
  r = requests.get(url, params=params, timeout=TIMEOUT, headers={'User-Agent':USER_AGENT})
  r.raise_for_status()
  return r

def fetch_usgs() -> list[dict[str, Any]]:
  end = datetime.now(timezone.utc)
  start = end - timedelta(days=30)
  payload = get('https://earthquake.usgs.gov/fdsnws/event/1/query', {
    'format':'geojson','starttime':start.strftime('%Y-%m-%d'),'endtime':end.strftime('%Y-%m-%dT%H:%M:%S'),
    'minlatitude':BBOX[1],'maxlatitude':BBOX[3],'minlongitude':BBOX[0],'maxlongitude':BBOX[2],
    'orderby':'time','limit':500
  }).json()
  out=[]
  for f in payload.get('features',[]):
    geom=f.get('geometry') or {}; c=geom.get('coordinates') or []
    p=f.get('properties') or {}
    if len(c)<2 or c[0] is None or c[1] is None: continue
    lon,lat=c[0],c[1]
    if not inside(float(lat),float(lon)): continue
    out.append({'id':'usgs:'+str(f.get('id') or ''),'kind':'earthquake','title':p.get('place') or 'Earthquake',
      'lat':float(lat),'lon':float(lon),'time_utc':datetime.fromtimestamp((p.get('time') or 0)/1000,timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
      'magnitude':p.get('mag'),'depth_km':c[2] if len(c)>2 else None,'severity':p.get('alert') or 'reported',
      'url':p.get('url') or SOURCES['usgs']['url'],'source':SOURCES['usgs']['name'],'status':'observed',
      'details':('Tsunami flag: yes' if p.get('tsunami') else 'Catalog event; check source for reviewed details.')})
  return out

def text_of(node: ET.Element, suffix: str) -> str | None:
  for el in node.iter():
    if el.tag.lower().endswith(suffix.lower()) and el.text:
      return ' '.join(el.text.split())
  return None

def fetch_gdacs() -> list[dict[str, Any]]:
  root=ET.fromstring(get(SOURCES['gdacs']['url']).content)
  out=[]
  for item in root.findall('.//item'):
    title=(item.findtext('title') or 'GDACS event').strip()
    desc=re.sub(r'<[^>]+>',' ',item.findtext('description') or '')
    desc=' '.join(desc.split())
    link=(item.findtext('link') or SOURCES['gdacs']['url']).strip()
    stamp=(item.findtext('pubDate') or '').strip()
    lat=lon=None
    # RSS commonly includes georss:point / geo:lat+geo:long or plain point.
    point=text_of(item,'point')
    if point:
      nums=re.findall(r'-?\d+(?:\.\d+)?',point)
      if len(nums)>=2:
        # GeoRSS point is lat lon; some feeds use lon,lat. Use geographic bounds to disambiguate.
        a,b=map(float,nums[:2])
        if inside(a,b): lat,lon=a,b
        elif inside(b,a): lat,lon=b,a
    if lat is None:
      la=text_of(item,'lat'); lo=text_of(item,'long') or text_of(item,'lon')
      try:
        if la and lo and inside(float(la),float(lo)): lat,lon=float(la),float(lo)
      except ValueError: pass
    nearby_text=bool(re.search(r'\b(myanmar|burma|bay of bengal|rakhine|andaman sea)\b',title+' '+desc,re.I))
    if lat is None and not nearby_text: continue
    # Don't assign fabricated coordinates to text-only events; they appear in list but not on map.
    out.append({'id':'gdacs:'+hashlib.sha1(link.encode('utf-8')).hexdigest()[:16],'kind':'disaster_alert','title':title[:240],
      'lat':lat,'lon':lon,'time_utc':stamp or None,'magnitude':None,'depth_km':None,'severity':'gdacs_alert',
      'url':link,'source':SOURCES['gdacs']['name'],'status':'reported','details':desc[:700]})
  return out

def fetch_firms() -> tuple[list[dict[str, Any]], str]:
  key=os.environ.get('NASA_FIRMS_MAP_KEY','').strip()
  if not key: return [], 'skipped_no_key'
  # VIIRS NOAA-20 near-real-time detections, last 1 day, Myanmar bounding box.
  url=f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}/1'
  r=get(url)
  rows=list(csv.DictReader(io.StringIO(r.text)))
  out=[]
  for i,row in enumerate(rows):
    try: lat,lon=float(row['latitude']),float(row['longitude'])
    except (ValueError,KeyError): continue
    if not inside(lat,lon): continue
    out.append({'id':'firms:'+str(row.get('acq_date',''))+':'+str(row.get('acq_time',''))+':'+str(i),
      'kind':'fire_detection','title':'Satellite active-fire detection','lat':lat,'lon':lon,
      'time_utc':(str(row.get('acq_date',''))+'T'+str(row.get('acq_time','0000')).zfill(4)[:2]+':'+str(row.get('acq_time','0000')).zfill(4)[2:4]+':00Z'),
      'magnitude':row.get('frp'),'depth_km':None,'severity':'satellite_detection','url':SOURCES['firms']['url'],
      'source':SOURCES['firms']['name'],'status':'detected','details':'Satellite detection only; not a confirmed ground fire report.'})
  return out, 'ok'

def fetch_weather_risk() -> list[dict[str, Any]]:
  """Create transparent forecast-screening notices, not official warnings.

  The thresholds are deliberately shown in each event. They are screening rules,
  not calibrated local impact thresholds and must never be presented as official alerts.
  """
  params = {
    'latitude': ','.join(str(x[2]) for x in WEATHER_CITIES),
    'longitude': ','.join(str(x[3]) for x in WEATHER_CITIES),
    'daily': 'temperature_2m_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,uv_index_max',
    'forecast_days': 3, 'timezone': 'UTC'
  }
  payload = get(WEATHER_API, params).json()
  locations = payload if isinstance(payload, list) else [payload]
  if len(locations) != len(WEATHER_CITIES):
    raise ValueError(f'Open-Meteo returned {len(locations)} locations; expected {len(WEATHER_CITIES)}')
  out: list[dict[str, Any]] = []
  for city, loc in zip(WEATHER_CITIES, locations):
    name, name_my, lat, lon = city
    daily = loc.get('daily') or {}
    dates = daily.get('time') or []
    arrays = {key: daily.get(key) or [] for key in ('temperature_2m_max','precipitation_sum','precipitation_probability_max','wind_speed_10m_max','uv_index_max')}
    for i, day in enumerate(dates):
      def val(key: str) -> float | None:
        values = arrays[key]
        try:
          raw = values[i]
          return float(raw) if raw is not None else None
        except (IndexError, TypeError, ValueError):
          return None
      temp, rain, prob, wind, uv = (val(k) for k in ('temperature_2m_max','precipitation_sum','precipitation_probability_max','wind_speed_10m_max','uv_index_max'))
      risks: list[tuple[str,str,str]] = []
      if rain is not None and rain >= 100:
        risks.append(('heavy_rain','severe',f'Daily precipitation forecast {rain:.1f} mm; screening threshold ≥100 mm/day.'))
      elif rain is not None and rain >= 50:
        risks.append(('heavy_rain','high',f'Daily precipitation forecast {rain:.1f} mm; screening threshold ≥50 mm/day.'))
      elif rain is not None and rain >= 25 and prob is not None and prob >= 60:
        risks.append(('heavy_rain','moderate',f'Daily precipitation forecast {rain:.1f} mm with {prob:.0f}% precipitation probability.'))
      if wind is not None and wind >= 90:
        risks.append(('strong_wind','severe',f'Maximum wind forecast {wind:.0f} km/h; screening threshold ≥90 km/h.'))
      elif wind is not None and wind >= 60:
        risks.append(('strong_wind','high',f'Maximum wind forecast {wind:.0f} km/h; screening threshold ≥60 km/h.'))
      elif wind is not None and wind >= 40:
        risks.append(('strong_wind','moderate',f'Maximum wind forecast {wind:.0f} km/h; screening threshold ≥40 km/h.'))
      if temp is not None and temp >= 43:
        risks.append(('extreme_heat','severe',f'Maximum temperature forecast {temp:.1f}°C; screening threshold ≥43°C.'))
      elif temp is not None and temp >= 40:
        risks.append(('extreme_heat','high',f'Maximum temperature forecast {temp:.1f}°C; screening threshold ≥40°C.'))
      elif temp is not None and temp >= 37:
        risks.append(('extreme_heat','moderate',f'Maximum temperature forecast {temp:.1f}°C; screening threshold ≥37°C.'))
      if uv is not None and uv >= 11:
        risks.append(('uv','high',f'Maximum UV index forecast {uv:.1f}; screening threshold ≥11.'))
      elif uv is not None and uv >= 8:
        risks.append(('uv','moderate',f'Maximum UV index forecast {uv:.1f}; screening threshold ≥8.'))
      for kind, level, details in risks:
        event_id = f'openmeteo:{name.lower().replace(" ","-")}:{day}:{kind}'
        title_en = {'heavy_rain':'Heavy rainfall possible','strong_wind':'Strong wind possible','extreme_heat':'Extreme heat screening','uv':'Very high UV screening'}[kind]
        title_my = {'heavy_rain':'မိုးသည်းထန်နိုင်ခြေ','strong_wind':'လေပြင်းတိုက်ခတ်နိုင်ခြေ','extreme_heat':'အပူလွန်ကဲနိုင်ခြေ','uv':'UV အညွှန်းမြင့်မားနိုင်ခြေ'}[kind]
        out.append({'id':event_id,'kind':'weather_risk','hazard_type':kind,'risk_level':level,
          'title':name,'city':name,'city_my':name_my,'risk_title_en':title_en,'risk_title_my':title_my, 'lat':lat,'lon':lon,
          'time_utc':f'{day}T00:00:00Z','forecast_date':day,'forecast_lead_days':i,
          'magnitude':None,'depth_km':None,'severity':level,'url':SOURCES['weather_forecast']['url'],
          'source':SOURCES['weather_forecast']['name'],'status':'forecast',
          'details':details+' Model-derived screening only; not an official warning. Check Myanmar DMH and local authorities.'})
  return out


def build() -> dict[str, Any]:
  events=[]; checks={}; successful=[]
  try:
    old=json.loads(OUT.read_text(encoding='utf-8'))
  except Exception:
    old={}
  old_events=old.get('events',[]) if isinstance(old,dict) else []
  for key, fn in [('usgs',fetch_usgs),('gdacs',fetch_gdacs),('weather_forecast',fetch_weather_risk)]:
    try:
      values=fn(); events.extend(values); successful.append(key); checks[key]={'status':'ok','count':len(values),'checked_utc':now_iso()}
    except Exception as e:
      LOG.warning('%s feed failed: %s',key,e)
      cached=[x for x in old_events if x.get('source') == SOURCES[key]['name']]
      events.extend(cached); checks[key]={'status':'error','message':str(e)[:240],'cached_count':len(cached),'checked_utc':now_iso()}
  try:
    values,status=fetch_firms(); events.extend(values)
    if status == 'ok': successful.append('firms')
    checks['firms']={'status':status,'count':len(values),'checked_utc':now_iso()}
  except Exception as e:
    LOG.warning('FIRMS failed: %s',e)
    cached=[x for x in old_events if x.get('source') == SOURCES['firms']['name']]
    events.extend(cached); checks['firms']={'status':'error','message':str(e)[:240],'cached_count':len(cached),'checked_utc':now_iso()}
  # De-duplicate and sort latest first; retain text-only GDACS alerts in the list.
  unique={e['id']:e for e in events}
  events=sorted(unique.values(),key=lambda x:x.get('time_utc') or '',reverse=True)
  return {'schema_version':1,'generated_utc':now_iso() if successful else old.get('generated_utc'),'checked_utc':now_iso(),'coverage':{'west':BBOX[0],'south':BBOX[1],'east':BBOX[2],'north':BBOX[3]},
    'source_checks':checks,'sources':SOURCES,'events':events,
    'disclaimer':'Live reported/observed events, not an exhaustive inventory or guaranteed forecast. Earthquakes cannot be predicted precisely. Fire detections require ground confirmation. Verify emergency instructions with Myanmar DMH and local authorities.'}

def selftest() -> None:
  assert inside(21.9,96.1) and not inside(35,110)
  assert len(WEATHER_CITIES) >= 15 and all(inside(lat,lon) for _,_,lat,lon in WEATHER_CITIES)
  sample={'features':[{'id':'test','geometry':{'coordinates':[96.1,21.9,10]},'properties':{'mag':4.2,'time':1760000000000,'place':'Myanmar','url':'https://example.org'}}]}
  f=sample['features'][0]; c=f['geometry']['coordinates']; assert inside(c[1],c[0]) and f['properties']['mag']==4.2
  # Mock the API response so thresholding is tested without network access.
  class FakeResponse:
    def __init__(self, payload: Any): self.payload = payload
    def json(self) -> Any: return self.payload
  daily = {'time':['2026-10-14','2026-10-15'], 'temperature_2m_max':[41.0,34.0],
           'precipitation_sum':[75.0,2.0], 'precipitation_probability_max':[80.0,20.0],
           'wind_speed_10m_max':[25.0,25.0], 'uv_index_max':[9.0,4.0]}
  fake = [{'daily':daily} for _ in WEATHER_CITIES]
  original_get = globals()['get']
  try:
    globals()['get'] = lambda url, params=None: FakeResponse(fake)
    screened = fetch_weather_risk()
  finally:
    globals()['get'] = original_get
  assert screened, 'Expected mocked high-rain/heat/UV screening events'
  assert all(e['kind']=='weather_risk' and e['status']=='forecast' and inside(e['lat'],e['lon']) for e in screened)
  assert any(e['hazard_type']=='heavy_rain' and e['risk_level']=='high' for e in screened)
  assert any(e['hazard_type']=='extreme_heat' and e['risk_level']=='high' for e in screened)
  print(f'disaster event self-test passed ({len(screened)} mocked forecast-screening events)')

def main() -> int:
  parser=argparse.ArgumentParser(); parser.add_argument('--selftest',action='store_true'); args=parser.parse_args()
  if args.selftest: selftest(); return 0
  payload=build(); OUT.parent.mkdir(parents=True,exist_ok=True)
  OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(f"Wrote {OUT.relative_to(ROOT)}: {len(payload['events'])} events; source checks={payload['source_checks']}")
  # Only fail if both primary public feeds failed, so optional FIRMS doesn't block updates.
  if all(payload['source_checks'].get(k,{}).get('status')=='error' for k in ('usgs','gdacs','weather_forecast')): return 1
  return 0
if __name__=='__main__': raise SystemExit(main())
