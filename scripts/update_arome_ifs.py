#!/usr/bin/env python3
"""Paquets officiels AROME-IFS 0,025° -> contrat départemental v3 partagé."""
from __future__ import annotations
import argparse, concurrent.futures, json, logging, re, tempfile, time
import urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
import schema_v3 as schema

DATASET='https://www.data.gouv.fr/api/1/datasets/6a3294c7190dd2ab81bef620/'
SOURCE_PAGE='https://www.data.gouv.fr/datasets/paquets-arome-ifs-resolution-0-025deg'
VERSION='1.0.0'
PATTERN=re.compile(r'^aromeifs__0025__(SP1|SP2)__(\d{2})H(\d{2})H__(.+)\.grib2$')
BLOCKS=[(0,6)]+[(s,min(s+5,51)) for s in range(7,52,6)]
FIELDS={
 '2t':('temperature_k',('K',),'heightAboveGround',2),
 '2r':('humidity_pct',('%',),'heightAboveGround',2),
 '10u':('wind_u_ms',('m s**-1',),'heightAboveGround',10),
 '10v':('wind_v_ms',('m s**-1',),'heightAboveGround',10),
 'max_i10fg':('gust_speed_ms',('m s**-1',),'heightAboveGround',10),
 'tp':('precipitation_total_mm',('kg m**-2',),'surface',0),
 'tsnowp':('snow_total_mm',('kg m**-2',),'surface',0),
 'tgrp':('graupel_total_mm',('kg m**-2',),'surface',0),
 '2d':('dewpoint_k',('K',),'heightAboveGround',2),
 'sp':('surface_pressure_pa',('Pa',),'surface',0),
 'prmsl':('sea_pressure_pa',('Pa',),'meanSea',0),
 'lcc':('cloud_low_pct',('%',),'surface',0),
 'mcc':('cloud_mid_pct',('%',),'surface',0),
 'hcc':('cloud_high_pct',('%',),'surface',0),
 'h':('altitude_m',('m',),'surface',0),
 'CAPE_INS':('cape_jkg',('m**2 s**-2','J kg**-1'),'unknown',0),
}

def get(url):
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AlertesMeteo-AROME-IFS/1.0'}),timeout=120) as r:return r.read()
  except Exception:
   if attempt==2:raise
   time.sleep(2**(attempt+1))

def select_resources(resources):
 runs={}
 for resource in resources:
  match=PATTERN.fullmatch(resource.get('title',''))
  if not match:continue
  group,start,end,run=match.groups(); start,end=int(start),int(end)
  u=urlparse(resource['url'])
  if u.scheme!='https' or u.hostname!='meteofrance-pnt.s3.rbx.io.cloud.ovh.net' or '/aromeifs/0025/' not in u.path:raise ValueError('Source différente de AROME-IFS')
  key=(group,start,end)
  if key in runs.setdefault(run,{}):raise ValueError('Paquet en double')
  runs[run][key]=resource
 required={(g,a,b) for g in ('SP1','SP2') for a,b in BLOCKS}
 for run in sorted(runs,reverse=True):
  if required.issubset(runs[run]):return run,{k:runs[run][k] for k in sorted(required)}
 raise ValueError('Catalogue AROME-IFS incomplet ou en cours de publication : dernières données conservées.')

def step_hours(value):
 m=re.fullmatch(r'(\d+(?:\.\d+)?)([smhd]?)',str(value).lower())
 if not m:raise ValueError('Unité de temps GRIB inconnue')
 h=float(m[1])*{'':1,'s':1/3600,'m':1/60,'h':1,'d':24}[m[2]]
 if not h.is_integer():raise ValueError('Échéance non horaire')
 return int(h)

def messages(path):
 with Path(path).open('rb') as f:
  while head:=f.read(16):
   if len(head)!=16 or head[:4]!=b'GRIB' or head[7]!=2:raise ValueError('Paquet GRIB2 invalide')
   length=int.from_bytes(head[8:16],'big')
   if not 20<=length<=64*1024*1024:raise ValueError('Taille de message GRIB inattendue')
   body=f.read(length-16)
   if len(body)!=length-16 or body[-4:]!=b'7777':raise ValueError('GRIB tronqué')
   yield head+body

