"""
Management command untuk manual trigger recalculation Z-Score dan Rekap
Usage: python manage.py recalculate_zscore
       python manage.py recalculate_zscore --tahun 2024
       python manage.py recalculate_zscore --all
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from coreapp.models import RekapSegmen, AnalisisZScore


class Command(BaseCommand):
    help = 'Manual trigger untuk recalculate Z-Score dan Rekap Segmen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tahun',
            type=int,
            help='Tahun untuk recalculate (default: tahun ini)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalculate untuk ALL tahun (tidak recommended untuk large dataset)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('🔄 Starting Z-Score recalculation...'))
        
        tahun_list = []
        
        if options.get('all'):
            # Get semua tahun yang ada di database
            from coreapp.models import KecelakaanPreprosesing
            from django.db.models import ExtensionAgg
            from django.db.models.functions import ExtractYear
            from django.db.models import Value
            from django.db.models import F
            
            tahun_list = KecelakaanPreprosesing.objects.dates('tanggal', 'year').values_list('tanggal__year', flat=True).distinct()
            self.stdout.write(self.style.SUCCESS(f'ℹ️ Found {len(tahun_list)} tahun dengan data'))
        elif options.get('tahun'):
            tahun_list = [options['tahun']]
        else:
            tahun_list = [timezone.now().year]
        
        success_count = 0
        error_count = 0
        
        for tahun in tahun_list:
            try:
                self.stdout.write(f'\n📅 Processing tahun {tahun}...')
                
                # Update Rekap
                self.stdout.write('   📊 Updating RekapSegmen...')
                RekapSegmen.update_rekap(tahun)
                self.stdout.write(self.style.SUCCESS('   ✅ RekapSegmen updated'))
                
                # Calculate Z-Score
                self.stdout.write('   📈 Calculating Z-Score...')
                AnalisisZScore.calculate_zscore(tahun)
                self.stdout.write(self.style.SUCCESS('   ✅ Z-Score calculated'))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error processing tahun {tahun}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'✅ Success: {success_count} tahun'))
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f'⚠️ Errors: {error_count} tahun'))
        self.stdout.write('='*80)
