from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Override adapter untuk menonaktifkan self-registration.
    HANYA superadmin yang boleh membuat akun melalui panel superadmin.
    """

    def is_open_for_signup(self, request):
        # Selalu menonaktifkan pendaftaran publik
        return False


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Override adapter Google OAuth:

    ALUR LOGIN GOOGLE:
    1. Ambil email dari akun Google
    2. DILARANG membuat user baru (auto-register diblokir)
    3. Cocokkan email dengan user yang sudah ada di database
    4. Jika tidak ditemukan → tolak login
    5. Jika is_active = False → tolak login
    6. Login user yang sudah ada
    """

    def is_open_for_signup(self, request, sociallogin):
        # Blok semua signup dari social account — TIDAK BOLEH ada user baru dari Google
        return False

    def pre_social_login(self, request, sociallogin):
        """
        Dipanggil sebelum social login diproses.
        Validasi apakah user boleh login via Google.

        Alur:
        1. Ambil email dari Google
        2. Jika tidak ada email → tolak
        3. Cari user berdasarkan email (JANGAN buat user baru)
        4. Jika tidak ditemukan → tolak
        5. Jika is_active = False → tolak
        6. Hubungkan ke user yang sudah ada
        """
        # 1. Ambil email dari akun Google
        email = sociallogin.account.extra_data.get('email', '')
        if not email:
            # Coba dari sociallogin.email_addresses
            if sociallogin.email_addresses:
                email = sociallogin.email_addresses[0].email

        if not email:
            # Jika tidak ada email, tolak login
            response = redirect('/login/?error=google_no_email')
            raise ImmediateHttpResponse(response)

        email = email.strip().lower()

        # 2. Cari user berdasarkan email — JANGAN auto-register
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # User tidak ditemukan di database → tolak login
            response = redirect('/login/?error=google_not_registered')
            raise ImmediateHttpResponse(response)
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).order_by('-created_at').first()
            if not user:
                response = redirect('/login/?error=google_not_registered')
                raise ImmediateHttpResponse(response)

        # 3. Cek is_active dari User model langsung
        if not user.is_active:
            response = redirect('/login/?error=google_inactive')
            raise ImmediateHttpResponse(response)

        # 4. Cek role — hanya superadmin dan admin yang diizinkan
        if user.role not in ('superadmin', 'admin'):
            response = redirect('/login/?error=google_role_denied')
            raise ImmediateHttpResponse(response)

        # 5. Hubungkan social login ke user yang sudah ada (tidak membuat user baru)
        sociallogin.connect(request, user)
