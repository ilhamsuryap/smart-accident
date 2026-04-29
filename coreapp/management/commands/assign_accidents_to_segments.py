"""
Management command untuk assign kecelakaan ke segmen jalan terdekat berdasarkan proximity
Setiap kecelakaan akan diassign ke segmen yang paling dekat (threshold: 5 km)
"""
from django.core.management.base import BaseCommand, CommandError
from coreapp.models import Kecelakaan, SegmenJalan, AnalisisZScore
from geopy.distance import geodesic
import sys


class Command(BaseCommand):
    help = 'Assign kecelakaan data to nearest segmen jalan based on lat/lon proximity distance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tahun',
            type=int,
            default=None,
            help='Filter kecelakaan by tahun (optional). If not specified, process all kecelakaan.'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=5.0,
            help='Distance threshold in kilometers (default: 5.0). Kecelakaan beyond this distance won\'t be assigned.'
        )
        parser.add_argument(
            '--recalc-zscore',
            action='store_true',
            help='Recalculate Z-Score for all affected years after assignment.'
        )

    def handle(self, *args, **options):
        tahun = options.get('tahun')
        threshold = options.get('threshold', 5.0)
        recalc_zscore = options.get('recalc_zscore', False)

        self.stdout.write(self.style.WARNING(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS("ASSIGN KECELAKAAN TO SEGMENTS BY PROXIMITY"))
        self.stdout.write(self.style.WARNING(f"{'='*80}\n"))
        
        # Filter kecelakaan
        kecelakaan_qs = Kecelakaan.objects.select_related('segmen_jalan')
        if tahun:
            kecelakaan_qs = kecelakaan_qs.filter(tanggal__year=tahun)
            self.stdout.write(f"Filter: Tahun {tahun}")
        
        total_count = kecelakaan_qs.count()
        self.stdout.write(f"Total kecelakaan to process: {total_count}")
        self.stdout.write(f"Distance threshold: {threshold} km\n")
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING("No kecelakaan found to process."))
            return

        # Get all segmen for proximity calculation
        segmen_list = list(SegmenJalan.objects.select_related('ruas_jalan').all())
        
        if not segmen_list:
            raise CommandError("No segments found in database!")
        
        self.stdout.write(f"Checking against {len(segmen_list)} segments...\n")

        # Progress tracking
        assigned_count = 0
        not_assigned_count = 0
        already_assigned = 0
        affected_years = set()

        for idx, kecelakaan in enumerate(kecelakaan_qs, 1):
            # Show progress
            progress = f"[{idx}/{total_count}]"
            
            if kecelakaan.segmen_jalan:
                already_assigned += 1
                self.stdout.write(f"{progress} ✓ Already assigned to {kecelakaan.segmen_jalan.nama_segmen}")
                continue
            
            # Calculate distance to each segment
            accident_point = (float(kecelakaan.latitude), float(kecelakaan.longitude))
            
            min_distance = float('inf')
            closest_segmen = None
            
            for segmen in segmen_list:
                if not (segmen.lat_awal and segmen.lon_awal and segmen.lat_akhir and segmen.lon_akhir):
                    continue
                
                # Calculate distances to start and end points
                start_point = (float(segmen.lat_awal), float(segmen.lon_awal))
                distance_awal = geodesic(accident_point, start_point).kilometers
                
                end_point = (float(segmen.lat_akhir), float(segmen.lon_akhir))
                distance_akhir = geodesic(accident_point, end_point).kilometers
                
                # Use minimum distance
                distance = min(distance_awal, distance_akhir)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_segmen = segmen
            
            # Assign if within threshold
            if closest_segmen and min_distance <= threshold:
                kecelakaan.segmen_jalan = closest_segmen
                kecelakaan.save(update_fields=['segmen_jalan'])
                assigned_count += 1
                affected_years.add(kecelakaan.tanggal.year)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{progress} ✅ Assigned to {closest_segmen.ruas_jalan.nama_ruas} - {closest_segmen.nama_segmen} "
                        f"[Distance: {min_distance:.3f} km]"
                    )
                )
            else:
                not_assigned_count += 1
                distance_msg = f"{min_distance:.3f} km (threshold: {threshold} km)" if closest_segmen else "No segment found"
                self.stdout.write(
                    self.style.WARNING(f"{progress} ⚠ Not assigned ({distance_msg})")
                )

        # Summary
        self.stdout.write(self.style.WARNING(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(self.style.WARNING(f"{'='*80}"))
        self.stdout.write(f"Total processed: {total_count}")
        self.stdout.write(self.style.SUCCESS(f"  ✅ Newly assigned: {assigned_count}"))
        self.stdout.write(self.style.SUCCESS(f"  ✓ Already assigned: {already_assigned}"))
        self.stdout.write(self.style.WARNING(f"  ⚠ Not assigned: {not_assigned_count}"))

        # Recalculate Z-Scores if requested
        if recalc_zscore and affected_years:
            self.stdout.write(self.style.WARNING(f"\n{'='*80}"))
            self.stdout.write(self.style.SUCCESS("RECALCULATING Z-SCORES"))
            self.stdout.write(self.style.WARNING(f"{'='*80}"))
            
            for year in sorted(affected_years):
                try:
                    AnalisisZScore.calculate_zscore(year)
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Z-Score recalculated for {year}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error recalculating Z-Score for {year}: {e}")
                    )
        
        self.stdout.write(self.style.WARNING(f"{'='*80}\n"))
        self.stdout.write(self.style.SUCCESS("✅ Assignment complete!"))
