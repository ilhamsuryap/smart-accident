#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import SegmenJalan, AnalisisZScore
import json

print("\n" + "="*80)
print("SEGMENT DATA DIAGNOSTIC")
print("="*80)

segments = SegmenJalan.objects.select_related('ruas_jalan').all()
print(f"\nTotal segments in DB: {segments.count()}")

for i, segmen in enumerate(segments[:5], 1):
    print(f"\n--- Segment {i} (ID: {segmen.id}) ---")
    print(f"Nama: {segmen.nama_segmen}")
    print(f"Ruas: {segmen.ruas_jalan.nama_ruas}")
    print(f"KM: {segmen.km_awal} - {segmen.km_akhir}")
    
    # Check geometry
    print(f"Has stored geometry: {bool(segmen.geometry)}")
    if segmen.geometry:
        try:
            geom = json.loads(segmen.geometry)
            print(f"  Geometry type: {geom.get('type')}")
            print(f"  Coordinates count: {len(geom.get('coordinates', []))}")
        except Exception as e:
            print(f"  ERROR parsing geometry: {e}")
    
    # Check lat/lon
    print(f"Lat/Lon awal: {segmen.lat_awal}, {segmen.lon_awal}")
    print(f"Lat/Lon akhir: {segmen.lat_akhir}, {segmen.lon_akhir}")
    
    # Check parent geometry
    print(f"Parent (ruas_jalan) has geometry: {bool(segmen.ruas_jalan.geometry)}")
    
    # Check Z-Score
    zscore = AnalisisZScore.objects.filter(segmen_jalan=segmen).first()
    if zscore:
        print(f"Z-Score found: {zscore.nilai_zscore} ({zscore.kategori})")
    else:
        print(f"No Z-Score found for this segment")

print("\n" + "="*80)
