import os
import django
from django.db import connection
from django.core.management import call_command

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from coreapp.models import User, AIConfig

def main():
    print("1. Menonaktifkan Foreign Key Checks...")
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        print("2. Mengambil daftar tabel...")
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"Ditemukan {len(tables)} tabel. Mulai menghapus...")
        for table in tables:
            print(f"Menghapus tabel: {table}")
            cursor.execute(f"DROP TABLE IF EXISTS `{table}` CASCADE;")
            
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    print("Semua tabel berhasil dihapus.")

    print("\n3. Menjalankan migrasi Django...")
    call_command('migrate')

    print("\n4. Membuat akun superadmin default...")
    User.objects.create_superuser(
        email='admin@gmail.com',
        name='Admin',
        password='admin123'
    )
    print("Akun superadmin berhasil dibuat.")

    print("\n5. Memulihkan konfigurasi AIConfig...")
    AIConfig.objects.create(tipe='kmeans', api_key='AIzaSyBjjZq1Fd_F1WBSEcPsWpXj5TLMNTOhLNs')
    AIConfig.objects.create(tipe='ahc', api_key='AIzaSyBjjZq1Fd_F1WBSEcPsWpXj5TLMNTOhLNs')
    print("Konfigurasi AIConfig berhasil dibuat.")

    print("\nProses reset database dan migrasi selesai dengan sukses!")

if __name__ == '__main__':
    main()
