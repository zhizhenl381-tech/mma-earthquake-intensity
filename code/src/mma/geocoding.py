"""Offline place lookup and Google Maps geocoding for resolved post locations."""
from pathlib import Path
import csv,math,os

def distance_km(lat1,lon1,lat2,lon2):
    a=math.sin(math.radians(lat2-lat1)/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(math.radians(lon2-lon1)/2)**2
    return 2*6371*math.asin(min(1,math.sqrt(a)))

def lookup_place(name,table_path):
    with Path(table_path).open(encoding='utf-8-sig',newline='') as f:
        found=[r for r in csv.DictReader(f) if r['place_name'].casefold()==name.casefold()]
    if len(found)!=1:raise ValueError(f'Expected exactly one place match: {name}')
    r=found[0]
    return {'longitude':float(r['longitude']),'latitude':float(r['latitude']),
            'radius_km':float(r['radius_km']),'source':'place_table','place_name':name}

def google_geocode(query,api_key_env='GOOGLE_MAPS_API_KEY'):
    import httpx
    key=os.environ.get(api_key_env)
    if not key:raise ValueError(f'Set {api_key_env}')
    r=httpx.get('https://maps.googleapis.com/maps/api/geocode/json',params={'address':query,'key':key},timeout=60)
    r.raise_for_status();data=r.json()
    if data.get('status')!='OK' or len(data['results'])!=1:
        raise ValueError('Geocoding requires one unambiguous result')
    item=data['results'][0];g=item['geometry'];point=g['location'];box=g.get('bounds',g['viewport'])
    radius=max(distance_km(point['lat'],point['lng'],box[a]['lat'],box[b]['lng'])
               for a in ('northeast','southwest') for b in ('northeast','southwest'))
    return {'longitude':point['lng'],'latitude':point['lat'],'radius_km':radius,
            'source':'google_maps_bounds','place_id':item['place_id'],'formatted_address':item['formatted_address'],
            'raw_response':data}
