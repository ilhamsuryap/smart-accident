# ⚡ QUICK START - PERBAIKAN ASSIGNMENT KECELAKAAN

## Apa yang Berubah?

✅ **Sebelum**: Assignment kecelakaan ke segmen pakai jarak ke titik ujung (endpoint)  
✅ **Sesudah**: Assignment kecelakaan ke segmen pakai jarak garis lurus (perpendicular distance)

---

## 📌 Hasil Implementasi

### File yang dimodifikasi:

1. **`coreapp/models.py`** - Update `find_closest_segment()` & `_calculate_perpendicular_distance()` di 2 model:
   - `Kecelakaan`
   - `KecelakaanPreprosesing`

2. **`coreapp/management/commands/reassign_accidents_by_line.py`** (FILE BARU)
   - Command untuk re-assign data yang sudah ada
   - Support model selection, year filtering, custom tolerance

### Dokumentasi:

- **`DOKUMENTASI_PERBAIKAN_ASSIGNMENT.md`** - Dokumentasi lengkap dengan contoh & troubleshooting

---

## 🚀 Cara Pakai

### Untuk Data Baru (Upload):

Data akan **otomatis** di-assign menggunakan logika baru saat upload melalui form.

### Untuk Data Lama (Re-assign):

```bash
# Re-assign KecelakaanPreprosesing yang belum assigned
python manage.py reassign_accidents_by_line --model preprosesing

# Re-assign semua + force (termasuk yang sudah assigned)
python manage.py reassign_accidents_by_line --model all --force

# Custom tolerance (default 50 meter)
python manage.py reassign_accidents_by_line --tolerance 75

# Dengan recalculate Z-Score
python manage.py reassign_accidents_by_line --model all --force --recalc-zscore
```

---

## 🔧 Konfigurasi

**Default Tolerance**: 50 meter  
**Location**: `coreapp/models.py` - method `find_closest_segment()`

Ubah nilai ini untuk adjust sensitivity:

```python
tolerance_km = 0.050  # Change this (in km)
```

---

## ✨ Keunggulan

- ✅ Lebih akurat (perpendicular distance, bukan endpoint distance)
- ✅ Otomatis saat save/create (tidak perlu manual trigger)
- ✅ Dengan tolerance yang reasonable (50m default)
- ✅ Bisa handle multiple matches (ambil yang paling dekat)
- ✅ Detailed logging & progress tracking
- ✅ Support bulk re-processing

---

## 📊 Algoritma

```
1. Cek bounding box (~111m) → quick filter
2. Hitung jarak perpendicular ke garis segmen
3. Jika jarak ≤ 50m → ASSIGN
4. Jika multiple matches → ambil yang paling dekat
5. Jika tidak ada → UNASSIGNED
```

---

## 🧪 Test

```python
python manage.py shell

from coreapp.models import KecelakaanPreprosesing

k = KecelakaanPreprosesing.objects.first()
k.find_closest_segment()  # Trigger manual

print(k.segmen_jalan)  # Lihat hasil assignment
```

---

**Status**: ✅ Ready to use  
**Tested**: Perpendicular distance calculation & assignment logic  
**Performance**: Optimal untuk dataset normal (< 100k records)
