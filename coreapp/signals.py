"""
Django Signals untuk auto-update Z-Score dan Rekap ketika data kecelakaan berubah
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import KecelakaanPreprosesing, RekapSegmen, AnalisisZScore


@receiver(post_save, sender=KecelakaanPreprosesing)
def update_on_kecelakaan_preprosesing_create(sender, instance, created, **kwargs):
    """
    Trigger update RekapSegmen dan AnalisisZScore ketika KecelakaanPreprosesing dibuat atau diupdate
    """
    if created:
        print(f"✅ Signal: Kecelakaan Preprosesing baru dibuat. Auto-updating calculations...")
        
        # Dapatkan tahun dari data kecelakaan
        tahun = instance.tanggal.year
        
        # Update rekap untuk tahun tersebut
        try:
            RekapSegmen.update_rekap(tahun)
            print(f"✅ RekapSegmen updated for tahun {tahun}")
        except Exception as e:
            print(f"❌ Error updating RekapSegmen: {str(e)}")
        
        # Update Z-Score untuk tahun tersebut
        try:
            AnalisisZScore.calculate_zscore(tahun)
            print(f"✅ AnalisisZScore calculated for tahun {tahun}")
        except Exception as e:
            print(f"❌ Error calculating Z-Score: {str(e)}")


@receiver(post_delete, sender=KecelakaanPreprosesing)
def update_on_kecelakaan_preprosesing_delete(sender, instance, **kwargs):
    """
    Trigger update RekapSegmen dan AnalisisZScore ketika KecelakaanPreprosesing dihapus
    """
    print(f"🗑️ Signal: Kecelakaan Preprosesing dihapus. Auto-updating calculations...")
    
    # Dapatkan tahun dari data kecelakaan yang dihapus
    tahun = instance.tanggal.year
    
    # Update rekap untuk tahun tersebut
    try:
        RekapSegmen.update_rekap(tahun)
        print(f"✅ RekapSegmen updated for tahun {tahun}")
    except Exception as e:
        print(f"❌ Error updating RekapSegmen: {str(e)}")
    
    # Update Z-Score untuk tahun tersebut
    try:
        AnalisisZScore.calculate_zscore(tahun)
        print(f"✅ AnalisisZScore calculated for tahun {tahun}")
    except Exception as e:
        print(f"❌ Error calculating Z-Score: {str(e)}")
