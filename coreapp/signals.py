"""
Django Signals untuk auto-update Z-Score, Rekap, dan auto-assign kecelakaan ke segmen
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import KecelakaanPreprosesing, RekapSegmen, AnalisisZScore, SegmenJalan


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


@receiver(post_save, sender=SegmenJalan)
def auto_assign_kecelakaan_ke_segmen_baru(sender, instance, created, **kwargs):
    """
    Trigger ketika SegmenJalan baru dibuat atau diupdate.
    Auto-assign data KecelakaanPreprosesing yang belum punya segmen atau yang cocok dengan segmen baru.
    
    Flow:
    1. Ketika segmen jalan baru dibuat
    2. Cari semua data preprocessing yang belum punya segmen (segmen_jalan is NULL)
    3. Untuk setiap data, coba assign ke segmen baru jika koordinatnya cocok
    """
    if created:
        print(f"\n{'='*70}")
        print(f"🚨 Signal: Segmen Jalan BARU dibuat: {instance.nama_segmen or f'Segmen {instance.km_awal}-{instance.km_akhir}'}")
        print(f"{'='*70}")
        
        # Cari semua data preprocessing yang belum punya segmen
        kecelakaan_tanpa_segmen = KecelakaanPreprosesing.objects.filter(segmen_jalan__isnull=True)
        print(f"📊 Ditemukan {kecelakaan_tanpa_segmen.count()} data preprocessing tanpa segmen")
        
        if kecelakaan_tanpa_segmen.exists():
            assigned_count = 0
            tahun_list = set()  # Track tahun yang ada assignment
            
            for kecelakaan in kecelakaan_tanpa_segmen:
                try:
                    # Coba find closest segment
                    kecelakaan.find_closest_segment()
                    
                    # Jika berhasil di-assign (segmen_jalan tidak null setelah find_closest_segment)
                    if kecelakaan.segmen_jalan:
                        kecelakaan.save(update_fields=['segmen_jalan', 'updated_at'])
                        assigned_count += 1
                        tahun_list.add(kecelakaan.tanggal.year)
                        print(f"   ✅ Kecelakaan ({kecelakaan.tanggal} - {kecelakaan.kecamatan}) → {kecelakaan.segmen_jalan.nama_segmen}")
                        
                except Exception as e:
                    print(f"   ❌ Error assigning kecelakaan {kecelakaan.id}: {str(e)}")
            
            print(f"\n📈 Total data yang di-assign: {assigned_count}/{kecelakaan_tanpa_segmen.count()}")
            
            # Update rekap dan Z-Score untuk tahun-tahun yang ada assignment
            if assigned_count > 0 and tahun_list:
                try:
                    print(f"\n🔄 Updating calculations untuk tahun: {sorted(tahun_list)}")
                    for tahun in tahun_list:
                        RekapSegmen.update_rekap(tahun)
                        AnalisisZScore.calculate_zscore(tahun)
                    print(f"✅ RekapSegmen dan AnalisisZScore berhasil di-update")
                except Exception as e:
                    print(f"❌ Error updating calculations: {str(e)}")
        else:
            print(f"✅ Tidak ada data preprocessing yang perlu di-assign")
        
        print(f"{'='*70}\n")