def decode_packet(path,run,catalog):
 from eccodes import codes_new_from_message,codes_get,codes_get_double_elements,codes_release
 expected=datetime.fromisoformat(run.replace('Z','+00:00'))
 output={}
 for message in messages(path):
  g=codes_new_from_message(message)
  try:
   short=str(codes_get(g,'shortName'));field=FIELDS.get(short)
   if not field:continue
   name,units,level_type,level=field
   if str(codes_get(g,'typeOfLevel'))!=level_type or int(codes_get(g,'level'))!=level:continue
   if str(codes_get(g,'units')) not in units:raise ValueError(f'Unité inattendue : {short}')
   actual=datetime.strptime(f"{codes_get(g,'dataDate')}{int(codes_get(g,'dataTime')):04d}",'%Y%m%d%H%M').replace(tzinfo=timezone.utc)
   if actual!=expected:raise ValueError('Mélange de calculs météo')
   step=step_hours(codes_get(g,'endStep'));start=step_hours(codes_get(g,'startStep'))
   if not 0<=step<=51:raise ValueError('Échéance hors du contrat')
   if name in ('precipitation_total_mm','snow_total_mm','graupel_total_mm') and start!=0:raise ValueError('Cumul ne partant pas du calcul')
   if name=='gust_speed_ms' and start!=step-1:raise ValueError('Rafale non horaire')
   checks={'gridType':'regular_ll','Ni':1121,'Nj':717,'iScansNegatively':0,'jScansPositively':0,'jPointsAreConsecutive':0,'alternativeRowScanning':0}
   if any(codes_get(g,k)!=v for k,v in checks.items()):raise ValueError('Grille AROME-IFS inattendue')
   for k,target in [('latitudeOfFirstGridPointInDegrees',55.4),('longitudeOfFirstGridPointInDegrees',-12.),('iDirectionIncrementInDegrees',.025),('jDirectionIncrementInDegrees',.025)]:
    value=float(codes_get(g,k));value=(value+180)%360-180 if 'longitude' in k else value
    if abs(value-target)>1e-6:raise ValueError('Géographie de grille incohérente')
   values=np.asarray(codes_get_double_elements(g,'values',catalog.model_indexes),dtype=float)
   missing=float(codes_get(g,'missingValue'))
   values[~np.isfinite(values)|(np.abs(values)>1e20)|np.isclose(values,missing,rtol=0,atol=1e-9)]=np.nan
   if name in output.setdefault(step,{}):raise ValueError('Champ en double pour une échéance')
   output[step][name]=values
  finally:codes_release(g)
 return output

def fetch_packet(resource,key,run,catalog):
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'packet.grib2'
  payload=get(resource['url'])
  if resource.get('filesize') and len(payload)!=resource['filesize']:raise ValueError('Téléchargement incomplet')
  path.write_bytes(payload);del payload
  fields=decode_packet(path,run,catalog)
  if any(not key[1]<=step<=key[2] for step in fields):raise ValueError('Échéance différente du titre du paquet')
  return fields

def transform(raw,altitude,previous,lead):
 # Same 33-column contract and diagnostic conventions as the other AROME module.
 data,state=schema.transform_step(raw,altitude,previous,lead)
 if 'sea_pressure_pa' in raw:data['pressure_hpa']=schema.rounded(raw['sea_pressure_pa']/100,0)
 if 'dewpoint_k' in raw:data['dewpoint_c']=schema.rounded(raw['dewpoint_k']-273.15,1)
 # These columns exist in the contract but the corresponding fields are absent from these packets.
 shape=altitude.shape
 data['reflectivity_dbz']=np.full(shape,np.nan)
 data['visibility_km']=np.full(shape,np.nan)
 for name in ['lightning_score','hail_risk_code','convective_precipitation_mm','storm_type_code']:
  data[name]=np.full(shape,np.nan)
 data['thunder_risk_code']=np.where(np.isfinite(raw.get('cape_jkg',np.full(shape,np.nan))),data['thunder_risk_code'],np.nan)
 return data,state

def validate_product(root):
 reference=json.loads((Path(__file__).resolve().parents[1]/'tests/reference-schema.json').read_text())
 index=json.loads((root/'index.json').read_text())
 count=0
 for path in sorted((root/'departements').glob('*.json')):
  data=json.loads(path.read_text())
  assert data['schema_version']==3
  assert data['columns']=={k:reference[k] for k in ['points','communes','values']}
  assert len(data['forecast'])==52
  assert all(len(p)==4 for p in data['points'])
  assert all(len(c)==7 and isinstance(c[6],int) and 0<=c[6]<len(data['points']) for c in data['communes'])
  for hour,(date,rows) in enumerate(data['forecast']):
   assert len(rows)==len(data['points']) and all(len(row)==33 for row in rows)
   assert datetime.fromisoformat(date.replace('Z','+00:00'))==datetime.fromisoformat(index['model']['run_time'].replace('Z','+00:00'))+timedelta(hours=hour)
  count+=len(data['communes'])
 assert count==index['coverage']['communes'] and len(index['departments'])==96
 print('Contrat v3 vérifié :',count,'communes, 96 départements, 33 colonnes, 52 échéances (+0 à +51 h).',flush=True)

