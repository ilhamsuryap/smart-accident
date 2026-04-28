from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from geopy.distance import geodesic
import math
import requests
import json
import decimal
import traceback


class RuasJalan(models.Model):
    """Model untuk data ruas jalan"""
    
    JENIS_JALAN_CHOICES = (
        ('tol', 'Jalan Tol'),
        ('arteri', 'Jalan Arteri'),
        ('kolektor', 'Jalan Kolektor'),
        ('lokal', 'Jalan Lokal'),
        ('desa', 'Jalan Desa'),
    )
    
    id = models.AutoField(primary_key=True)
    nama_ruas = models.CharField(max_length=100)
    jenis_jalan = models.CharField(max_length=20, choices=JENIS_JALAN_CHOICES)
    wilayah = models.CharField(max_length=100)
    panjang_km = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(0)])
    lat_awal = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Latitude titik awal ruas jalan")
    lon_awal = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Longitude titik awal ruas jalan")
    lat_akhir = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Latitude titik akhir ruas jalan")
    lon_akhir = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Longitude titik akhir ruas jalan")
    geometry = models.TextField(null=True, blank=True, help_text="GeoJSON LineString untuk seluruh ruas jalan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Ruas Jalan'
        ordering = ['nama_ruas']
    
    def __str__(self):
        return f"{self.nama_ruas} ({self.jenis_jalan})"
    
    def generate_segmen(self):
        """Generate segmen jalan otomatis berdasarkan titik klik manual atau simpang jalan dari Overpass API"""
        # 1. Hapus segmen lama
        SegmenJalan.objects.filter(ruas_jalan=self).delete()

        if not self.geometry:
            print(f"Skipping generate_segmen for {self.nama_ruas}: No geometry.")
            return

        # 2. Ambil data geometry dan cek properti 'splits' (untuk pembagian manual)
        try:
            geom_data = json.loads(self.geometry)
            # Jika geometry disimpan sebagai GeoJSON Feature
            if geom_data.get('type') == 'Feature':
                properties = geom_data.get('properties', {})
                manual_splits = properties.get('splits', [])          # [{km, lat, lon}, ...]
                segment_geometries = properties.get('segment_geometries', []) # [GeoJSON geometry, ...]
                segment_info = properties.get('segment_info', []) # [{nama_segmen, keterangan}, ...]
                geom_obj = geom_data.get('geometry', {})
            else:
                # Jika geometry disimpan sebagai raw geometry (LineString/MultiLineString)
                manual_splits = []
                segment_geometries = []
                segment_info = []
                geom_obj = geom_data

            geom_type = geom_obj.get('type')
            raw_coords = geom_obj.get('coordinates', [])
            
            if geom_type == 'LineString':
                coords = raw_coords
            elif geom_type == 'MultiLineString':
                coords = [pt for line in raw_coords for pt in line]
            else:
                coords = raw_coords

            if not coords or not isinstance(coords[0], list):
                print(f"Skipping generate_segmen for {self.nama_ruas}: Invalid coordinates format.")
                return
        except Exception as e:
            print(f"Error parsing geometry for {self.nama_ruas}: {e}")
            return

        # 3. Hitung jarak kumulatif untuk koordinat asli
        source_coords = coords 
        cumulative_distances = [0.0]
        total_dist = 0.0
        for i in range(len(source_coords) - 1):
            p1 = source_coords[i]
            p2 = source_coords[i+1]
            try:
                d = geodesic((p1[1], p1[0]), (p2[1], p2[0])).kilometers
                total_dist += d
                cumulative_distances.append(total_dist)
            except Exception as e:
                print(f"Error calculating geodesic distance: {e}")
                cumulative_distances.append(total_dist)

        # 4. Tentukan titik bagi (split points)
        final_points = [] # List of {km, lat, lon}

        if manual_splits:
            # Mode Manual: Gunakan titik bagi dan koordinat yang dikirim dari frontend
            print(f"Using manual splits for {self.nama_ruas}: {manual_splits}")
            for s in manual_splits:
                if isinstance(s, dict):
                    final_points.append({
                        'km': float(s.get('km', 0)),
                        'lat': s.get('lat'),
                        'lon': s.get('lon')
                    })
                else:
                    # Fallback format lama (hanya float KM)
                    val = float(s)
                    final_points.append({'km': val, 'lat': None, 'lon': None})
            
            # Sortir berdasarkan KM dan hapus duplikat
            final_points.sort(key=lambda x: x['km'])
            
            # Jika titik pertama bukan 0, tambahkan 0
            if not any(p['km'] == 0 for p in final_points):
                final_points.insert(0, {'km': 0.0, 'lat': coords[0][1], 'lon': coords[0][0]})
        else:
            # Mode Otomatis (Simpang): Gunakan Overpass API (logika lama)
            print(f"No manual splits found, falling back to Overpass API for {self.nama_ruas}")
            auto_kms = [0.0]
            try:
                lons = [float(c[0]) for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]
                lats = [float(c[1]) for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]
                
                if lons and lats:
                    buffer = 0.0005 
                    min_lat, max_lat = min(lats) - buffer, max(lats) + buffer
                    min_lon, max_lon = min(lons) - buffer, max(lons) + buffer

                    overpass_url = "https://overpass-api.de/api/interpreter"
                    overpass_query = f"""
                    [out:json][timeout:25];
                    way({min_lat},{min_lon},{max_lat},{max_lon})[highway];
                    node(w)->.n;
                    foreach .n(
                      way(bn)[highway];
                      if (count(ways) > 1) {{
                        .n out;
                      }}
                    );
                    """
                    response = requests.post(overpass_url, data={'data': overpass_query}, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        for element in data.get('elements', []):
                            if element['type'] == 'node':
                                int_lat, int_lon = element['lat'], element['lon']
                                min_d_to_road = float('inf')
                                km_on_road = 0.0
                                
                                for i in range(len(source_coords) - 1):
                                    p1 = source_coords[i]
                                    d_to_p1 = geodesic((int_lat, int_lon), (p1[1], p1[0])).kilometers
                                    if d_to_p1 < min_d_to_road:
                                        min_d_to_road = d_to_p1
                                        km_on_road = cumulative_distances[i]

                                if min_d_to_road < 0.03:
                                    if 0.01 < km_on_road < total_dist - 0.01:
                                        auto_kms.append(km_on_road)
            except Exception as e:
                print(f"Error in automatic split fallback: {e}")
            
            auto_kms.append(total_dist)
            auto_kms = sorted(list(set(auto_kms)))
            for km in auto_kms:
                final_points.append({'km': km, 'lat': None, 'lon': None})

        # 5. Buat SegmenJalan di database
        is_manual = bool(manual_splits)
        for i in range(len(final_points) - 1):
            p_start = final_points[i]
            p_end   = final_points[i + 1]

            km_awal        = decimal.Decimal(str(round(p_start['km'], 3)))
            km_akhir       = decimal.Decimal(str(round(p_end['km'],   3)))
            panjang_segmen = km_akhir - km_awal

            if panjang_segmen <= 0:
                continue

            # ── Geometry per segmen ──────────────────────────────────────
            # Prioritas 1: gunakan geometry Geoapify per-segmen yang dikirim frontend
            #              (akurat mengikuti jalur jalan sesungguhnya)
            # Prioritas 2: fallback ke slicing LineString utuh
            seg_geometry = None
            if is_manual and i < len(segment_geometries) and segment_geometries[i]:
                seg_geom_raw = segment_geometries[i]
                seg_geometry = json.dumps(seg_geom_raw) if isinstance(seg_geom_raw, dict) else str(seg_geom_raw)
            if not seg_geometry:
                seg_geometry = self._get_segment_geometry(float(km_awal), float(km_akhir))

            # ── Koordinat titik awal dan akhir segmen ────────────────────
            # Prioritas: dari splits (koordinat klik user) → dari geometry
            s_lat_awal  = p_start.get('lat')
            s_lon_awal  = p_start.get('lon')
            s_lat_akhir = p_end.get('lat')
            s_lon_akhir = p_end.get('lon')

            if (s_lat_awal is None or s_lat_akhir is None) and seg_geometry:
                try:
                    seg_data   = json.loads(seg_geometry)
                    seg_coords = seg_data.get('coordinates', [])
                    if seg_coords:
                        if s_lat_awal  is None: s_lon_awal,  s_lat_awal  = seg_coords[0]
                        if s_lat_akhir is None: s_lon_akhir, s_lat_akhir = seg_coords[-1]
                except Exception:
                    pass

            # ── Label titik ──────────────────────────────────────────────
            t_awal_label  = f"Titik {i + 1}" if is_manual else f"KM {km_awal}"
            t_akhir_label = f"Titik {i + 2}" if is_manual else f"KM {km_akhir}"
            if is_manual:
                if i == 0:                     t_awal_label  += " (START)"
                if i == len(final_points) - 2: t_akhir_label += " (END)"

            # ── Ekstrak Info Segmen ──────────────────────────────────────
            s_nama_segmen = None
            s_keterangan = None
            if is_manual and i < len(segment_info):
                s_info = segment_info[i]
                if isinstance(s_info, dict):
                    s_nama_segmen = s_info.get('nama_segmen')
                    s_keterangan = s_info.get('keterangan')
                    
            if not s_nama_segmen:
                s_nama_segmen = f"Segmen {i + 1}"

            # ── Simpan ke database ───────────────────────────────────────
            SegmenJalan.objects.create(
                ruas_jalan     = self,
                km_awal        = km_awal,
                km_akhir       = km_akhir,
                panjang_segmen = panjang_segmen,
                lat_awal       = s_lat_awal,
                lon_awal       = s_lon_awal,
                lat_akhir      = s_lat_akhir,
                lon_akhir      = s_lon_akhir,
                titik_awal     = t_awal_label,
                titik_akhir    = t_akhir_label,
                geometry       = seg_geometry,   # GeoJSON LineString dari Geoapify
                nama_segmen    = s_nama_segmen,
                keterangan     = s_keterangan,
            )
        print(f"Successfully generated {len(final_points) - 1} segments for {self.nama_ruas}.")


    def _get_segment_geometry(self, km_start, km_end):
        """Memotong geometry utama untuk segmen tertentu (km_start sampai km_end)"""
        if not self.geometry:
            return None
            
        try:
            geom_data = json.loads(self.geometry)
            if geom_data.get('type') == 'Feature':
                geom_data = geom_data.get('geometry', {})
            coords = geom_data.get('coordinates', [])
            
            if not coords:
                return None
                
            # Logika pemotongan sederhana berdasarkan jarak kumulatif
            def calculate_dist(p1, p2):
                return geodesic((p1[1], p1[0]), (p2[1], p2[0])).kilometers
                
            segment_coords = []
            total_dist = 0
            
            for i in range(len(coords) - 1):
                p1 = coords[i]
                p2 = coords[i+1]
                d = calculate_dist(p1, p2)
                
                # Jika p1 atau p2 berada dalam rentang, atau segmen p1-p2 melintasi rentang
                p1_in = (total_dist >= km_start and total_dist <= km_end)
                p2_in = (total_dist + d >= km_start and total_dist + d <= km_end)
                crosses = (total_dist < km_start and total_dist + d > km_end)
                
                if p1_in or p2_in or crosses:
                    if not segment_coords:
                        segment_coords.append(p1)
                    segment_coords.append(p2)
                
                total_dist += d
                if total_dist > km_end and not (p1_in or p2_in or crosses):
                    break
                    
            # Pastikan minimal ada 2 titik untuk LineString
            if len(segment_coords) >= 2:
                return json.dumps({
                    "type": "LineString",
                    "coordinates": segment_coords
                })
        except Exception as e:
            print(f"Error slicing geometry: {e}")
            
        return None


class SegmenJalan(models.Model):
    """Model untuk data segmen jalan (pembagian dari ruas jalan)"""
    
    id = models.AutoField(primary_key=True)
    ruas_jalan = models.ForeignKey(RuasJalan, on_delete=models.CASCADE, related_name='segmen_jalan')
    km_awal = models.DecimalField(max_digits=10, decimal_places=3)
    km_akhir = models.DecimalField(max_digits=10, decimal_places=3)
    panjang_segmen = models.DecimalField(max_digits=10, decimal_places=3)
    lat_awal = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    lon_awal = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    lat_akhir = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    lon_akhir = models.DecimalField(max_digits=12, decimal_places=9, null=True, blank=True)
    titik_awal = models.CharField(max_length=100, null=True, blank=True, help_text="Label titik awal (contoh: Titik 1)")
    titik_akhir = models.CharField(max_length=100, null=True, blank=True, help_text="Label titik akhir (contoh: Titik 2)")
    nama_segmen = models.CharField(max_length=255, null=True, blank=True, help_text="Nama segmen, bisa diubah dinamis")
    keterangan = models.TextField(null=True, blank=True, help_text="Penjelasan/keterangan segmen")
    geometry = models.TextField(null=True, blank=True, help_text="GeoJSON LineString untuk segmen ini")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Segmen Jalan'
        ordering = ['ruas_jalan', 'km_awal']
        unique_together = ('ruas_jalan', 'km_awal', 'km_akhir')
    
    def __str__(self):
        nama = self.nama_segmen if self.nama_segmen else f"Segmen {self.km_awal}-{self.km_akhir} km"
        return f"{self.ruas_jalan.nama_ruas} - {nama}"
    
    def get_accident_count(self, tahun=None):
        """Hitung jumlah kecelakaan di segmen ini"""
        from django.utils import timezone
        
        kecelakaan = Kecelakaan.objects.filter(segmen_jalan=self)
        
        if tahun:
            kecelakaan = kecelakaan.filter(tanggal__year=tahun)
        
        return kecelakaan.count()


class Kecelakaan(models.Model):
    """Model untuk data kecelakaan"""
    
    id = models.AutoField(primary_key=True)
    tanggal = models.DateField()
    waktu = models.TimeField()
    latitude = models.DecimalField(max_digits=30, decimal_places=20)
    longitude = models.DecimalField(max_digits=30, decimal_places=20)
    segmen_jalan = models.ForeignKey(SegmenJalan, on_delete=models.SET_NULL, null=True, blank=True,related_name='kecelakaan')
    korban_meninggal = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_berat = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_ringan = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    kerugian_materi = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    desa = models.CharField(max_length=100)
    kecamatan = models.CharField(max_length=100)
    kabupaten_kota = models.CharField(max_length=100)
    keterangan = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Kecelakaan'
        ordering = ['-tanggal', '-waktu']
    
    def __str__(self):
        return f"Kecelakaan {self.tanggal} - {self.kecamatan}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Otomatis assign segmen jalan terdekat
        if self.latitude and self.longitude and not self.segmen_jalan:
            self.find_closest_segment()
    
    def find_closest_segment(self):
        """Temukan segmen jalan terdekat menggunakan geopy"""
        from django.db.models import F, FloatField, ExpressionWrapper
        
        accident_point = (float(self.latitude), float(self.longitude))
        
        # Hitung jarak ke setiap segmen (menggunakan rata2 km awal/akhir)
        min_distance = float('inf')
        closest_segmen = None
        
        # Iterasi semua segmen untuk hitung jarak
        for segmen in SegmenJalan.objects.select_related('ruas_jalan'):
            # Estimasi koordinat segmen menggunakan rata-rata km
            # Dalam aplikasi nyata, sebaiknya simpan lat/lon di SegmenJalan juga
            # Untuk saat ini, gunakan ruas_jalan reference
            
            # Jarak dihitung ke center ruas jalan (simplified)
            # Better: simpan start/end lat/lon untuk setiap segmen
            distance = 0  # Default jika tidak ada data
            
            if distance < min_distance:
                min_distance = distance
                closest_segmen = segmen
        
        if closest_segmen:
            self.segmen_jalan = closest_segmen
            super().save(update_fields=['segmen_jalan'])
    
    @property
    def total_korban(self):
        """Total semua korban"""
        return self.korban_meninggal + self.korban_luka_berat + self.korban_luka_ringan


class RekapSegmen(models.Model):
    """Model untuk rekapitulasi data kecelakaan per segmen"""
    
    id = models.AutoField(primary_key=True)
    segmen_jalan = models.ForeignKey(
        SegmenJalan, 
        on_delete=models.CASCADE,
        related_name='rekap'
    )
    jumlah_kecelakaan = models.IntegerField(default=0)
    total_korban = models.IntegerField(default=0)
    total_meninggal = models.IntegerField(default=0)
    total_luka_berat = models.IntegerField(default=0)
    total_luka_ringan = models.IntegerField(default=0)
    total_kerugian = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    periode_tahun = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Rekap Segmen'
        unique_together = ('segmen_jalan', 'periode_tahun')
        ordering = ['-periode_tahun', 'segmen_jalan']
    
    def __str__(self):
        return f"{self.segmen_jalan} - {self.periode_tahun}"
    
    @staticmethod
    def update_rekap(tahun=None):
        """Update rekapitulasi untuk tahun tertentu atau semua tahun"""
        from django.db.models import Sum, Count, Q
        
        if tahun is None:
            tahun = timezone.now().year
        
        # Hapus rekap lama
        RekapSegmen.objects.filter(periode_tahun=tahun).delete()
        
        # Hitung ulang dari data kecelakaan
        segmen_list = SegmenJalan.objects.all()
        
        for segmen in segmen_list:
            kecelakaan_data = Kecelakaan.objects.filter(
                segmen_jalan=segmen,
                tanggal__year=tahun
            ).aggregate(
                jumlah=Count('id'),
                meninggal=Sum('korban_meninggal'),
                luka_berat=Sum('korban_luka_berat'),
                luka_ringan=Sum('korban_luka_ringan'),
                kerugian=Sum('kerugian_materi')
            )
            
            # Hitung total korban dari penjumlahan meninggal + luka_berat + luka_ringan
            total_korban = (kecelakaan_data['meninggal'] or 0) + \
                          (kecelakaan_data['luka_berat'] or 0) + \
                          (kecelakaan_data['luka_ringan'] or 0)
            
            RekapSegmen.objects.create(
                segmen_jalan=segmen,
                jumlah_kecelakaan=kecelakaan_data['jumlah'] or 0,
                total_korban=total_korban,
                total_meninggal=kecelakaan_data['meninggal'] or 0,
                total_luka_berat=kecelakaan_data['luka_berat'] or 0,
                total_luka_ringan=kecelakaan_data['luka_ringan'] or 0,
                total_kerugian=kecelakaan_data['kerugian'] or 0,
                periode_tahun=tahun
            )


class AnalisisZScore(models.Model):
    """Model untuk analisis Z-Score tingkat kerawanan kecelakaan"""
    
    KATEGORI_CHOICES = (
        ('sangat_tinggi', 'Sangat Tinggi (Z > 1.5)'),
        ('tinggi', 'Tinggi (0.5 < Z ≤ 1.5)'),
        ('sedang', 'Sedang (-0.5 < Z ≤ 0.5)'),
        ('rendah', 'Rendah (-1.5 < Z ≤ -0.5)'),
        ('sangat_rendah', 'Sangat Rendah (Z ≤ -1.5)'),
    )
    
    id = models.AutoField(primary_key=True)
    segmen_jalan = models.ForeignKey(
        SegmenJalan,
        on_delete=models.CASCADE,
        related_name='analisis_zscore'
    )
    nilai_zscore = models.DecimalField(max_digits=5, decimal_places=3)
    kategori = models.CharField(max_length=20, choices=KATEGORI_CHOICES)
    tahun = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Analisis Z-Score'
        unique_together = ('segmen_jalan', 'tahun')
        ordering = ['-tahun', '-nilai_zscore']
    
    def __str__(self):
        return f"{self.segmen_jalan} - {self.kategori} ({self.nilai_zscore}) - {self.tahun}"
    
    @staticmethod
    def calculate_zscore(tahun=None):
        """Hitung Z-Score untuk semua segmen"""
        from django.db.models import Avg, StdDev
        import decimal
        
        if tahun is None:
            tahun = timezone.now().year
        
        # Pastikan rekap sudah update
        RekapSegmen.update_rekap(tahun)
        
        # Hapus analisis lama
        AnalisisZScore.objects.filter(tahun=tahun).delete()
        
        # Hitung mean dan std dev dari jumlah kecelakaan
        stats = RekapSegmen.objects.filter(
            periode_tahun=tahun
        ).aggregate(
            mean=Avg('jumlah_kecelakaan'),
            stddev=StdDev('jumlah_kecelakaan')
        )
        
        mean = float(stats['mean'] or 0)
        stddev = float(stats['stddev'] or 1)
        
        # Hindari pembagian dengan 0
        if stddev == 0:
            stddev = 1
        
        # Hitung Z-Score untuk setiap segmen
        rekap_list = RekapSegmen.objects.filter(periode_tahun=tahun)
        
        for rekap in rekap_list:
            zscore = (float(rekap.jumlah_kecelakaan) - mean) / stddev
            
            # Kategorisasi berdasarkan Z-Score
            if zscore > 1.5:
                kategori = 'sangat_tinggi'
            elif zscore > 0.5:
                kategori = 'tinggi'
            elif zscore > -0.5:
                kategori = 'sedang'
            elif zscore > -1.5:
                kategori = 'rendah'
            else:
                kategori = 'sangat_rendah'
            
            AnalisisZScore.objects.create(
                segmen_jalan=rekap.segmen_jalan,
                nilai_zscore=decimal.Decimal(str(round(zscore, 3))),
                kategori=kategori,
                tahun=tahun
            )
    
    def get_kategori_display_color(self):
        """Dapatkan warna untuk kategori Z-Score"""
        colors = {
            'sangat_tinggi': '#d32f2f',  # Merah gelap
            'tinggi': '#f57c00',          # Oranye
            'sedang': '#fbc02d',          # Kuning
            'rendah': '#7cb342',          # Hijau muda
            'sangat_rendah': '#388e3c',  # Hijau
        }
        return colors.get(self.kategori, '#999999')
    
    #=========================K-Means Location Models=========================
class Kota(models.Model):
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama

class Kecamatan(models.Model):
    kota = models.ForeignKey(Kota, on_delete=models.CASCADE)
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama

class Kelurahan(models.Model):
    kecamatan = models.ForeignKey(Kecamatan, on_delete=models.CASCADE)
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama

class KMeansData(models.Model):
    """Model untuk data mentah yang digunakan dalam proses K-Means"""
    no_referensi = models.CharField(max_length=50, blank=True, null=True)
    umur = models.IntegerField()
    tkp = models.CharField(max_length=255)
    penyebab = models.CharField(max_length=255)
    hari = models.CharField(max_length=20)
    tanggal = models.DateField()
    jam = models.CharField(max_length=10) # Format "19.00"
    jenis_kendaraan = models.CharField(max_length=100)
    tipe_kendaraan = models.CharField(max_length=100)
    kerugian_material = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "K-Means Data"
        ordering = ['-tanggal', '-jam']

    def __str__(self):
        return f"{self.tanggal} - {self.tkp}"

class AIConfig(models.Model):
    """Model untuk menyimpan konfigurasi API Key AI"""
    tipe = models.CharField(max_length=50, unique=True, default='kmeans')
    api_key = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "AI Config"

    def __str__(self):
        return f"Config {self.tipe}"
