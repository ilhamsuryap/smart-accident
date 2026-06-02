from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin
)
from geopy.distance import geodesic
import math
import requests
import json
import decimal
import traceback

# ============================================================================
# MODEL POLRES (Dinamis — tidak pakai enum)
# ============================================================================

class Polres(models.Model):
    """Model untuk data Polres yang dikelola secara dinamis oleh superadmin"""
    nama = models.CharField(max_length=100, verbose_name='Nama Polres')
    kode = models.CharField(max_length=50, unique=True, verbose_name='Kode Polres', help_text='Contoh: polres_madiun')
    alamat = models.TextField(blank=True, null=True, verbose_name='Alamat')
    telepon = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telepon')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Polres'
        verbose_name_plural = 'Polres'
        ordering = ['nama']

    def __str__(self):
        return self.nama


# ============================================================================
# CUSTOM USER MODEL & AUTHENTICATION
# ============================================================================

from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    """Manager untuk Custom User Model"""

    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError("Email harus diisi")
        if not name:
            raise ValueError("Nama harus diisi")

        email = self.normalize_email(email)

        # Default keamanan
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields["role"] not in ["admin", "superadmin"]:
            raise ValueError("Role tidak valid")

        user = self.model(
            email=email,
            name=name,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # untuk Google OAuth

        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password, **extra_fields):
        extra_fields.setdefault("role", "superadmin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("role") != "superadmin":
            raise ValueError("Superuser harus memiliki role=superadmin")
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser harus memiliki is_staff=True")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser harus memiliki is_superuser=True")

        return self.create_user(email, name, password, **extra_fields)
    
class User(AbstractBaseUser, PermissionsMixin):
    """Custom User Model untuk sistem autentikasi internal"""
    
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
    )
    
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True, verbose_name='Username')
    first_name = models.CharField(max_length=150, blank=True, verbose_name='Nama Depan')
    last_name = models.CharField(max_length=150, blank=True, verbose_name='Nama Belakang')
    name = models.CharField(max_length=255, verbose_name='Nama Lengkap')
    email = models.EmailField(unique=True, verbose_name='Email Institusi')
    password = models.CharField(max_length=128, null=True, blank=True, verbose_name='Password')
    google_id = models.CharField(max_length=255, null=True, blank=True, unique=True, verbose_name='Google ID')
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='admin',
        verbose_name='Role'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktif',
        help_text='Tentukan apakah user dapat login'
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Staff Status',
        help_text='Tentukan apakah user dapat mengakses admin panel'
    )
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name='Dibuat Oleh',
        help_text='Superadmin yang membuat akun ini'
    )
    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Login Terakhir'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Dibuat Pada'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Diperbarui Pada'
    )
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.email}) - {self.get_role_display()}"
    
    def is_superadmin(self):
        """Check apakah user adalah superadmin"""
        return self.role == 'superadmin'
    
    def is_admin_user(self):
        """Check apakah user adalah admin"""
        return self.role == 'admin'


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('login_success', 'Login Berhasil'),
        ('login_failed', 'Login Gagal'),
        ('logout', 'Logout'),
        ('login_oauth_success', 'Login OAuth Berhasil'),
        ('login_oauth_failed', 'Login OAuth Gagal'),
        ('user_created', 'User Dibuat'),
        ('user_updated', 'User Diperbarui'),
        ('user_deleted', 'User Dihapus'),
        ('user_deactivated', 'User Dinonaktifkan'),
        ('user_reactivated', 'User Diaktifkan Kembali'),
        ('role_changed', 'Role Diubah'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ WAJIB
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=(('success', 'Sukses'), ('failed', 'Gagal')),
        default='success'
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email if self.user else 'Unknown'} - {self.get_action_display()} ({self.get_status_display()})"