def build(catalog_path,output,repository,force=False):
 catalog=schema.load_catalog(Path(catalog_path))
 run,resources=select_resources(json.loads(get(DATASET))['resources'])
 run_date=datetime.fromisoformat(run.replace('Z','+00:00'))
 if datetime.now(timezone.utc)-run_date>timedelta(hours=30):raise ValueError('Calcul AROME-IFS trop ancien')
 try:current=json.loads(get(f'https://raw.githubusercontent.com/{repository}/data/index.json'))
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  current={}
 if not force and current.get('model',{}).get('run_time')==schema.iso_utc(run_date) and current.get('model',{}).get('pipeline_version')==VERSION:
  print('Calcul déjà publié, aucune modification.',flush=True);return
 print(f'AROME-IFS {run} : {len(resources)} paquets, {catalog.commune_count} communes.',flush=True)
 raw={i:{} for i in range(52)}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  jobs={pool.submit(fetch_packet,r,k,run,catalog):k for k,r in resources.items()}
  for job in concurrent.futures.as_completed(jobs):
   try: fields=job.result()
   except Exception:
    for pending in jobs:pending.cancel()
    raise
   for step,values in fields.items():
    if raw[step].keys() & values.keys():raise ValueError('Champ en double entre paquets')
    raw[step].update(values)
   print('Paquet validé :',jobs[job],flush=True)
 altitude=raw[0].get('altitude_m')
 if altitude is None:raise ValueError('Altitude du point de grille manquante')
 for department in catalog.departments.values():
  for p,global_id in zip(department.points,department.global_point_ids):p.append(schema.json_number(altitude[global_id],True))
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 state={};generated=schema.iso_utc(datetime.now(timezone.utc))
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);handles={code:(temp/f'{code}.ndjson').open('w',encoding='utf-8') for code in catalog.departments}
  try:
   for lead in range(52):
    required={'temperature_k','humidity_pct','wind_u_ms','wind_v_ms','surface_pressure_pa','cape_jkg'}
    if lead:required|={'precipitation_total_mm','snow_total_mm','graupel_total_mm','gust_speed_ms','cloud_low_pct','cloud_mid_pct','cloud_high_pct'}
    if not required.issubset(raw[lead]):raise ValueError(f'Champs manquants à +{lead} h : {required-raw[lead].keys()}')
    for key in ('precipitation_total_mm','snow_total_mm','graupel_total_mm'):
     if lead>1 and np.any(raw[lead][key]-raw[lead-1][key]<-.05):raise ValueError('Cumul décroissant')
    transformed,state=transform(raw[lead],altitude,state,lead)
    for code,department in catalog.departments.items():
     record=[schema.iso_utc(run_date+timedelta(hours=lead)),schema.compact_rows(transformed,department.global_point_ids)]
     json.dump(record,handles[code],ensure_ascii=False,separators=(',',':'),allow_nan=False);handles[code].write('\n')
  finally:
   for f in handles.values():f.close()
  department_index,total_bytes=schema.write_departments(output,temp,catalog,generated)
 index={'schema_version':3,'status':'ok','generated_at':generated,'model':{'name':'AROME-IFS 0,025°','provider':'Météo-France','dataset':'Paquets AROME IFS résolution 0,025°','domain':'France métropolitaine','resolution_degrees':.025,'resolution_km':2.5,'native_resolution_km':1.3,'forecast_hours_requested':51,'run_time':schema.iso_utc(run_date),'pipeline_version':VERSION,'catalog_version':catalog.version,'storm_diagnostics':True,'snow_diagnostics':True,'source_url':SOURCE_PAGE,'license':'Licence Ouverte 2.0'},'coverage':{'label':'France métropolitaine et Corse','communes':catalog.commune_count,'departments':96},'condition_codes':schema.CONDITION_CODES,'diagnostics':{'direct':['température','humidité','vent','rafales','précipitations','neige en équivalent eau','graupel','CAPE','pression','nuages par étage','altitude de grille'],'derived':['nébulosité totale estimée à partir des étages','risque orage indicatif à partir de CAPE','neige fraîche et tenue estimées'],'unavailable':['visibility_km','reflectivity_dbz','lightning_score','hail_risk_code','convective_precipitation_mm','storm_type_code'],'note':'null signifie indisponible, pas zéro. Les diagnostics ne sont pas des vigilances officielles. snow_depth_cm suit la convention historique du cumul estimé de neige fraîche, sans fonte ni tassement : ce n’est pas une hauteur de neige observée au sol.'},'search':{'provider':'API Découpage administratif','endpoint':'https://geo.api.gouv.fr/communes'},'maps':{'status':'unavailable'},'departments':department_index,'total_department_bytes':total_bytes}
 (output/'index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 validate_product(output)

if __name__=='__main__':
 logging.basicConfig(level=logging.INFO)
 p=argparse.ArgumentParser();p.add_argument('--catalog',default='config/communes-france.json');p.add_argument('--output-dir',default='build/national');p.add_argument('--repository',default='alertesmeteo-hub/AROME-IFS-2.5-km');p.add_argument('--force',action='store_true')
 a=p.parse_args();build(a.catalog,a.output_dir,a.repository,a.force)
