from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """
    Authentication backend kustom:
    - Login menggunakan EMAIL (bukan username)
    - Validasi role: hanya superadmin atau admin yang diizinkan
    - Validasi is_active dari Profile (bukan dari User.is_active bawaan Django)
    """

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        # Support panggilan dengan keyword 'email' maupun 'username' (allauth kadang pakai username)
        login_email = email or username

        if not login_email or not password:
            return None

        # Normalisasi email (lowercase)
        login_email = login_email.strip().lower()

        try:
            user = User.objects.get(email__iexact=login_email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Ambil yang paling baru jika ada duplikat
            user = User.objects.filter(email__iexact=login_email).order_by('-date_joined').first()
            if not user:
                return None

        # Cek password
        if not user.check_password(password):
            return None

        # Cek profile dan role
        try:
            profile = user.profile
        except Exception:
            # Jika tidak ada profile, tolak login
            return None

        # Cek is_active di profile
        if not profile.is_active:
            return None

        # Cek role harus superadmin atau admin
        if profile.role not in ('superadmin', 'admin'):
            return None

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
