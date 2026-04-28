from django.contrib import admin
from .models import RuasJalan, SegmenJalan, Kecelakaan, RekapSegmen, AnalisisZScore, KecelakaanRaw, KecelakaanPreprosesing


@admin.register(RuasJalan)
class RuasJalanAdmin(admin.ModelAdmin):
    list_display = ['nama_ruas', 'jenis_jalan', 'wilayah', 'panjang_km', 'created_at']
    list_filter = ['jenis_jalan', 'wilayah', 'created_at']
    search_fields = ['nama_ruas', 'wilayah']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Informasi Umum', {
            'fields': ('nama_ruas', 'jenis_jalan', 'wilayah', 'panjang_km')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SegmenJalan)
class SegmenJalanAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'km_awal', 'km_akhir', 'panjang_segmen', 'created_at']
    list_filter = ['ruas_jalan', 'created_at']
    search_fields = ['ruas_jalan__nama_ruas']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Informasi Segmen', {
            'fields': ('ruas_jalan', 'km_awal', 'km_akhir', 'panjang_segmen')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Kecelakaan)
class KecelakaanAdmin(admin.ModelAdmin):
    list_display = ['tanggal', 'waktu', 'kecamatan', 'total_korban', 'kerugian_materi']
    list_filter = ['tanggal', 'kecamatan', 'kabupaten_kota', 'created_at']
    search_fields = ['desa', 'kecamatan', 'kabupaten_kota']
    readonly_fields = ['created_at', 'updated_at', 'total_korban']
    fieldsets = (
        ('Waktu', {
            'fields': ('tanggal', 'waktu')
        }),
        ('Lokasi', {
            'fields': ('latitude', 'longitude', 'desa', 'kecamatan', 'kabupaten_kota', 'segmen_jalan')
        }),
        ('Data Korban', {
            'fields': ('korban_meninggal', 'korban_luka_berat', 'korban_luka_ringan', 'total_korban')
        }),
        ('Kerugian & Keterangan', {
            'fields': ('kerugian_materi', 'keterangan')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RekapSegmen)
class RekapSegmenAdmin(admin.ModelAdmin):
    list_display = ['segmen_jalan', 'periode_tahun', 'jumlah_kecelakaan', 'total_korban', 'total_kerugian']
    list_filter = ['periode_tahun', 'segmen_jalan__ruas_jalan']
    search_fields = ['segmen_jalan__ruas_jalan__nama_ruas']
    readonly_fields = ['created_at', 'updated_at', 'jumlah_kecelakaan', 'total_korban', 
                       'total_meninggal', 'total_luka_berat', 'total_luka_ringan', 'total_kerugian']
    fieldsets = (
        ('Informasi Segmen', {
            'fields': ('segmen_jalan', 'periode_tahun')
        }),
        ('Data Rekapitulasi', {
            'fields': ('jumlah_kecelakaan', 'total_meninggal', 'total_luka_berat', 'total_luka_ringan', 'total_korban', 'total_kerugian')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AnalisisZScore)
class AnalisisZScoreAdmin(admin.ModelAdmin):
    list_display = ['segmen_jalan', 'tahun', 'nilai_zscore', 'kategori']
    list_filter = ['tahun', 'kategori', 'segmen_jalan__ruas_jalan']
    search_fields = ['segmen_jalan__ruas_jalan__nama_ruas']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Informasi Analisis', {
            'fields': ('segmen_jalan', 'tahun', 'nilai_zscore', 'kategori')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(KecelakaanRaw)
class KecelakaanRawAdmin(admin.ModelAdmin):
    list_display = ['tanggal', 'waktu', 'kecamatan', 'total_korban']
    list_filter = ['tanggal', 'kecamatan', 'kabupaten_kota']
    search_fields = ['desa', 'kecamatan', 'kabupaten_kota']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Waktu', {
            'fields': ('tanggal', 'waktu')
        }),
        ('Lokasi', {
            'fields': ('latitude', 'longitude', 'desa', 'kecamatan', 'kabupaten_kota')
        }),
        ('Data Korban', {
            'fields': ('korban_meninggal', 'korban_luka_berat', 'korban_luka_ringan')
        }),
        ('Kerugian & Keterangan', {
            'fields': ('kerugian_materi', 'keterangan')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_korban(self, obj):
        return obj.korban_meninggal + obj.korban_luka_berat + obj.korban_luka_ringan
    total_korban.short_description = 'Total Korban'


@admin.register(KecelakaanPreprosesing)
class KecelakaanPreprosessingAdmin(admin.ModelAdmin):
    list_display = ['tanggal', 'waktu', 'kecamatan', 'segmen_jalan', 'total_korban']
    list_filter = ['tanggal', 'kecamatan', 'kabupaten_kota', 'segmen_jalan__ruas_jalan']
    search_fields = ['desa', 'kecamatan', 'kabupaten_kota', 'segmen_jalan__nama_segmen']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Waktu', {
            'fields': ('tanggal', 'waktu')
        }),
        ('Lokasi', {
            'fields': ('latitude', 'longitude', 'desa', 'kecamatan', 'kabupaten_kota', 'segmen_jalan')
        }),
        ('Data Korban', {
            'fields': ('korban_meninggal', 'korban_luka_berat', 'korban_luka_ringan')
        }),
        ('Kerugian & Keterangan', {
            'fields': ('kerugian_materi', 'keterangan')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_korban(self, obj):
        return obj.korban_meninggal + obj.korban_luka_berat + obj.korban_luka_ringan
    total_korban.short_description = 'Total Korban'