class Profile(models.Model):
    """Model untuk profil tambahan user"""
    
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
    )

    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='User'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='admin',
        help_text="Role pengguna dalam sistem"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Status aktif akun. Jika False, user tidak dapat login."
    )
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres',
        help_text="Polres yang dikelola oleh user ini (dinamis dari database)"
    )
    alamat = models.TextField(blank=True, null=True, verbose_name='Alamat')
    foto = models.ImageField(upload_to='profile/', blank=True, null=True, verbose_name='Foto')
    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Nomor Telepon'
    )
    avatar = models.ImageField(
        upload_to='profile/',
        null=True,
        blank=True,
        verbose_name='Avatar'
    )
    bio = models.TextField(
        null=True,
        blank=True,
        verbose_name='Bio'
    )
    institution = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Institusi'
    )
    position = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Jabatan'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Dibuat Pada'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Diperbarui Pada'
    )
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile - {self.user.name or self.user.username}"

    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_admin_role(self):
        return self.role in ('superadmin', 'admin')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Otomatis buat Profile ketika User baru dibuat — sinkronkan role dari User ke Profile"""
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        # Sinkronkan role dari User ke Profile
        if profile.role != instance.role:
            profile.role = instance.role
            profile.is_active = instance.is_active
            profile.save(update_fields=['role', 'is_active'])
    else:
        # Update profile saat user diupdate
        try:
            profile = instance.profile
            profile.role = instance.role
            profile.is_active = instance.is_active
            profile.save(update_fields=['role', 'is_active'])
        except Profile.DoesNotExist:
            Profile.objects.create(
                user=instance,
                role=instance.role,
                is_active=instance.is_active
            )



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
    lat_awal = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True, help_text="Latitude titik awal ruas jalan")
    lon_awal = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True, help_text="Longitude titik awal ruas jalan")
    lat_akhir = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True, help_text="Latitude titik akhir ruas jalan")
    lon_akhir = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True, help_text="Longitude titik akhir ruas jalan")
    geometry = models.TextField(null=True, blank=True, help_text="GeoJSON LineString untuk seluruh ruas jalan")
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres',
        help_text="Polres yang menambahkan ruas jalan ini"
    )
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
    lat_awal = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True)
    lon_awal = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True)
    lat_akhir = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True)
    lon_akhir = models.DecimalField(max_digits=25, decimal_places=20, null=True, blank=True)
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
    latitude = models.DecimalField(max_digits=30, decimal_places=20, help_text="Latitude koordinat kecelakaan")
    longitude = models.DecimalField(max_digits=30, decimal_places=20, help_text="Longitude koordinat kecelakaan")
    segmen_jalan = models.ForeignKey(SegmenJalan, on_delete=models.SET_NULL, null=True, blank=True, related_name='kecelakaan', help_text="Otomatis diassign ke segmen terdekat (threshold 5km) saat disimpan. Bisa diubah manual jika perlu.")
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
            # Jika find_closest_segment berhasil assign, simpan perubahan
            if self.segmen_jalan:
                super().save(update_fields=['segmen_jalan'])
    
    def find_closest_segment(self):
        """
        Temukan segmen jalan di mana titik kecelakaan berada TEPAT DI ANTARA
        titik awal dan titik akhir segmen. Menggunakan proyeksi perpendicular
        dari titik ke garis segmen untuk presisi maksimal.
        
        Algoritma:
        1. Cek apakah titik ada dalam bounding box segmen
        2. Hitung jarak perpendicular dari titik ke garis segmen
        3. Jika jarak <= tolerance, assign ke segmen tersebut
        """
        import math
        
        accident_lat = float(self.latitude)
        accident_lon = float(self.longitude)
        
        # Tolerance untuk jarak perpendicular: ~50 meter
        tolerance_km = 0.050
        
        best_match = None
        smallest_distance = float('inf')
        
        # Iterasi semua segmen untuk cek titik
        for segmen in SegmenJalan.objects.select_related('ruas_jalan').all():
            if not (segmen.lat_awal and segmen.lon_awal and segmen.lat_akhir and segmen.lon_akhir):
                continue
            
            s_lat_awal = float(segmen.lat_awal)
            s_lon_awal = float(segmen.lon_awal)
            s_lat_akhir = float(segmen.lat_akhir)
            s_lon_akhir = float(segmen.lon_akhir)
            
            # 1. Cek bounding box dulu (quick check)
            buffer = 0.001  # ~111 meter
            min_lat = min(s_lat_awal, s_lat_akhir) - buffer
            max_lat = max(s_lat_awal, s_lat_akhir) + buffer
            min_lon = min(s_lon_awal, s_lon_akhir) - buffer
            max_lon = max(s_lon_awal, s_lon_akhir) + buffer
            
            if not (min_lat <= accident_lat <= max_lat and min_lon <= accident_lon <= max_lon):
                continue
            
            # 2. Hitung jarak perpendicular dari titik ke garis segmen
            perp_distance = self._calculate_perpendicular_distance(
                accident_lat, accident_lon,
                s_lat_awal, s_lon_awal,
                s_lat_akhir, s_lon_akhir
            )
            
            # 3. Jika jarak perpendicular <= tolerance, ini adalah match
            if perp_distance is not None and perp_distance <= tolerance_km:
                if perp_distance < smallest_distance:
                    smallest_distance = perp_distance
                    best_match = segmen
        
        # Assign ke segmen terbaik jika ada match (tanpa save, dibiarkan parent save handle)
        if best_match:
            self.segmen_jalan = best_match
            print(f"✓ Kecelakaan {self.id} → Segmen '{best_match.nama_segmen}' (jarak perp: {smallest_distance*1000:.1f}m)")
        else:
            print(f"⚠ Kecelakaan {self.id}: Tidak ada segmen yang sesuai (tolerance: {tolerance_km*1000:.0f}m)")
    
    def _calculate_perpendicular_distance(self, lat, lon, lat1, lon1, lat2, lon2):
        """
        Hitung jarak PERPENDICULAR dari titik (lat, lon) ke garis segmen
        antara titik (lat1, lon1) dan (lat2, lon2).
        
        Mengembalikan:
        - Jarak dalam km jika titik proyeksi ada dalam segmen
        - None jika titik proyeksi diluar rentang segmen
        """
        import math
        
        # Convert ke radians
        lat = math.radians(lat)
        lon = math.radians(lon)
        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)
        
        R = 6371  # Earth radius in km
        
        # Angular distance dari start ke accident
        dLat = lat - lat1
        dLon = lon - lon1
        a = math.sin(dLat/2)**2 + math.cos(lat1) * math.cos(lat) * math.sin(dLon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        d13 = R * c
        
        # Bearing dari start ke end
        dLon12 = lon2 - lon1
        y = math.sin(dLon12) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon12)
        theta12 = math.atan2(y, x)
        
        # Bearing dari start ke accident
        dLon13 = lon - lon1
        y13 = math.sin(dLon13) * math.cos(lat)
        x13 = math.cos(lat1) * math.sin(lat) - math.sin(lat1) * math.cos(lat) * math.cos(dLon13)
        theta13 = math.atan2(y13, x13)
        
        # Cross-track distance (perpendicular distance)
        dXt = math.asin(math.sin(d13/R) * math.sin(theta13 - theta12))
        cross_track_distance_km = abs(dXt * R)
        
        # Along-track distance (untuk cek apakah dalam rentang)
        try:
            dAt = math.acos(max(-1, min(1, math.cos(d13/R) / abs(math.cos(dXt)))))
        except:
            dAt = 0
        
        # Jarak dari start ke end
        dLat12 = lat2 - lat1
        dLon12_calc = lon2 - lon1
        a12 = math.sin(dLat12/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon12_calc/2)**2
        c12 = 2 * math.asin(math.sqrt(a12))
        d12 = R * c12
        
        # Cek apakah proyeksi ada dalam rentang segmen
        # Dengan toleransi kecil di ujung-ujung segmen
        if -0.05 <= dAt <= (d12 + 0.05):
            return cross_track_distance_km
        else:
            # Proyeksi di luar segmen, jadi tidak cocok
            return None
    
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
        
        if tahun is None or tahun == 0 or tahun == '0':
            tahun = 0
        else:
            try:
                tahun = int(tahun)
            except (ValueError, TypeError):
                tahun = 0
        
        # Hapus rekap lama
        RekapSegmen.objects.filter(periode_tahun=tahun).delete()
        
        # Hitung ulang dari data kecelakaan preprocessing
        segmen_list = SegmenJalan.objects.all()
        
        for segmen in segmen_list:
            if tahun == 0:
                kecelakaan_data = KecelakaanPreprosesing.objects.filter(
                    segmen_jalan=segmen
                ).aggregate(
                    jumlah=Count('id'),
                    meninggal=Sum('korban_meninggal'),
                    luka_berat=Sum('korban_luka_berat'),
                    luka_ringan=Sum('korban_luka_ringan'),
                    kerugian=Sum('kerugian_materi')
                )
            else:
                kecelakaan_data = KecelakaanPreprosesing.objects.filter(
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
    def calculate_zscore_all_years():
        """Hitung Z-Score untuk semua tahun (tahun=0)"""
        AnalisisZScore.calculate_zscore(0)
    
    @staticmethod
    def calculate_zscore(tahun=None):
        """Hitung Z-Score untuk setiap segmen PER RUAS JALAN dengan interval dinamis"""
        from django.db.models import Avg, StdDev, Max, Min
        import decimal
        
        if tahun is None or tahun == 0 or tahun == '0':
            tahun = 0
        
        # 1. Pastikan data rekapitulasi kecelakaan sudah diperbarui untuk tahun yang dipilih
        RekapSegmen.update_rekap(tahun)
        
        # 2. Hapus data analisis Z-Score lama untuk tahun tersebut agar tidak duplikat
        AnalisisZScore.objects.filter(tahun=tahun).delete()
        
        # 3. Ambil semua daftar ruas jalan yang unik
        ruas_jalan_list = RuasJalan.objects.all().distinct()
        
        print(f"\n📊 Calculating Z-Score for {tahun} - Per Ruas Jalan (Dynamic Intervals)")
        print(f"{'='*80}")
        
        # 4. Iterasi setiap ruas jalan untuk menghitung Z-Score secara spesifik per ruas
        for ruas_jalan in ruas_jalan_list:
            # Ambil semua segmen yang termasuk dalam ruas jalan ini
            segments_in_ruas = SegmenJalan.objects.filter(ruas_jalan=ruas_jalan)
            
            # Hitung statistik dasar (Rata-rata dan Standar Deviasi) dari jumlah kecelakaan di ruas ini
            # StdDev (σ) mengukur seberapa jauh variasi data kecelakaan dari rata-ratanya
            
            # Standar Deviasi digunakan untuk memahami apakah angka kecelakaan di suatu 
            # ruas jalan cenderung merata di semua segmen, atau hanya menumpuk di titik-titik tertentu saja.
            # Nilai ini kemudian menjadi pembagi dalam rumus Z-Score untuk menentukan apakah sebuah angka kecelakaan di satu segmen termasuk "ekstrim" (rawan) atau masih dalam batas wajar.
            stats = RekapSegmen.objects.filter(
                periode_tahun=tahun,
                segmen_jalan__in=segments_in_ruas
            ).aggregate(
                mean=Avg('jumlah_kecelakaan'),
                stddev=StdDev('jumlah_kecelakaan')
            )
            
            mean = float(stats['mean'] or 0)
            stddev = float(stats['stddev'] or 1)
            
            # Hindari pembagian dengan nol jika standar deviasi tidak terhitung
            if stddev == 0:
                stddev = 1
            
            # 5. Hitung nilai Z-Score mentah untuk setiap segmen
            # Rumus: Z = (X - μ) / σ
            # Di mana X = jumlah kecelakaan, μ = rata-rata, σ = standar deviasi
            zscore_dict = {}
            rekap_list = RekapSegmen.objects.filter(
                periode_tahun=tahun,
                segmen_jalan__in=segments_in_ruas
            )
            
            for rekap in rekap_list:
                zscore = (float(rekap.jumlah_kecelakaan) - mean) / stddev
                zscore_dict[rekap.segmen_jalan.id] = {
                    'rekap': rekap,
                    'zscore': zscore
                }
            
            # 6. Tentukan nilai Z_max dan Z_min untuk menentukan rentang interval klasifikasi
            if zscore_dict:
                zscore_values = [item['zscore'] for item in zscore_dict.values()]
                z_max = max(zscore_values)
                z_min = min(zscore_values)
            else:
                z_max = 0
                z_min = 0
            
            # 7. Hitung Interval (I) untuk membagi data ke dalam 5 kategori klasifikasi
            # Rumus Interval: I = (Z_max - Z_min) / Jumlah_Kelas
            num_classifications = 5
            if z_max != z_min:
                interval = (z_max - z_min) / num_classifications
            else:
                interval = 1  # Default jika semua nilai Z-Score sama
            
            # 8. Tentukan ambang batas (threshold) untuk setiap tingkatan kategori
            threshold_1 = z_min + (1 * interval)  # Batas Sangat Rendah -> Rendah
            threshold_2 = z_min + (2 * interval)  # Batas Rendah -> Sedang
            threshold_3 = z_min + (3 * interval)  # Batas Sedang -> Tinggi
            threshold_4 = z_min + (4 * interval)  # Batas Tinggi -> Sangat Tinggi
            
            segmen_count = segments_in_ruas.count()
            print(f"\n🛣️ Ruas: {ruas_jalan.nama_ruas} ({segmen_count} segmen)")
            print(f"   Mean: {mean:.2f}, StdDev: {stddev:.2f}")
            print(f"   Z_max: {z_max:.3f}, Z_min: {z_min:.3f}, Interval: {interval:.3f}")
            print(f"   Thresholds: {threshold_1:.3f} | {threshold_2:.3f} | {threshold_3:.3f} | {threshold_4:.3f}")
            
            # 9. Klasifikasikan setiap segmen ke dalam kategori berdasarkan threshold yang sudah dihitung
            for segmen_id, data in zscore_dict.items():
                rekap = data['rekap']
                zscore = data['zscore']
                
                # Penentuan kategori secara dinamis
                if zscore >= threshold_4:
                    kategori = 'sangat_tinggi'
                elif zscore >= threshold_3:
                    kategori = 'tinggi'
                elif zscore >= threshold_2:
                    kategori = 'sedang'
                elif zscore >= threshold_1:
                    kategori = 'rendah'
                else:
                    kategori = 'sangat_rendah'
                
                # 10. Simpan hasil analisis Z-Score ke database
                AnalisisZScore.objects.create(
                    segmen_jalan=rekap.segmen_jalan,
                    nilai_zscore=decimal.Decimal(str(round(zscore, 3))),
                    kategori=kategori,
                    tahun=tahun
                )
                
                print(f"   ✓ {rekap.segmen_jalan.nama_segmen}: {rekap.jumlah_kecelakaan} accidents → Z={zscore:.3f} ({kategori})")
        
        print(f"\n{'='*80}\n")

    
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


class KecelakaanRaw(models.Model):
    """Model untuk data kecelakaan raw (data mentah dari upload)"""
    id = models.BigAutoField(primary_key=True)
    nomor_kecelakaan = models.CharField(max_length=50, null=True, blank=True, help_text='Nomor identitas kecelakaan')
    tanggal = models.DateField()
    waktu = models.TimeField()
    latitude = models.DecimalField(max_digits=30, decimal_places=20)
    longitude = models.DecimalField(max_digits=30, decimal_places=20)
    korban_meninggal = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_berat = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_ringan = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    kerugian_materi = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    desa = models.CharField(max_length=100)
    kecamatan = models.CharField(max_length=100)
    kabupaten_kota = models.CharField(max_length=100)
    keterangan = models.TextField(blank=True)
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres',
        help_text="Polres yang upload data raw ini"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Data Kecelakaan Raw'
        ordering = ['-tanggal', '-waktu']
    
    @property
    def total_korban(self):
        return self.korban_meninggal + self.korban_luka_berat + self.korban_luka_ringan

    def __str__(self):
        return f"Raw {self.tanggal} - {self.kecamatan}"


class KecelakaanPreprosesing(models.Model):
    """Model untuk data kecelakaan yang sudah dipreproses (akan diassign ke segmen)"""
    id = models.BigAutoField(primary_key=True)
    nomor_kecelakaan = models.CharField(max_length=50, null=True, blank=True, help_text='Nomor identitas kecelakaan')
    tanggal = models.DateField()
    waktu = models.TimeField()
    latitude = models.DecimalField(max_digits=30, decimal_places=20)
    longitude = models.DecimalField(max_digits=30, decimal_places=20)
    segmen_jalan = models.ForeignKey(SegmenJalan, on_delete=models.SET_NULL, null=True, blank=True, related_name='kecelakaan_preprosesing')
    korban_meninggal = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_berat = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    korban_luka_ringan = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    kerugian_materi = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    desa = models.CharField(max_length=100)
    kecamatan = models.CharField(max_length=100)
    kabupaten_kota = models.CharField(max_length=100)
    keterangan = models.TextField(blank=True)
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres',
        help_text="Polres yang upload data preprocessing ini"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Data Kecelakaan Preprocessing'
        ordering = ['-tanggal', '-waktu']
    
    @property
    def total_korban(self):
        return self.korban_meninggal + self.korban_luka_berat + self.korban_luka_ringan

    def __str__(self):
        return f"Preproses {self.tanggal} - {self.kecamatan}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Otomatis assign segmen jalan terdekat
        if self.latitude and self.longitude and not self.segmen_jalan:
            self.find_closest_segment()
            # Jika find_closest_segment berhasil assign, simpan perubahan
            if self.segmen_jalan:
                super().save(update_fields=['segmen_jalan'])
    
    def find_closest_segment(self):
        """
        Temukan segmen jalan di mana titik kecelakaan berada TEPAT DI ANTARA
        titik awal dan titik akhir segmen. Menggunakan proyeksi perpendicular
        dari titik ke garis segmen untuk presisi maksimal.
        
        Algoritma:
        1. Cek apakah titik ada dalam bounding box segmen
        2. Hitung jarak perpendicular dari titik ke garis segmen
        3. Jika jarak <= tolerance, assign ke segmen tersebut
        """
        import math
        
        accident_lat = float(self.latitude)
        accident_lon = float(self.longitude)
        
        # Tolerance untuk jarak perpendicular: ~50 meter
        tolerance_km = 0.050
        
        best_match = None
        smallest_distance = float('inf')
        
        # Iterasi semua segmen untuk cek titik
        for segmen in SegmenJalan.objects.select_related('ruas_jalan').all():
            if not (segmen.lat_awal and segmen.lon_awal and segmen.lat_akhir and segmen.lon_akhir):
                continue
            
            s_lat_awal = float(segmen.lat_awal)
            s_lon_awal = float(segmen.lon_awal)
            s_lat_akhir = float(segmen.lat_akhir)
            s_lon_akhir = float(segmen.lon_akhir)
            
            # 1. Cek bounding box dulu (quick check)
            buffer = 0.001  # ~111 meter
            min_lat = min(s_lat_awal, s_lat_akhir) - buffer
            max_lat = max(s_lat_awal, s_lat_akhir) + buffer
            min_lon = min(s_lon_awal, s_lon_akhir) - buffer
            max_lon = max(s_lon_awal, s_lon_akhir) + buffer
            
            if not (min_lat <= accident_lat <= max_lat and min_lon <= accident_lon <= max_lon):
                continue
            
            # 2. Hitung jarak perpendicular dari titik ke garis segmen
            perp_distance = self._calculate_perpendicular_distance(
                accident_lat, accident_lon,
                s_lat_awal, s_lon_awal,
                s_lat_akhir, s_lon_akhir
            )
            
            # 3. Jika jarak perpendicular <= tolerance, ini adalah match
            if perp_distance is not None and perp_distance <= tolerance_km:
                if perp_distance < smallest_distance:
                    smallest_distance = perp_distance
                    best_match = segmen
        
        # Assign ke segmen terbaik jika ada match (tanpa save, dibiarkan parent save handle)
        if best_match:
            self.segmen_jalan = best_match
            print(f"✓ KecelakaanPreprosesing {self.id} → Segmen '{best_match.nama_segmen}' (jarak perp: {smallest_distance*1000:.1f}m)")
        else:
            print(f"⚠ KecelakaanPreprosesing {self.id}: Tidak ada segmen yang sesuai (tolerance: {tolerance_km*1000:.0f}m)")
    
    def _calculate_perpendicular_distance(self, lat, lon, lat1, lon1, lat2, lon2):
        """
        Hitung jarak PERPENDICULAR dari titik (lat, lon) ke garis segmen
        antara titik (lat1, lon1) dan (lat2, lon2).
        
        Mengembalikan:
        - Jarak dalam km jika titik proyeksi ada dalam segmen
        - None jika titik proyeksi diluar rentang segmen
        """
        import math
        
        # Convert ke radians
        lat = math.radians(lat)
        lon = math.radians(lon)
        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)
        
        R = 6371  # Earth radius in km
        
        # Angular distance dari start ke accident
        dLat = lat - lat1
        dLon = lon - lon1
        a = math.sin(dLat/2)**2 + math.cos(lat1) * math.cos(lat) * math.sin(dLon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        d13 = R * c
        
        # Bearing dari start ke end
        dLon12 = lon2 - lon1
        y = math.sin(dLon12) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon12)
        theta12 = math.atan2(y, x)
        
        # Bearing dari start ke accident
        dLon13 = lon - lon1
        y13 = math.sin(dLon13) * math.cos(lat)
        x13 = math.cos(lat1) * math.sin(lat) - math.sin(lat1) * math.cos(lat) * math.cos(dLon13)
        theta13 = math.atan2(y13, x13)
        
        # Cross-track distance (perpendicular distance)
        dXt = math.asin(math.sin(d13/R) * math.sin(theta13 - theta12))
        cross_track_distance_km = abs(dXt * R)
        
        # Along-track distance (untuk cek apakah dalam rentang)
        try:
            dAt = math.acos(max(-1, min(1, math.cos(d13/R) / abs(math.cos(dXt)))))
        except:
            dAt = 0
        
        # Jarak dari start ke end
        dLat12 = lat2 - lat1
        dLon12_calc = lon2 - lon1
        a12 = math.sin(dLat12/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon12_calc/2)**2
        c12 = 2 * math.asin(math.sqrt(a12))
        d12 = R * c12
        
        # Cek apakah proyeksi ada dalam rentang segmen
        # Dengan toleransi kecil di ujung-ujung segmen
        if -0.05 <= dAt <= (d12 + 0.05):
            return cross_track_distance_km
        else:
            # Proyeksi di luar segmen, jadi tidak cocok
            return None
    
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

class ClusterData(models.Model):
    """Model untuk data mentah yang digunakan dalam proses clustering"""
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
    tahun = models.IntegerField(null=True, blank=True, verbose_name="Tahun")
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Cluster Data"
        db_table = 'clusterdata'
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


class LakaMentah(models.Model):
    """Model untuk menyimpan data laka mentah secara literal dari Excel"""
    id = models.AutoField(primary_key=True)
    tanggal = models.TextField(null=True, blank=True)
    lap_pol = models.TextField(null=True, blank=True)
    uraian_kejadian = models.TextField(null=True, blank=True)
    tkp = models.TextField(null=True, blank=True)
    terlapor = models.TextField(null=True, blank=True)
    korban = models.TextField(null=True, blank=True)
    bb = models.TextField(null=True, blank=True)
    ket = models.TextField(null=True, blank=True)
    tahun = models.IntegerField(null=True, blank=True, verbose_name="Tahun")
    polres = models.ForeignKey(
        'Polres',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Polres'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Data Laka Mentah"
        ordering = ['-id']
        db_table = 'laka_mentah'

    def __str__(self):
        return f"Raw Laka #{self.id} - {self.lap_pol}"

