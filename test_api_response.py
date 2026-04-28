#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import SegmenJalan, AnalisisZScore, Kecelakaan
from django.utils import timezone
import json

print("\n" + "="*80)
print("API RESPONSE SIMULATION - TAHUN 2026")
print("="*80)

tahun = 2026

# Check Z-Scores exist
zscore_count = AnalisisZScore.objects.filter(tahun=tahun).count()
print(f"\nZ-Score records for {tahun}: {zscore_count}")

if zscore_count == 0:
    print(f"⚠️ No Z-Scores found! Attempting to auto-calculate...")
    try:
        AnalisisZScore.calculate_zscore(tahun)
        zscore_count = AnalisisZScore.objects.filter(tahun=tahun).count()
        print(f"✓ Auto-calculated. Now have {zscore_count} Z-Score records")
    except Exception as e:
        print(f"❌ Failed to calculate: {e}")

segmen_list = SegmenJalan.objects.select_related('ruas_jalan').all()
print(f"\nProcessing {segmen_list.count()} segments...")

features = []
line_count = 0
marker_count = 0

for segmen in segmen_list[:3]:  # Just first 3 for diagnostic
    print(f"\n--- Segment {segmen.id}: {segmen.nama_segmen} ---")
    
    # Count accidents
    accident_count = Kecelakaan.objects.filter(
        segmen_jalan=segmen,
        tanggal__year=tahun
    ).count()
    print(f"Accidents in {tahun}: {accident_count}")
    
    # Get Z-Score
    try:
        analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
        kategori = analisis.kategori
        zscore = float(analisis.nilai_zscore)
        color = analisis.get_kategori_display_color()
        print(f"Z-Score: {zscore} ({kategori}) - Color: {color}")
    except AnalisisZScore.DoesNotExist:
        if accident_count == 0:
            kategori = 'aman'
            zscore = -2.0
            color = '#1976d2'
            print(f"No Z-Score but no accidents → AMAN (blue)")
        else:
            kategori = 'unknown'
            zscore = 0
            color = '#999999'
            print(f"No Z-Score and has accidents → UNKNOWN (gray)")
    
    # Parse geometry
    geometry = None
    if segmen.geometry:
        try:
            geometry = json.loads(segmen.geometry)
            print(f"✓ Parsed stored geometry: {geometry.get('type')}")
            coords = geometry.get('coordinates', [])
            print(f"  Coordinates: {len(coords)} item(s)")
            if coords and len(coords) > 0:
                if geometry.get('type') == 'MultiLineString':
                    print(f"    First line has {len(coords[0])} points")
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            geometry = None
    
    # Test fallback
    if not geometry and segmen.lat_awal and segmen.lon_awal:
        geometry = {
            'type': 'LineString',
            'coordinates': [
                [float(segmen.lon_awal), float(segmen.lat_awal)],
                [float(segmen.lon_akhir), float(segmen.lat_akhir)]
            ]
        }
        print(f"✓ Using fallback geometry from lat/lon")
    
    if geometry:
        print(f"✓ GEOMETRY READY - should be rendered as line feature")
        line_count += 1
        marker_count += 1
    else:
        print(f"❌ NO GEOMETRY - feature skipped")

print(f"\n{'='*80}")
print(f"SUMMARY: {line_count} lines, {marker_count} markers should render")
print(f"{'='*80}\n")
