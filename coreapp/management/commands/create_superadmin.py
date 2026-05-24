"""
Management command untuk membuat akun superadmin pertama.
Usage:
    python manage.py create_superadmin
    python manage.py create_superadmin --email admin@polres.go.id --password rahasia123
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from coreapp.models import Profile, Polres

User = get_user_model()


class Command(BaseCommand):
    help = 'Membuat akun superadmin pertama untuk sistem Smart Accident'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email akun superadmin',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password akun superadmin',
        )
        parser.add_argument(
            '--polres_id',
            type=int,
            help='ID Polres (default: polres pertama di database)',
        )

    def handle(self, *args, **options):
        
        self.stdout.write(self.style.MIGRATE_HEADING('=== Buat Akun Superadmin ===\n'))

        email = options.get('email')
        password = options.get('password')
        polres_id = options.get('polres_id')

        # ==== EMAIL ====
        if not email:
            email = input('Email superadmin: ').strip()
        if not email:
            raise CommandError('Email tidak boleh kosong.')

        email = email.lower()

        # ==== PASSWORD ====
        if not password:
            import getpass
            password = getpass.getpass('Password superadmin: ')
            password_confirm = getpass.getpass('Konfirmasi password: ')
            if password != password_confirm:
                raise CommandError('Password tidak cocok.')

        if len(password) < 8:
            raise CommandError('Password minimal 8 karakter.')

        # ==== POLRES ====
        if polres_id:
            try:
                polres = Polres.objects.get(id=polres_id, is_active=True)
            except Polres.DoesNotExist:
                raise CommandError('Polres dengan ID tersebut tidak ditemukan atau tidak aktif.')
        else:
            polres = Polres.objects.filter(is_active=True).first()
            if not polres:
                polres = Polres.objects.create(
                    nama='Madiun',
                    kode='MDN',
                    is_active=True
                )
                self.stdout.write(self.style.WARNING(f'⚠️  Tidak ditemukan Polres aktif. Membuat Polres default: {polres.nama} (ID: {polres.id})'))
               

        # ==== CEK USER EXIST ====
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f'User dengan email {email} sudah ada.')

        # ==== CREATE USER ====
        user = User.objects.create_superuser(
        email=email,
        name='Super Admin',
        password=password,
        role='superadmin',
        is_active=True,
    )

        # ==== PROFILE ====
        profile, created = Profile.objects.get_or_create(
           user=user,
           defaults={
               'polres': polres
               }
               )

# pastikan role & status benar
        profile.role = 'superadmin'
        profile.is_active = True
        profile.polres = polres
        profile.save()

        self.stdout.write(self.style.SUCCESS('\n✓ Akun superadmin berhasil dibuat!'))
        self.stdout.write(f'  Email  : {email}')
        self.stdout.write(f'  Role   : superadmin')
        self.stdout.write(f'  Polres : {polres.nama}')
        self.stdout.write('\nSilakan login di /login/')