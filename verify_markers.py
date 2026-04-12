#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import SegmenJalan
import json

print("\n" + "="*80)
print("MARKER PLACEMENT VERIFICATION")
print("="*80)

segments = SegmenJalan.objects.select_related('ruas_jalan').all()[:3]

for segmen in segments:
    print(f"\n--- Segment: {segmen.nama_segmen} (Ruas: {segmen.ruas_jalan.nama_ruas}) ---")
    print(f"KM Range: {segmen.km_awal} - {segmen.km_akhir}")
    
    if segmen.geometry:
        try:
            geom = json.loads(segmen.geometry)
            if geom.get('type') == 'MultiLineString':
                coords = []
                for line in geom.get('coordinates', []):
                    coords.extend(line)
            else:
                coords = geom.get('coordinates', [])
            
            if coords:
                print(f"Total coordinates in geometry: {len(coords)}")
                print(f"  START point (marker awal): {coords[0]}")
                print(f"  END point (marker akhir): {coords[-1]}")
                print(f"  Lat/Lon in DB - awal: ({segmen.lat_awal}, {segmen.lon_awal})")
                print(f"  Lat/Lon in DB - akhir: ({segmen.lat_akhir}, {segmen.lon_akhir})")
                
                # Check if coordinates match
                if coords[0] and coords[-1]:
                    geom_lon_awal, geom_lat_awal = coords[0]
                    geom_lon_akhir, geom_lat_akhir = coords[-1]
                    print(f"  ✓ Markers akan ditempatkan di: [{geom_lon_awal}, {geom_lat_awal}] dan [{geom_lon_akhir}, {geom_lat_akhir}]")
        except Exception as e:
            print(f"  Error: {e}")

print("\n" + "="*80)
