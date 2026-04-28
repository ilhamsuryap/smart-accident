# 📋 DOKUMENTASI PERBAIKAN SISTEM ASSIGNMENT KECELAKAAN KE SEGMEN

## 🎯 RINGKASAN PERUBAHAN

Sistem assignment kecelakaan ke segmen jalan telah diperbaiki dari metode berbasis **jarak ke endpoint** menjadi metode berbasis **perpendicular distance ke garis segmen**. Ini menghasilkan assignment yang lebih akurat berdasarkan koordinat titik.

---

## 🔄 PERUBAHAN TEKNIS

### 1. **Model: `Kecelakaan` dan `KecelakaanPreprosesing`**

#### Yang Berubah:

- **Sebelum**: Menggunakan bounding box sederhana atau distance ke endpoint
- **Sesudah**: Menggunakan perpendicular distance (jarak garis lurus) ke garis segmen

#### Algoritma Baru:

```python
1. Cek bounding box untuk quick filtering (~111 meter buffer)
2. Hitung jarak perpendicular dari titik kecelakaan ke garis segmen
3. Jika jarak <= tolerance (50 meter), assign ke segmen tersebut
4. Jika ada multiple matches, pilih yang paling dekat
```

#### Method Baru:

- `find_closest_segment()` - Mencari segmen terbaik berdasarkan perpendicular distance
- `_calculate_perpendicular_distance()` - Menghitung perpendicular distance menggunakan Haversine formula

#### Tolerance Pengaturan:

- **Default**: 50 meter (dapat disesuaikan)
- **Logika**: Jika titik kecelakaan berada dalam jarak perpendicular <= 50m dari garis segmen, dianggap cocok

---

## 🛠️ CARA MENGGUNAKAN

### A. For New Data (Upload)

Ketika upload data kecelakaan preprocessing, sistem akan **otomatis** assign ke segmen menggunakan logika baru:

```python
# Di views.py - upload_kecelakaan_preprosesing()
KecelakaanPreprosesing.objects.create(**create_data)  # Otomatis trigger find_closest_segment()
```

### B. Re-assign Existing Data

Gunakan management command baru untuk re-assign data yang sudah ada:

```bash
# Re-assign KecelakaanPreprosesing yang belum di-assign
python manage.py reassign_accidents_by_line --model preprosesing

# Re-assign semua model
python manage.py reassign_accidents_by_line --model all

# Force re-assign yang sudah di-assign sebelumnya
python manage.py reassign_accidents_by_line --model all --force

# Dengan tolerance custom (default 50m)
python manage.py reassign_accidents_by_line --model preprosesing --tolerance 75

# Dengan filter tahun tertentu
python manage.py reassign_accidents_by_line --model preprosesing --tahun 2024

# Dengan recalculate Z-Score otomatis
python manage.py reassign_accidents_by_line --model preprosesing --recalc-zscore
```

#### Opsi Command:

```
--model {kecelakaan|preprosesing|raw|all}  : Model mana yang di-process (default: preprosesing)
--tahun TAHUN                               : Filter tahun tertentu (opsional)
--tolerance METERS                          : Perpendicular distance tolerance dalam meter (default: 50)
--force                                     : Force re-assign yang sudah di-assign
--recalc-zscore                            : Recalculate Z-Score setelah assignment
```

---

## 📊 CONTOH SKENARIO

### Skenario 1: Kecelakaan tepat pada garis segmen

```
Segmen: Km 10-11 jalan Tol
Titik Awal: Lat -7.100, Lon 111.100
Titik Akhir: Lat -7.110, Lon 111.110

Kecelakaan: Lat -7.1045, Lon 111.1045
Perpendicular Distance: 25 meter ✓
Hasil: ASSIGN (25m < 50m tolerance)
```

### Skenario 2: Kecelakaan di luar garis segmen

```
Kecelakaan: Lat -7.200, Lon 111.200
Perpendicular Distance: 500 meter
Proyeksi: Diluar rentang segmen
Hasil: NOT ASSIGN (500m > 50m tolerance + diluar proyeksi)
```

### Skenario 3: Multiple matches

```
Kecelakaan: Lat -7.1045, Lon 111.1045
Match 1: Segmen A - perpendicular distance 30 meter
Match 2: Segmen B - perpendicular distance 45 meter
Hasil: ASSIGN ke Segmen A (paling dekat)
```

---

## 🔍 CARA MEMVERIFIKASI

### 1. Check Assignment di Database:

```sql
-- Cek berapa banyak yang sudah di-assign
SELECT COUNT(*) FROM coreapp_kecelakaanpreprosesing
WHERE segmen_jalan_id IS NOT NULL;

-- Cek yang belum di-assign
SELECT COUNT(*) FROM coreapp_kecelakaanpreprosesing
WHERE segmen_jalan_id IS NULL;

-- Cek distribution per segmen
SELECT segmen_jalan_id, COUNT(*)
FROM coreapp_kecelakaanpreprosesing
GROUP BY segmen_jalan_id;
```

