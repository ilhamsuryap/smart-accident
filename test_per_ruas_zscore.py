#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import AnalisisZScore, RekapSegmen

print("\n" + "="*80)
print("TESTING Z-SCORE CALCULATION - PER RUAS JALAN")
print("="*80)

# Recalculate for 2026
AnalisisZScore.calculate_zscore(tahun=2026)

# Verify results
print("\n" + "="*80)
print("VERIFICATION - Z-SCORE RESULTS")
print("="*80 + "\n")

from coreapp.models import SegmenJalan
from collections import defaultdict

zscore_by_ruas = defaultdict(list)

for segmen in SegmenJalan.objects.all():
    try:
        zscore = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=2026)
        rekap = RekapSegmen.objects.filter(segmen_jalan=segmen, periode_tahun=2026).first()
        ruas_nama = segmen.ruas_jalan.nama_ruas
        accident_count = rekap.jumlah_kecelakaan if rekap else 0
        
        zscore_by_ruas[ruas_nama].append({
            'segmen': segmen.nama_segmen,
            'accidents': accident_count,
            'zscore': zscore.nilai_zscore,
            'kategori': zscore.kategori,
            'color': zscore.get_kategori_display_color()
        })
    except AnalisisZScore.DoesNotExist:
        pass

for ruas_nama, zscore_data in sorted(zscore_by_ruas.items()):
    print(f"🛣️ RUAS: {ruas_nama}")
    for item in zscore_data:
        print(f"   {item['segmen']}: {item['accidents']} accidents → Z={float(item['zscore']):.3f} ({item['kategori']}) {item['color']}")
    print()

print("="*80)
