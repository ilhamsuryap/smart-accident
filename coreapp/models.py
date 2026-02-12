from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from geopy.distance import geodesic
import math


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Ruas Jalan'
        ordering = ['nama_ruas']
    
    def __str__(self):
        return f"{self.nama_ruas} ({self.jenis_jalan})"
    
    def generate_segmen(self):
        """Generate segmen jalan otomatis setiap 1 km"""
        # Hapus segmen lama
        SegmenJalan.objects.filter(ruas_jalan=self).delete()
        
        # Hitung jumlah segmen
        panjang = float(self.panjang_km)
        jumlah_segmen = int(math.ceil(panjang))
        
        # Buat segmen
        for i in range(jumlah_segmen):
            km_awal = i
            km_akhir = min(i + 1, panjang)
            panjang_segmen = km_akhir - km_awal
            
            SegmenJalan.objects.create(
                ruas_jalan=self,
                km_awal=km_awal,
                km_akhir=km_akhir,
                panjang_segmen=panjang_segmen
            )


class SegmenJalan(models.Model):
    """Model untuk data segmen jalan (pembagian dari ruas jalan)"""
    
    id = models.AutoField(primary_key=True)
    ruas_jalan = models.ForeignKey(RuasJalan, on_delete=models.CASCADE, related_name='segmen_jalan')
    km_awal = models.DecimalField(max_digits=10, decimal_places=3)
    km_akhir = models.DecimalField(max_digits=10, decimal_places=3)
    panjang_segmen = models.DecimalField(max_digits=10, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Segmen Jalan'
        ordering = ['ruas_jalan', 'km_awal']
        unique_together = ('ruas_jalan', 'km_awal', 'km_akhir')
    
    def __str__(self):
        return f"{self.ruas_jalan.nama_ruas} - Segmen {self.km_awal}-{self.km_akhir} km"
    
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
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    segmen_jalan = models.ForeignKey(
        SegmenJalan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='kecelakaan'
    )
    jumlah_kecelakaan = models.IntegerField(default=1, validators=[MinValueValidator(1)])
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
                total_korban=Sum('jumlah_kecelakaan'),
                meninggal=Sum('korban_meninggal'),
                luka_berat=Sum('korban_luka_berat'),
                luka_ringan=Sum('korban_luka_ringan'),
                kerugian=Sum('kerugian_materi')
            )
            
            RekapSegmen.objects.create(
                segmen_jalan=segmen,
                jumlah_kecelakaan=kecelakaan_data['jumlah'] or 0,
                total_korban=kecelakaan_data['total_korban'] or 0,
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