### 2. Test Manual:

Buka terminal Django dan test:

```python
python manage.py shell

from coreapp.models import KecelakaanPreprosesing, SegmenJalan

# Get specific kecelakaan
k = KecelakaanPreprosesing.objects.get(id=1)
print(f"Lat: {k.latitude}, Lon: {k.longitude}")

# Trigger assignment
k.find_closest_segment()
print(f"Assigned to: {k.segmen_jalan}")

# View perpendicular distance manually
segmen = SegmenJalan.objects.first()
distance = k._calculate_perpendicular_distance(
    float(k.latitude), float(k.longitude),
    float(segmen.lat_awal), float(segmen.lon_awal),
    float(segmen.lat_akhir), float(segmen.lon_akhir)
)
print(f"Distance to {segmen.nama_segmen}: {distance} km")
```

---

## 📈 TUNING & CUSTOMIZATION

### Mengubah Tolerance

Jika ingin mengubah default tolerance (50 meter):

**File**: `coreapp/models.py`

```python
# Dalam method find_closest_segment()
tolerance_km = 0.050  # Change this (nilai dalam km)
```

Konversi referensi:

- 30 meter = 0.030 km
- 50 meter = 0.050 km (default)
- 75 meter = 0.075 km
- 100 meter = 0.100 km

### Performance Optimization

Jika ada data sangat banyak, bisa optimize dengan:

1. **Batch processing** (di management command):

```python
for kecelakaan in qs.iterator(chunk_size=1000):
    # Process
```

2. **Database indexing**:

```sql
CREATE INDEX idx_lat_lon ON coreapp_kecelakaanpreprosesing(latitude, longitude);
```

3. **Parallel processing** (future improvement):

```python
from multiprocessing.pool import ThreadPool
```

---

## 🐛 TROUBLESHOOTING

### Problem: Banyak kecelakaan yang unassigned

**Solusi**:

1. Cek apakah segmen memiliki titik awal/akhir yang lengkap

   ```sql
   SELECT * FROM coreapp_segmenjalan
   WHERE lat_awal IS NULL OR lon_awal IS NULL;
   ```

2. Coba ubah tolerance menjadi lebih besar

   ```bash
   python manage.py reassign_accidents_by_line --tolerance 100
   ```

3. Verifikasi koordinat kecelakaan valid (dalam rentang geografis)

### Problem: Assignment tidak konsisten

**Solusi**:

1. Jalankan dengan `--force` untuk re-assign
2. Bersihkan data yang salah terlebih dahulu
3. Cek apakah ada duplikat segmen

### Problem: Slow performance

**Solusi**:

1. Filter dengan tahun tertentu
2. Gunakan `--batch-size` jika ada di custom version
3. Kurangi jumlah segmen dengan segment filtering

---

## 📝 FILE YANG DIMODIFIKASI

1. **`coreapp/models.py`**
   - Updated `Kecelakaan.save()` & `find_closest_segment()`
   - Updated `Kecelakaan._calculate_perpendicular_distance()`
   - Updated `KecelakaanPreprosesing.save()` & `find_closest_segment()`
   - Updated `KecelakaanPreprosesing._calculate_perpendicular_distance()`
   - Removed old distance calculation methods

2. **`coreapp/management/commands/reassign_accidents_by_line.py`** (NEW)
   - Management command untuk re-assign existing data
   - Support multiple models & tahun filtering
   - Progress tracking & detailed reporting

---

## ✅ CHECKLIST IMPLEMENTASI

- [x] Update `Kecelakaan` model dengan perpendicular distance
- [x] Update `KecelakaanPreprosesing` model dengan perpendicular distance
- [x] Buat management command untuk re-assign
- [x] Add detailed logging & progress tracking
- [x] Support multi-model processing
- [x] Support year filtering
- [x] Support Z-Score recalculation
- [x] Documentation

---

## 🚀 NEXT STEPS

1. **Jalankan re-assignment untuk existing data**:

   ```bash
   python manage.py reassign_accidents_by_line --model all --force
   ```

2. **Verifikasi hasil**:
   - Cek dashboard untuk updated stats
   - Cek peta untuk marker placement yang akurat
   - Cek detail per segmen untuk kecelakaan count yang benar

3. **Monitor performance**:
   - Track assignment success rate
   - Monitor query performance
   - Document any edge cases

4. **Optional improvements**:
   - Add caching untuk segment coordinates
   - Add bulk update untuk better performance
   - Add API endpoint untuk check assignment distance

---

## 📚 REFERENSI

- **Haversine Formula**: Calculating distances on Earth's surface
- **Perpendicular Distance**: Distance from point to line segment
- **Great Circle Distance**: More accurate than Euclidean for geographic coordinates
- **Cross-track Distance**: https://en.wikipedia.org/wiki/Cross_track_error

---

**Dibuat**: 2026-04-22  
**Author**: Copilot Assistant  
**Status**: ✅ Ready for Production
