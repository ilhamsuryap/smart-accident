# Smart Accident - Sistem Pemetaan dan Analisis Kerawanan Kecelakaan Lalu Lintas

Aplikasi Django berbasis GIS untuk pemetaan dan analisis tingkat kerawanan kecelakaan lalu lintas menggunakan Z-Score analysis.

## Fitur Utama

- **Manajemen Data Ruas Jalan** - CRUD data ruas jalan dengan geometri LineString
- **Segmentasi Otomatis** - Pembagian ruas jalan menjadi segmen per 1 km secara otomatis
- **Manajemen Data Kecelakaan** - Pencatatan data kecelakaan dengan koordinat geografis
- **Analisis Z-Score** - Perhitungan tingkat kerawanan berbasis Z-Score statistics
- **Kategorisasi Kerawanan** - Pengelompokan ke 5 kategori (Sangat Tinggi hingga Sangat Rendah)
- **Peta Interaktif** - Visualisasi data menggunakan Leaflet.js
- **Autentikasi User** - Sistem login untuk admin dan user biasa
- **API REST** - API untuk akses data GeoJSON dan statistik

## Teknologi

- **Backend:** Django 6.0+
- **Database:** MySQL (dengan GeoDjango)
- **Frontend Map:** Leaflet.js
- **Autentikasi:** Django Built-in Auth
- **API:** Django REST Framework
- **GIS:** GeoDjango dengan GDAL

## Prerequisites

- Python 3.8+
- MySQL Server
- OSGeo4W atau GDAL Library (untuk Windows)
- Virtual Environment

## Instalasi

### 1. Setup Database MySQL

```bash
mysql -u root -p
CREATE DATABASE smart_accident_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'smart_user'@'localhost' IDENTIFIED BY 'password_anda';
GRANT ALL PRIVILEGES ON smart_accident_db.* TO 'smart_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 2. Setup GDAL (Windows)

Download dan install OSGeo4W dari https://trac.osgeo.org/osgeo4w/

Pilih instalasi dengan GDAL dan Proj libraries.

### 3. Clone Repository dan Setup Virtual Environment

```bash
cd SmartAccident
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Konfigurasi Environment

Copy `.env.example` ke `.env` dan sesuaikan konfigurasi:

```bash
cp .env.example .env
```

Edit `.env`:

```
DB_NAME=smart_accident_db
DB_USER=smart_user
DB_PASSWORD=password_anda
DB_HOST=localhost
DB_PORT=3306
```

### 6. Migrasi Database

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Buat Superuser (Admin)

```bash
python manage.py createsuperuser
```

### 8. Jalankan Development Server

```bash
python manage.py runserver
```

Akses aplikasi di: http://localhost:8000

## Penggunaan

### 1. Login

- Buka http://localhost:8000
- Klik Login
- Gunakan akun superuser yang telah dibuat

### 2. Menambah Ruas Jalan

1. Navigasi ke **Ruas Jalan**
2. Klik **Tambah Ruas Jalan**
3. Isi form:
   - Nama Ruas
   - Jenis Jalan (Tol, Arteri, Kolektor, Lokal, Desa)
   - Wilayah
   - Panjang (km)
4. Simpan

### 3. Generate Segmen Jalan

1. Di halaman detail ruas jalan, klik **Generate Segmen Otomatis**
2. Sistem akan membagi ruas menjadi segmen per 1 km

### 4. Menambah Data Kecelakaan

1. Navigasi ke **Data Kecelakaan**
2. Klik **Tambah Data Kecelakaan**
3. Isi form dengan data lengkap:
   - Tanggal & Waktu
   - Latitude & Longitude (akan auto-convert ke POINT geometry)
   - Lokasi administratif (Desa, Kecamatan, Kabupaten)
   - Data korban (Meninggal, Luka Berat, Luka Ringan)
   - Kerugian materi
   - Keterangan
4. Sistem akan otomatis mencari segmen jalan terdekat

### 5. Menjalankan Analisis Z-Score

1. Navigasi ke **Analisis**
2. Pilih tahun yang ingin dianalisis
3. Klik **Hitung Ulang Analisis**
4. Sistem akan menghitung:
   - Rekapitulasi kecelakaan per segmen
   - Z-Score untuk setiap segmen
   - Kategorisasi tingkat kerawanan

### 6. Melihat Peta Interaktif

1. Navigasi ke **Peta Interaktif**
2. Pilih tahun
3. Peta akan menampilkan:
   - Segmen jalan berwarna berdasarkan kategori Z-Score
   - Titik lokasi kecelakaan
   - Statistik kategori di sidebar

## Struktur Model Database

### RuasJalan

- id (INT)
- nama_ruas (VARCHAR 100)
- jenis_jalan (ENUM)
- wilayah (VARCHAR 100)
- panjang_km (DECIMAL)
- geom (LineString, SRID 4326)
- created_at, updated_at (TIMESTAMP)

### SegmenJalan

