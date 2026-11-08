"""UTM grid assignment and radius-based spatial eligibility."""
import math,re

PATTERN=re.compile(r"(?P<zone>\d{1,2})(?P<hem>[NS])_E(?P<e>\d+)_N(?P<n>\d+)(?:_S(?P<size>\d+))?")

def grid_id(longitude,latitude,size_m,zone=None):
    from pyproj import Transformer
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -180<=longitude<=180 or not -80<=latitude<=84:
        raise ValueError("Coordinates must be within the UTM domain")
    if size_m not in (1000,10000):raise ValueError("Grid size must be 1000 or 10000 m")
    zone=zone or min(60,max(1,int((longitude+180)//6)+1))
    if not 1<=zone<=60:raise ValueError("UTM zone must be 1..60")
    hem="N" if latitude>=0 else "S"
    e,n=Transformer.from_crs(4326,(32600 if hem=="N" else 32700)+zone,always_xy=True).transform(longitude,latitude)
    # Snap floating-point projection noise only at a metric grid boundary.
    e=round(e) if abs(e-round(e))<1e-6 else e
    n=round(n) if abs(n-round(n))<1e-6 else n
    key=f"{zone}{hem}_E{math.floor(e/size_m)*size_m}_N{math.floor(n/size_m)*size_m}"
    return key+("_S1000" if size_m==1000 else "")

def parse_grid(key):
    m=PATTERN.fullmatch(key)
    if not m:raise ValueError(f"Invalid UTM grid identifier: {key}")
    d=m.groupdict();zone=int(d['zone']);size=int(d['size'] or 10000)
    if not 1<=zone<=60 or size not in (1000,10000):raise ValueError("Invalid UTM zone or size")
    return zone,d['hem'],int(d['e']),int(d['n']),size

def parent_grid(key):
    z,h,e,n,_=parse_grid(key)
    return f"{z}{h}_E{e//10000*10000}_N{n//10000*10000}"

def grid_center(key):
    from pyproj import Transformer
    z,h,e,n,size=parse_grid(key)
    lon,lat=Transformer.from_crs((32600 if h=="N" else 32700)+z,4326,always_xy=True).transform(e+size/2,n+size/2)
    return {"longitude":lon,"latitude":lat}

def eligible_scales(radius_km):
    if not math.isfinite(radius_km) or radius_km<0:raise ValueError("Invalid location radius")
    return (1,10) if radius_km<=.5 else (10,) if radius_km<=5 else ()

def assign_location(geolocation):
    """Keep low-precision records at their supplied community identifier."""
    if not geolocation:return []
    radius=geolocation['radius_km'];scales=eligible_scales(radius)
    if not scales:
        return [{"scale_km":None,"grid_id":geolocation['community_id'],"radius_km":radius}] if geolocation.get('community_id') else []
    return [{"scale_km":s,"grid_id":grid_id(geolocation['longitude'],geolocation['latitude'],s*1000,geolocation.get('utm_zone')),
             "radius_km":radius} for s in scales]
