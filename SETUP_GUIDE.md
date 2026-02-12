# SETUP CHECKLIST - Smart Accident GIS Application

## ✅ Tahap 1: Persiapan Environment

- [x] Python 3.8+ terinstall
- [x] MySQL Server running
- [x] Virtual Environment dibuat
- [x] Virtual Environment diaktifkan

## ✅ Tahap 2: Instalasi GDAL (Windows)

**IMPORTANT untuk Windows:**

1. Download OSGeo4W dari https://trac.osgeo.org/osgeo4w/
2. Run installer sebagai Administrator
3. Pilih instalasi dengan opsi:
   - GDAL
   - Proj
   - GEOS
4. Catat lokasi instalasi (default: C:\OSGeo4W)

## ✅ Tahap 3: Konfigurasi Database

```bash
# Login ke MySQL
mysql -u root -p

# Jalankan commands berikut:
CREATE DATABASE smart_accident_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'smart_user'@'localhost' IDENTIFIED BY 'password123';
GRANT ALL PRIVILEGES ON smart_accident_db.* TO 'smart_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## ✅ Tahap 4: Setup Project Django

```bash
# 1. Masuk folder project
cd SmartAccident

# 2. Buat virtual environment
python -m venv venv

# 3. Aktivasi (Windows)
venv\Scripts\activate

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install requirements
pip install -r requirements.txt
```

## ✅ Tahap 5: Konfigurasi Environment

```bash
# 1. Copy .env.example ke .env
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows

# 2. Edit .env dengan text editor
# Isi dengan:
DB_NAME=smart_accident_db
DB_USER=smart_user
DB_PASSWORD=password123
DB_HOST=localhost
DB_PORT=3306
DEBUG=True
```

## ✅ Tahap 6: Database Migrations

```bash
# 1. Buat migrations dari models
python manage.py makemigrations

# 2. Jalankan migrations
python manage.py migrate

# 3. Create superuser (admin account)
python manage.py createsuperuser
# Ikuti prompt untuk:
# - Username: admin (atau nama lain)
# - Email: admin@example.com
# - Password: (buat password yang aman)
```

## ✅ Tahap 7: Jalankan Server

```bash
python manage.py runserver
```

Server akan berjalan di: http://localhost:8000

## ✅ Tahap 8: Akses Aplikasi

### URL Utama:

- **Home/Dashboard:** http://localhost:8000
- **Login:** http://localhost:8000/login
- **Ruas Jalan:** http://localhost:8000/ruas-jalan/
- **Kecelakaan:** http://localhost:8000/kecelakaan/
- **Peta Interaktif:** http://localhost:8000/peta/
- **Analisis:** http://localhost:8000/analisis/
- **Admin:** http://localhost:8000/admin

## 📋 Struktur Folder Project

```
SmartAccident/
├── SmartAccident/          # Project settings folder
│   ├── settings.py         # ✅ Sudah dikonfigurasi
│   ├── urls.py             # ✅ Sudah dikonfigurasi
│   ├── wsgi.py
│   └── asgi.py
├── coreapp/                # Main app
│   ├── models.py           # ✅ Semua models dibuat
│   ├── views.py            # ✅ Semua views dibuat
│   ├── forms.py            # ✅ Semua forms dibuat
│   ├── urls.py             # ✅ URL routing dibuat
│   ├── admin.py            # ✅ Admin interface
│   ├── apps.py             # ✅ App config
│   └── management/         # Custom commands
├── templates/              # HTML templates
│   ├── base.html           # ✅ Base template
│   ├── registration/       # ✅ Auth templates
│   │   ├── login.html
│   │   └── register.html
│   └── coreapp/            # ✅ App templates
│       ├── dashboard.html
│       ├── ruas_jalan/
│       ├── kecelakaan/
│       ├── map/
│       └── analisis/
├── static/                 # Static files
│   ├── css/
│   ├── js/
│   └── img/
├── manage.py
├── requirements.txt        # ✅ Sudah updated
├── README.md               # ✅ Dokumentasi lengkap
└── .env.example            # ✅ Template config

