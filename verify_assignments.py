#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import Kecelakaan, SegmenJalan, AnalisisZScore

print("\n" + "="*80)
print("VERIFICATION: ACCIDENTS ASSIGNED TO SEGMENTS")
print("="*80 + "\n")

# Check all accidents
kecelakaan_list = Kecelakaan.objects.select_related('segmen_jalan').all()
print(f"Total accidents: {kecelakaan_list.count()}\n")

for kec in kecelakaan_list:
    print(f"Kecelakaan {kec.id}:")
    print(f"  Tanggal: {kec.tanggal}")
    print(f"  Lokasi: ({kec.latitude}, {kec.longitude})")
    
    if kec.segmen_jalan:
        segmen = kec.segmen_jalan
        print(f"  ✅ Assigned to: {segmen.nama_segmen} (Ruas: {segmen.ruas_jalan.nama_ruas})")
        print(f"     KM {segmen.km_awal} - {segmen.km_akhir}")
        
        # Check z-score for this segment
        zscore = AnalisisZScore.objects.filter(
            segmen_jalan=segmen,
            tahun=kec.tanggal.year
        ).first()
        
        if zscore:
            print(f"     Z-Score: {zscore.nilai_zscore} ({zscore.kategori})")
        else:
            print(f"     ⚠ No Z-Score found for this segment")
    else:
        print(f"  ❌ Not assigned to any segment")
    
    print()

print("="*80)
print("SEGMENT Z-SCORES FOR YEAR 2026")
print("="*80 + "\n")

# Show all segments and their z-scores
segments = SegmenJalan.objects.select_related('ruas_jalan').all()
for segmen in segments:
    print(f"{segmen.nama_segmen} (Ruas: {segmen.ruas_jalan.nama_ruas}):")
    
    # Count accidents
    accident_count = Kecelakaan.objects.filter(segmen_jalan=segmen, tanggal__year=2026).count()
    print(f"  Accidents in 2026: {accident_count}")
    
    # Get z-score
    zscore = AnalisisZScore.objects.filter(segmen_jalan=segmen, tahun=2026).first()
    if zscore:
        print(f"  Z-Score: {zscore.nilai_zscore} ({zscore.kategori}) - {zscore.get_kategori_display_color()}")
    else:
        print(f"  No Z-Score calculated")
    
    print()

print("="*80)
