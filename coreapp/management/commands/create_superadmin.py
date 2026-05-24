"""
Management command untuk membuat akun superadmin pertama.
Usage:
    python manage.py create_superadmin
    python manage.py create_superadmin --email admin@polres.go.id --password rahasia123
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from coreapp.models import Profile, POLRES_CHOICES


class Command(BaseCommand):
    help = 'Membuat akun superadmin pertama untuk sistem Smart Accident'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email akun superadmin',
            default=None,
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password akun superadmin',
            default=None,
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username akun superadmin (default: superadmin)',
            default='superadmin',
        )
        parser.add_argument(
            '--polres',
            type=str,
            help='Polres untuk superadmin (default: madiun)',
            default='madiun',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Buat Akun Superadmin ===\n'))

        email = options.get('email')
        password = options.get('password')
        username = options.get('username', 'superadmin')
        polres = options.get('polres', 'madiun')

        # Input interaktif jika tidak ada argumen
        if not email:
            email = input('Email superadmin: ').strip()
        if not email:
            raise CommandError('Email tidak boleh kosong.')

        if not password:
            import getpass
            password = getpass.getpass('Password superadmin: ')
            password_confirm = getpass.getpass('Konfirmasi password: ')
            if password != password_confirm:
                raise CommandError('Password tidak cocok.')

        if len(password) < 8:
            raise CommandError('Password minimal 8 karakter.')

        email = email.lower()

        # Cek apakah email sudah ada
        if User.objects.filter(email__iexact=email).exists():
            existing_user = User.objects.get(email__iexact=email)
            try:
                profile = existing_user.profile
                if profile.role == 'superadmin':
                    self.stdout.write(
                        self.style.WARNING(f'User dengan email {email} sudah menjadi superadmin.')
                    )
                    return
                else:
                    # Upgrade ke superadmin
                    profile.role = 'superadmin'
                    profile.is_active = True
                    profile.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'User {email} berhasil diupgrade ke superadmin.')
                    )
                    return
            except Profile.DoesNotExist:
                pass

        # Generate username unik
        base_username = username
        counter = 1
        while User.objects.filter(username=base_username).exists():
            base_username = f"{username}{counter}"
            counter += 1

        # Buat user baru
        user = User.objects.create_user(
            username=base_username,
            email=email,
            password=password,
            is_staff=True,        # Agar bisa akses Django admin
            is_superuser=False,   # Bukan superuser Django, tapi superadmin sistem kita
        )

        # Update profile
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=user)

        profile.role = 'superadmin'
        profile.is_active = True
        profile.polres = polres
        profile.save()

        self.stdout.write(self.style.SUCCESS('\n✓ Akun superadmin berhasil dibuat!'))
        self.stdout.write(f'  Email    : {email}')
        self.stdout.write(f'  Username : {base_username}')
        self.stdout.write(f'  Role     : superadmin')
        self.stdout.write(f'  Polres   : {polres}')
        self.stdout.write('\nSilakan login di /login/ menggunakan email dan password di atas.')