```

## 🎯 Quick Start Data

### 1. Tambah Ruas Jalan Test

Buka Admin (http://localhost:8000/admin) atau gunakan UI:

**Contoh Data:**

- Nama: Jalan Ahmad Yani
- Jenis: Arteri
- Wilayah: Samarinda
- Panjang: 15 km

### 2. Generate Segmen

Klik "Generate Segmen Otomatis" - akan membuat 15 segmen per 1 km

### 3. Tambah Data Kecelakaan

**Contoh:**

- Tanggal: 2025-01-15
- Waktu: 14:30
- Latitude: -0.4917
- Longitude: 117.1450
- Desa: Sempaja
- Kecamatan: Samarinda Ilir
- Kabupaten: Samarinda
- Korban Meninggal: 1
- Korban Luka Berat: 2
- Korban Luka Ringan: 3

### 4. Jalankan Analisis

Di halaman Analisis, klik "Hitung Ulang Analisis Tahun 2025"

### 5. Lihat Peta

Buka Peta Interaktif dan pilih tahun untuk melihat visualisasi

## 🔧 Troubleshooting

### Error 1: "ModuleNotFoundError: No module named 'django'"

**Solusi:**

```bash
pip install -r requirements.txt
```

### Error 2: "django.core.exceptions.ImproperlyConfigured: GIS-enabled database backend required"

**Solusi:**

- Pastikan database engine di settings.py adalah `django.contrib.gis.db.backends.mysql`
- Pastikan migrations sudah dijalankan

### Error 3: "GDAL library not found" (Windows)

**Solusi:**

```python
# Tambahkan ke settings.py atau .env
GDAL_LIBRARY_PATH = r'C:\OSGeo4W\bin\gdal304.dll'
GEOS_LIBRARY_PATH = r'C:\OSGeo4W\bin\geos_c.dll'
PROJ_LIB = r'C:\OSGeo4W\share\proj'
```

### Error 4: "Can't connect to MySQL server"

**Solusi:**

1. Pastikan MySQL server running
2. Cek username/password di .env
3. Cek database sudah dibuat

### Error 5: "TemplateDoesNotExist"

**Solusi:**

```bash
# Pastikan folder templates ada di root project
# Check TEMPLATES di settings.py
python manage.py runserver --reload
```

## 📊 Model Relationships

```
RuasJalan (1) ──── (Many) SegmenJalan
                      │
                      └── (Many) Kecelakaan ──── RekapSegmen
                                 │
                                 └── AnalisisZScore
```

## 🔐 Fitur Keamanan

- [x] User authentication dengan Django Built-in
- [x] Admin/User role separation
- [x] CSRF protection
- [x] SQL injection prevention
- [x] Password hashing

## 📱 Responsive Design

- [x] Mobile-friendly UI
- [x] Bootstrap 5
- [x] Leaflet map responsive
- [x] Touch-friendly buttons

## ⚡ Performance Tips

1. **Database Indexing:**
   - Segmen jalan indexed by ruas_jalan
   - Kecelakaan indexed by tanggal, segmen_jalan
   - AnalisisZScore indexed by tahun, kategori

2. **Query Optimization:**
   - Gunakan select_related() untuk FK
   - Gunakan prefetch_related() untuk reverse FK
   - Pagination untuk list views

3. **Caching:**
   - Statistik dihitung on-demand
   - Hasil disimpan di RekapSegmen untuk reuse

## 📚 Dokumentasi API

Semua API endpoints sudah documented di README.md

## 🚀 Deployment

Untuk production:

1. Set `DEBUG = False` di settings.py
2. Update `ALLOWED_HOSTS`
3. Setup database yang reliable
4. Gunakan web server (Gunicorn, uWSGI)
5. Setup SSL/HTTPS
6. Collect static files: `python manage.py collectstatic`

## ✨ Features Summary

✅ **CRUD Operations**

- Ruas Jalan
- Segmen Jalan (auto-generated)
- Kecelakaan
- Rekapitulasi per segmen
- Analisis Z-Score

✅ **GIS Features**

- Spatial indexing
- LineString untuk ruas/segmen
- Point untuk kecelakaan
- Distance calculations
- Interactive maps

✅ **Analytics**

- Z-Score calculation
- 5-category classification
- Statistical summaries
- Time-series analysis

✅ **User Interface**

- Responsive design
- Interactive maps
- Real-time search
- Admin interface

✅ **API**

- GeoJSON endpoints
- Statistics endpoints
- RESTful design

---

## 📞 Support

Untuk masalah atau pertanyaan:

1. Check README.md
2. Check django documentation
3. Check GeoDjango documentation
4. Check Leaflet.js documentation

**Setup selesai! Happy coding! 🎉**
