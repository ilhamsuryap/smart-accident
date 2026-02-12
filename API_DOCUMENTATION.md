# Smart Accident API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Semua endpoints memerlukan user login.

## Endpoints

### 1. Segmen Jalan GeoJSON API

**Endpoint:** `GET /api/segmen/geojson/`

**Parameters:**

- `tahun` (optional, int): Tahun untuk filter analisis Z-Score. Default: tahun saat ini

**Description:**
Mengembalikan GeoJSON FeatureCollection dengan LineString segmen jalan dan informasi kategori Z-Score kerawanan.

**Example Request:**

```bash
curl "http://localhost:8000/api/segmen/geojson/?tahun=2025" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Example Response:**

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
        "km_awal": 0.0,
        "km_akhir": 1.0,
        "kategori": "sangat_tinggi",
        "zscore": 2.543,
        "color": "#d32f2f",
        "url": "/analisis/segmen/1/"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [106.8241, -6.2088],
          [106.8251, -6.2098],
          [106.8261, -6.2108]
        ]
      }
    },
    {
      "type": "Feature",
      "id": 2,
      "properties": {
        "segmen_id": 2,
        "ruas_nama": "Jalan Sudirman",
        "km_awal": 1.0,
        "km_akhir": 2.0,
        "kategori": "tinggi",
        "zscore": 1.234,
        "color": "#f57c00",
        "url": "/analisis/segmen/2/"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [106.8261, -6.2108],
          [106.8271, -6.2118]
        ]
      }
    }
  ]
}
```

**Status Codes:**

- `200`: Success
- `401`: Unauthorized
- `404`: Data not found

---

### 2. Kecelakaan GeoJSON API

**Endpoint:** `GET /api/kecelakaan/geojson/`

**Parameters:**

- `tahun` (optional, int): Tahun untuk filter data kecelakaan. Default: tahun saat ini

**Description:**
Mengembalikan GeoJSON FeatureCollection dengan Point lokasi kecelakaan dan informasi detail korban.

**Example Request:**

```bash
curl "http://localhost:8000/api/kecelakaan/geojson/?tahun=2025" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Example Response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 1,
      "properties": {
        "kecelakaan_id": 1,
        "tanggal": "2025-01-15",
        "waktu": "14:30:00",
        "lokasi": "Sempaja, Samarinda Ilir",
        "korban_meninggal": 1,
        "korban_luka_berat": 2,
        "korban_luka_ringan": 3,
        "total_korban": 6,
        "kerugian": 15000000.0,
        "url": "/kecelakaan/1/"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [117.145, -0.4917]
      }
    },
    {
      "type": "Feature",
      "id": 2,
      "properties": {
        "kecelakaan_id": 2,
        "tanggal": "2025-01-16",
        "waktu": "09:15:00",
        "lokasi": "Loa Buah, Samarinda Ulu",
        "korban_meninggal": 0,
        "korban_luka_berat": 1,
        "korban_luka_ringan": 2,
        "total_korban": 3,
        "kerugian": 8500000.0,
        "url": "/kecelakaan/2/"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [117.1234, -0.5012]
      }
    }
  ]
}
```

**Status Codes:**

- `200`: Success
- `401`: Unauthorized

---

### 3. Statistik Analisis API

**Endpoint:** `GET /api/analisis/statistik/`

**Parameters:**

- `tahun` (optional, int): Tahun untuk statistik. Default: tahun saat ini

**Description:**
Mengembalikan statistik jumlah segmen per kategori Z-Score.

**Example Request:**

```bash
curl "http://localhost:8000/api/analisis/statistik/?tahun=2025" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Example Response:**

```json
{
  "tahun": 2025,
  "total_segmen": 150,
  "kategori": {
    "sangat_tinggi": 12,
    "tinggi": 28,
    "sedang": 45,
    "rendah": 38,
    "sangat_rendah": 27
  }
}
```

**Status Codes:**

- `200`: Success
- `401`: Unauthorized

---

## Data Models

### Kategori Z-Score

| Kategori      | Range Z-Score   | Warna                | Tingkat Kerawanan           |
| ------------- | --------------- | -------------------- | --------------------------- |
| Sangat Tinggi | Z > 1.5         | #d32f2f (Merah)      | Rawan Tingkat Sangat Tinggi |
| Tinggi        | 0.5 < Z ≤ 1.5   | #f57c00 (Oranye)     | Rawan Tingkat Tinggi        |
| Sedang        | -0.5 < Z ≤ 0.5  | #fbc02d (Kuning)     | Rawan Tingkat Sedang        |
| Rendah        | -1.5 < Z ≤ -0.5 | #7cb342 (Hijau Muda) | Rawan Tingkat Rendah        |
| Sangat Rendah | Z ≤ -1.5        | #388e3c (Hijau)      | Rawan Tingkat Sangat Rendah |

### Rumus Z-Score

```
Z = (X - μ) / σ