- id (INT)
- ruas_jalan (FK)
- km_awal (DECIMAL)
- km_akhir (DECIMAL)
- panjang_segmen (DECIMAL)
- geom (LineString, SRID 4326)
- created_at, updated_at (TIMESTAMP)

### Kecelakaan

- id (INT)
- tanggal (DATE)
- waktu (TIME)
- latitude (DECIMAL 9,6)
- longitude (DECIMAL 9,6)
- geom (Point, SRID 4326)
- segmen_jalan (FK)
- jumlah_kecelakaan (INT)
- korban_meninggal (INT)
- korban_luka_berat (INT)
- korban_luka_ringan (INT)
- kerugian_materi (DECIMAL)
- desa, kecamatan, kabupaten_kota (VARCHAR)
- keterangan (TEXT)
- created_at, updated_at (TIMESTAMP)

### RekapSegmen

- id (INT)
- segmen_jalan (FK)
- jumlah_kecelakaan (INT)
- total_korban (INT)
- total_meninggal, total_luka_berat, total_luka_ringan (INT)
- total_kerugian (DECIMAL)
- periode_tahun (INT)
- created_at, updated_at (TIMESTAMP)

### AnalisisZScore

- id (INT)
- segmen_jalan (FK)
- nilai_zscore (DECIMAL 5,3)
- kategori (ENUM: sangat_tinggi, tinggi, sedang, rendah, sangat_rendah)
- tahun (INT)
- created_at, updated_at (TIMESTAMP)

## API Endpoints

### 1. Segmen GeoJSON

```
GET /api/segmen/geojson/?tahun=2025
```

Mengembalikan GeoJSON FeatureCollection dengan LineString segmen jalan dan kategori Z-Score.

**Response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 1,
      "properties": {
        "segmen_id": 1,
        "ruas_nama": "Jalan Sudirman",
        "km_awal": 0,
        "km_akhir": 1,
        "kategori": "sangat_tinggi",
        "zscore": 2.5,
        "color": "#d32f2f"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [...]
      }
    }
  ]
}
```

### 2. Kecelakaan GeoJSON

```
GET /api/kecelakaan/geojson/?tahun=2025
```

Mengembalikan GeoJSON FeatureCollection dengan Point lokasi kecelakaan.

### 3. Statistik Analisis

```
GET /api/analisis/statistik/?tahun=2025
```

Mengembalikan statistik jumlah segmen per kategori.

**Response:**

```json
{
  "tahun": 2025,
  "total_segmen": 150,
  "kategori": {
    "sangat_tinggi": 10,
    "tinggi": 25,
    "sedang": 40,
    "rendah": 45,
    "sangat_rendah": 30
  }
}
```

## Rumus Z-Score

Z-Score dihitung untuk setiap segmen berdasarkan jumlah kecelakaan:

```
Z = (X - μ) / σ

Dimana:
- X = Jumlah kecelakaan di segmen
- μ = Rata-rata jumlah kecelakaan semua segmen
- σ = Standar deviasi jumlah kecelakaan
```

### Kategorisasi:

- **Sangat Tinggi:** Z > 1.5
- **Tinggi:** 0.5 < Z ≤ 1.5
- **Sedang:** -0.5 < Z ≤ 0.5
- **Rendah:** -1.5 < Z ≤ -0.5
- **Sangat Rendah:** Z ≤ -1.5

## Admin Interface

Akses admin Django di: http://localhost:8000/admin

Fitur admin:

- Manajemen penuh data RuasJalan, SegmenJalan, Kecelakaan
- Viewing RekapSegmen dan AnalisisZScore
- Map view untuk data spasial

## Troubleshooting

### Error GDAL/GEOS tidak ditemukan (Windows)

1. Install OSGeo4W
2. Tambahkan ke PATH atau konfigurasi di settings.py:

```python
import os
os.environ['GDAL_LIBRARY_PATH'] = r'C:\OSGeo4W\bin\gdal304.dll'
os.environ['GEOS_LIBRARY_PATH'] = r'C:\OSGeo4W\bin\geos_c.dll'
```

### Error Database Connection

1. Pastikan MySQL running
2. Cek credentials di .env
3. Pastikan database sudah dibuat

### Error Module Not Found

```bash
pip install -r requirements.txt
```

## Development

### Membuat Migrasi

```bash
python manage.py makemigrations
python manage.py migrate
```

### Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Testing

```bash
python manage.py test coreapp
```

## Production Deployment

1. Set DEBUG = False di settings.py
2. Konfigurasi ALLOWED_HOSTS
3. Gunakan production WSGI server (Gunicorn, uWSGI)
4. Setup database dengan proper credentials
5. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

## Kontribusi

Untuk kontribusi atau laporan bug, silakan buat issue di repository.

## Lisensi

MIT License - Copyright (c) 2025

## Support

Untuk pertanyaan atau support, hubungi tim development.

---

**Catatan:** Pastikan semua data koordinat menggunakan WGS84 (SRID 4326) untuk konsistensi geographic data.
