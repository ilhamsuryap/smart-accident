"""
Management command untuk re-assign kecelakaan ke segmen jalan berdasarkan proximity ke GARIS segmen,
bukan hanya ke titik awal/akhir. Menggunakan perpendicular distance (jarak garis lurus).

Fitur:
- Assign berdasarkan garis segmen, bukan titik endpoint
- Tolerance adjustable (default: 50 meter)
- Support untuk Kecelakaan, KecelakaanPreprosesing, dan KecelakaanRaw
- Force re-assign untuk data yang sudah assigned sebelumnya
"""
from django.core.management.base import BaseCommand, CommandError
from coreapp.models import Kecelakaan, KecelakaanPreprosesing, KecelakaanRaw, SegmenJalan, AnalisisZScore
import sys


class Command(BaseCommand):
    help = 'Re-assign kecelakaan to segmen based on perpendicular distance to segment line'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='preprosesing',
            choices=['kecelakaan', 'preprosesing', 'raw', 'all'],
            help='Model to process: kecelakaan, preprosesing, raw, or all (default: preprosesing)'
        )
        parser.add_argument(
            '--tahun',
            type=int,
            default=None,
            help='Filter by tahun (optional). If not specified, process all.'
        )
        parser.add_argument(
            '--tolerance',
            type=float,
            default=50,
            help='Perpendicular distance tolerance in meters (default: 50m). Typical: 30-100m.'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-assign even for data that already has segmen assigned.'
        )
        parser.add_argument(
            '--recalc-zscore',
            action='store_true',
            help='Recalculate Z-Score after assignment.'
        )

    def handle(self, *args, **options):
        model_choice = options.get('model', 'preprosesing')
        tahun = options.get('tahun')
        tolerance_meters = options.get('tolerance', 50)
        force_reassign = options.get('force', False)
        recalc_zscore = options.get('recalc_zscore', False)

        # Convert tolerance to km
        tolerance_km = tolerance_meters / 1000.0

        self.stdout.write(self.style.WARNING(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS("REASSIGN KECELAKAAN TO SEGMENTS BY LINE PROXIMITY"))
        self.stdout.write(self.style.WARNING(f"{'='*80}\n"))

        # Determine which models to process
        models_to_process = []
        if model_choice == 'all':
            models_to_process = [
                ('KecelakaanPreprosesing', KecelakaanPreprosesing),
                ('KecelakaanRaw', KecelakaanRaw),
                ('Kecelakaan', Kecelakaan),
            ]
        else:
            model_map = {
                'kecelakaan': ('Kecelakaan', Kecelakaan),
                'preprosesing': ('KecelakaanPreprosesing', KecelakaanPreprosesing),
                'raw': ('KecelakaanRaw', KecelakaanRaw),
            }
            models_to_process = [model_map[model_choice]]

        self.stdout.write(f"Models to process: {', '.join([m[0] for m in models_to_process])}")
        self.stdout.write(f"Tolerance: {tolerance_meters} meters ({tolerance_km} km)")
        self.stdout.write(f"Force re-assign: {force_reassign}")
        if tahun:
            self.stdout.write(f"Filter tahun: {tahun}")
        self.stdout.write("")

        # Get all segmen once
        all_segmen = list(SegmenJalan.objects.select_related('ruas_jalan').all())
        if not all_segmen:
            raise CommandError("❌ Tidak ada segment ditemukan di database!")

        self.stdout.write(f"✓ Loaded {len(all_segmen)} segments from database\n")

        # Process each model
        total_processed = 0
        total_assigned = 0
        total_unassigned = 0
        affected_years = set()

        for model_name, model_class in models_to_process:
            self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
            self.stdout.write(self.style.SUCCESS(f"Processing {model_name}"))
            self.stdout.write(self.style.SUCCESS(f"{'='*60}"))

            # Filter queryset
            qs = model_class.objects.all()
            if tahun:
                qs = qs.filter(tanggal__year=tahun)
            
            if not force_reassign:
                qs = qs.filter(segmen_jalan__isnull=True)

            total_count = qs.count()
            
            if total_count == 0:
                self.stdout.write(f"ℹ No records to process")
                continue

            self.stdout.write(f"Total records to process: {total_count}\n")

            assigned = 0
            unassigned = 0

            for idx, kecelakaan in enumerate(qs, 1):
                # Show progress
                progress = f"[{idx:4d}/{total_count:4d}]"
                
                # Store old assignment
                old_segmen = kecelakaan.segmen_jalan

                # Find closest segment using perpendicular distance
                best_match = None
                smallest_distance = float('inf')

                accident_lat = float(kecelakaan.latitude)
                accident_lon = float(kecelakaan.longitude)

                for segmen in all_segmen:
                    if not (segmen.lat_awal and segmen.lon_awal and segmen.lat_akhir and segmen.lon_akhir):
                        continue

                    s_lat_awal = float(segmen.lat_awal)
                    s_lon_awal = float(segmen.lon_awal)
                    s_lat_akhir = float(segmen.lat_akhir)
                    s_lon_akhir = float(segmen.lon_akhir)

                    # Quick bounding box check
                    buffer = 0.001  # ~111 meter
                    min_lat = min(s_lat_awal, s_lat_akhir) - buffer
                    max_lat = max(s_lat_awal, s_lat_akhir) + buffer
                    min_lon = min(s_lon_awal, s_lon_akhir) - buffer
                    max_lon = max(s_lon_awal, s_lon_akhir) + buffer

                    if not (min_lat <= accident_lat <= max_lat and min_lon <= accident_lon <= max_lon):
                        continue

                    # Calculate perpendicular distance
                    perp_distance = self._calculate_perpendicular_distance(
                        accident_lat, accident_lon,
                        s_lat_awal, s_lon_awal,
                        s_lat_akhir, s_lon_akhir
                    )

                    # Check if within tolerance
                    if perp_distance is not None and perp_distance <= tolerance_km:
                        if perp_distance < smallest_distance:
                            smallest_distance = perp_distance
                            best_match = segmen

                # Assign atau update
                if best_match:
                    kecelakaan.segmen_jalan = best_match
                    kecelakaan.save()
                    
                    if old_segmen != best_match:
                        status = "→" if old_segmen is None else "✓"
                        self.stdout.write(
                            f"{progress} {status} {best_match.nama_segmen} "
                            f"(dist: {smallest_distance*1000:.1f}m)"
                        )
                    assigned += 1
                    affected_years.add(kecelakaan.tanggal.year)
                else:
                    kecelakaan.segmen_jalan = None
                    kecelakaan.save()
                    
                    self.stdout.write(f"{progress} ✗ Tidak ada segmen (luar tolerance)")
                    unassigned += 1

            self.stdout.write(f"\n✓ Assigned: {assigned}")
            self.stdout.write(f"✗ Unassigned: {unassigned}")

            total_processed += total_count
            total_assigned += assigned
            total_unassigned += unassigned

        # Final summary
        self.stdout.write(self.style.WARNING(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(self.style.WARNING(f"{'='*80}"))
        self.stdout.write(f"Total processed: {total_processed}")
        self.stdout.write(f"Total assigned: {total_assigned}")
        self.stdout.write(f"Total unassigned: {total_unassigned}")
        self.stdout.write(f"Affected years: {sorted(affected_years)}")

        # Recalculate Z-Score if requested
        if recalc_zscore and affected_years:
            self.stdout.write(f"\n🔄 Recalculating Z-Score for years: {sorted(affected_years)}")
            for tahun_iter in sorted(affected_years):
                try:
                    AnalisisZScore.recalculate_zscore(tahun_iter)
                    self.stdout.write(f"   ✓ Z-Score recalculated for {tahun_iter}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ✗ Error for {tahun_iter}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("\n✓ Done!\n"))

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
        a = math.sin(dLat / 2) ** 2 + math.cos(lat1) * math.cos(lat) * math.sin(dLon / 2) ** 2
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
        dXt = math.asin(math.sin(d13 / R) * math.sin(theta13 - theta12))
        cross_track_distance_km = abs(dXt * R)

        # Along-track distance (untuk cek apakah dalam rentang)
        try:
            dAt = math.acos(max(-1, min(1, math.cos(d13 / R) / abs(math.cos(dXt)))))
        except:
            dAt = 0

        # Jarak dari start ke end
        dLat12 = lat2 - lat1
        dLon12_calc = lon2 - lon1
        a12 = math.sin(dLat12 / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon12_calc / 2) ** 2
        c12 = 2 * math.asin(math.sqrt(a12))
        d12 = R * c12

        # Cek apakah proyeksi ada dalam rentang segmen
        # Dengan toleransi kecil di ujung-ujung segmen
        if -0.05 <= dAt <= (d12 + 0.05):
            return cross_track_distance_km
        else:
            # Proyeksi di luar segmen, jadi tidak cocok
            return None
