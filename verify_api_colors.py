#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import SegmenJalan, AnalisisZScore, Kecelakaan
import json

print("\n" + "="*80)
print("API GEOJSON RESPONSE VERIFICATION - YEAR 2026")
print("="*80 + "\n")

segmen_list = SegmenJalan.objects.select_related('ruas_jalan').all()

print(f"Total segments: {segmen_list.count()}\n")

for segmen in segmen_list[:5]:  # First 5 segments
    print(f"--- Segment: {segmen.nama_segmen} ---")
    print(f"Ruas: {segmen.ruas_jalan.nama_ruas}")
    print(f"KM: {segmen.km_awal} - {segmen.km_akhir}")
    
    # Count accidents
    accident_count = Kecelakaan.objects.filter(
        segmen_jalan=segmen,
        tanggal__year=2026
    ).count()
    print(f"Accidents in 2026: {accident_count}")
    
    # Get Z-Score
    try:
        analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=2026)
        kategori = analisis.kategori
        zscore = float(analisis.nilai_zscore)
        color = analisis.get_kategori_display_color()
        
        # Determine which branch the API will take
        if analisis:
            status = f"✅ Has Z-Score"
        else:
            status = "⚠ No Z-Score"
        
        print(f"Z-Score: {zscore} ({kategori})")
        print(f"Color (Hex): {color}")
        print(f"Color (Readable): {kategori.replace('_', ' ').title()}")
        print(f"API Branch: {status}")
        
    except AnalisisZScore.DoesNotExist:
        # This segment doesn't have z-score
        if accident_count == 0:
            kategori = 'aman'
            color = '#1976d2'
            zscore = -2.0
            status = "Blue (Safe - No Accidents)"
        else:
            kategori = 'unknown'
            color = '#999999'
            zscore = 0
            status = "Gray (Has Accidents but No Z-Score)"
        
        print(f"Z-Score: {zscore} ({kategori})")
        print(f"Color (Hex): {color}")
        print(f"API Branch: Fallback - {status}")
    
    print()

print("="*80)
print("COLOR MAPPING REFERENCE")
print("="*80)
print("""
#d32f2f  → Sangat Tinggi  (Z > 1.5)     → RED
#f57c00  → Tinggi         (0.5 < Z ≤ 1.5) → ORANGE
#fbc02d  → Sedang         (-0.5 < Z ≤ 0.5) → YELLOW
#7cb342  → Rendah         (-1.5 < Z ≤ -0.5) → GREEN
#388e3c  → Sangat Rendah  (Z ≤ -1.5)    → DARK GREEN
#1976d2  → Aman           (No Accidents)  → BLUE
""")
print("="*80 + "\n")