Dimana:
X = Jumlah kecelakaan di segmen
μ = Rata-rata jumlah kecelakaan semua segmen
σ = Standar deviasi jumlah kecelakaan
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found

```json
{
  "detail": "Not found."
}
```

### 500 Server Error

```json
{
  "error": "Internal server error"
}
```

---

## Example Usage (JavaScript/Axios)

### Fetch Segmen GeoJSON

```javascript
const axios = require("axios");

async function getSegmenData(tahun = 2025) {
  try {
    const response = await axios.get("/api/segmen/geojson/", {
      params: { tahun: tahun },
    });

    console.log("Segmen Data:", response.data);
    // Gunakan untuk rendering di Leaflet
    const geojsonLayer = L.geoJSON(response.data, {
      style: function (feature) {
        return {
          color: feature.properties.color,
          weight: 3,
          opacity: 0.8,
        };
      },
    }).addTo(map);
  } catch (error) {
    console.error("Error fetching data:", error);
  }
}
```

### Fetch Kecelakaan GeoJSON

```javascript
async function getKecelakaanData(tahun = 2025) {
  try {
    const response = await axios.get("/api/kecelakaan/geojson/", {
      params: { tahun: tahun },
    });

    console.log("Kecelakaan Data:", response.data);

    const markerLayer = L.geoJSON(response.data, {
      pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
          radius: 6,
          fillColor: "#d32f2f",
          color: "#fff",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.8,
        });
      },
      onEachFeature: function (feature, layer) {
        const props = feature.properties;
        const popup = `
          <strong>${props.lokasi}</strong><br>
          Tanggal: ${props.tanggal}<br>
          Korban Meninggal: ${props.korban_meninggal}
        `;
        layer.bindPopup(popup);
      },
    }).addTo(map);
  } catch (error) {
    console.error("Error fetching data:", error);
  }
}
```

### Fetch Statistik

```javascript
async function getStatistik(tahun = 2025) {
  try {
    const response = await axios.get("/api/analisis/statistik/", {
      params: { tahun: tahun },
    });

    const stats = response.data;
    console.log(`Total Segmen: ${stats.total_segmen}`);
    console.log(`Sangat Tinggi: ${stats.kategori.sangat_tinggi}`);
    console.log(`Tinggi: ${stats.kategori.tinggi}`);
  } catch (error) {
    console.error("Error fetching statistics:", error);
  }
}
```

---

## Rate Limiting

Tidak ada rate limiting untuk development. Untuk production, implementasi rate limiting.

---

## CORS

CORS diaktifkan via `django-cors-headers`. Konfigurasi di settings.py:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",
    "https://yourdomain.com"
]
```

---

## Best Practices

1. **Always include tahun parameter** untuk hasil yang akurat
2. **Cache hasil GeoJSON** di client untuk performa lebih baik
3. **Handle error responses** dengan graceful
4. **Update data secara berkala** setelah menambah data baru
5. **Gunakan feature bounds** untuk membatasi peta view

---

## Pagination

List views menggunakan Django REST Framework pagination:

- Default: 100 items per page
- Parameter: `?page=2`

---

## Filtering

GeoJSON endpoints menggunakan query parameters untuk filtering:

- `tahun`: Filter by year
- Untuk filtering lebih lanjut, gunakan admin interface

---

## Versioning

API saat ini: **v1** (tidak ada prefix di URL)

Untuk future versions, akan menggunakan:

```
/api/v2/segmen/geojson/
/api/v2/kecelakaan/geojson/
```

---

## Changelog

### Version 1.0 (2025-01-25)

- Initial API release
- 3 main endpoints
- GeoJSON support
- Z-Score statistics

---

## Support

Untuk masalah atau pertanyaan:

- Baca dokumentasi di `/admin/`
- Check Django REST Framework docs
- Check Leaflet.js docs

---

**Last Updated:** 2025-01-25
