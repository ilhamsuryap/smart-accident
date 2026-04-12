#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import SegmenJalan, RekapSegmen, AnalisisZScore
from collections import defaultdict

print("\n" + "="*90)
print("DEMONSTRASI PERHITUNGAN Z-SCORE DENGAN INTERVAL DINAMIS")
print("(Sesuai Metodologi dari Gambar: Langkah a, b, c, d, e)")
print("="*90 + "\n")

tahun = 2026

for ruas in SegmenJalan.objects.all().values_list('ruas_jalan__id', 'ruas_jalan__nama_ruas').distinct():
    ruas_id, ruas_nama = ruas
    segments = SegmenJalan.objects.filter(ruas_jalan_id=ruas_id)
    
    # a. Hitung rata-rata jumlah kecelakaan
    rekap_list = RekapSegmen.objects.filter(periode_tahun=tahun, segmen_jalan__in=segments)
    
    total_accidents = sum([r.jumlah_kecelakaan for r in rekap_list])
    n_segments = len(rekap_list)
    x_bar = total_accidents / n_segments if n_segments > 0 else 0
    
    print(f"\n{'-'*90}")
    print(f"RUAS JALAN: {ruas_nama}")
    print(f"{'-'*90}")
    
    # Langkah a: Menghitung rata-rata jumlah kecelakaan
    print(f"\na. MENGHITUNG RATA-RATA JUMLAH KECELAKAAN (X_bar)")
    print(f"   X_bar = Sigma X_i / n")
    print(f"   X_bar = {total_accidents} / {n_segments} = {x_bar:.3f}")
    
    # Langkah b: Menghitung standar deviasi
    print(f"\nb. MENGHITUNG STANDAR DEVIASI (S)")
    variance_sum = sum([(r.jumlah_kecelakaan - x_bar)**2 for r in rekap_list])
    variance = variance_sum / n_segments if n_segments > 0 else 0
    stddev = variance ** 0.5
    print(f"   S = sqrt(Sigma(X_i - X_bar)^2 / n)")
    print(f"   S = sqrt({variance_sum:.3f} / {n_segments}) = sqrt({variance:.3f}) = {stddev:.3f}")
    
    # Langkah c: Menghitung Z-Score untuk setiap segmen
    print(f"\nc. MENGHITUNG Z-SCORE UNTUK SETIAP SEGMEN (Z_i = (X_i - X_bar) / S)")
    
    zscore_values = []
    for rekap in rekap_list:
        zscore = (rekap.jumlah_kecelakaan - x_bar) / (stddev if stddev != 0 else 1)
        zscore_values.append(zscore)
        print(f"   {rekap.segmen_jalan.nama_segmen}: ({rekap.jumlah_kecelakaan} - {x_bar:.3f}) / {stddev:.3f} = {zscore:.3f}")
    
    # Langkah d: Menghitung Interval (I)
    z_max = max(zscore_values)
    z_min = min(zscore_values)
    num_klasifikasi = 5
    interval = (z_max - z_min) / num_klasifikasi if z_max != z_min else 1
    
    print(f"\nd. MENGHITUNG NILAI INTERVAL (I)")
    print(f"   Z_max = {z_max:.3f}")
    print(f"   Z_min = {z_min:.3f}")
    print(f"   I = (Z_max - Z_min) / Sigma klasifikasi")
    print(f"   I = ({z_max:.3f} - ({z_min:.3f})) / {num_klasifikasi}")
    print(f"   I = {z_max - z_min:.3f} / {num_klasifikasi} = {interval:.3f}")
    
    # Langkah e: Klasifikasi berdasarkan interval
    print(f"\ne. TABEL KLASIFIKASI KERAWANAN (DENGAN INTERVAL DINAMIS)")
    t1 = z_min + (1 * interval)
    t2 = z_min + (2 * interval)
    t3 = z_min + (3 * interval)
    t4 = z_min + (4 * interval)
    
    print(f"   No  Nilai Z-Score              Keterangan")
    print(f"   {'-'*60}")
    print(f"   1   Z >= {t4:.3f}               Rawan Kecelakaan Sangat Besar")
    print(f"   2   {t3:.3f} <= Z < {t4:.3f}    Rawan Kecelakaan Besar")
    print(f"   3   {t2:.3f} <= Z < {t3:.3f}    Rawan Kecelakaan Sedang")
    print(f"   4   {t1:.3f} <= Z < {t2:.3f}    Rawan Kecelakaan Kecil")
    print(f"   5   Z < {t1:.3f}               Rawan Kecelakaan Sangat Kecil")
    
    # Hasil klasifikasi
    print(f"\nHASIL KLASIFIKASI SEGMEN:")
    print(f"   {'Segmen':<30} {'Accidents':<10} {'Z-Score':<12} {'Kategori':<20}")
    print(f"   {'-'*70}")
    
    for rekap in rekap_list:
        zscore = (rekap.jumlah_kecelakaan - x_bar) / (stddev if stddev != 0 else 1)
        
        if zscore >= t4:
            kategori = 'Sangat Tinggi'
        elif zscore >= t3:
            kategori = 'Tinggi'
        elif zscore >= t2:
            kategori = 'Sedang'
        elif zscore >= t1:
            kategori = 'Rendah'
        else:
            kategori = 'Sangat Rendah'
        
        print(f"   {rekap.segmen_jalan.nama_segmen:<30} {rekap.jumlah_kecelakaan:<10} {zscore:>10.3f}   {kategori:<20}")

print(f"\n{'='*90}\n")
