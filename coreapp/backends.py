from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Authentication backend kustom:
    - Login menggunakan EMAIL (bukan username)
    - Validasi is_active dari User model langsung
    - Validasi role: hanya superadmin atau admin yang diizinkan
    - Dilarang membuat user baru dari Google OAuth
    """

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        # Support panggilan dengan keyword 'email' maupun 'username' (allauth kadang pakai username)
        login_email = email or username

        if not login_email or not password:
            return None

        # Normalisasi email (lowercase)
        login_email = login_email.strip().lower()

        # 1. Cari user berdasarkan email
        try:
            user = User.objects.get(email__iexact=login_email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Ambil yang paling baru jika ada duplikat
            user = User.objects.filter(email__iexact=login_email).order_by('-created_at').first()
            if not user:
                return None

        # 2. Cek password
        if not user.check_password(password):
            return None

        # 3. Cek is_active dari User model langsung
        if not user.is_active:
            return None

        # 4. Cek role harus superadmin atau admin
        if user.role not in ('superadmin', 'admin'):
            return None

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
