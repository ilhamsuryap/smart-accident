from django.shortcuts import redirect
from django.contrib import messages
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth.models import User


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Override adapter untuk menonaktifkan self-registration.
    Hanya superadmin yang boleh membuat akun baru.
    """

    def is_open_for_signup(self, request):
        # Selalu menonaktifkan pendaftaran publik
        return False


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Override adapter Google OAuth:
    - DILARANG membuat user baru dari Google login
    - Hanya user yang sudah ada di database yang bisa login via Google
    - Cek is_active dan role sebelum login
    """

    def is_open_for_signup(self, request, sociallogin):
        # Blok semua signup dari social account
        return False

    def pre_social_login(self, request, sociallogin):
        """
        Dipanggil sebelum social login diproses.
        Di sini kita validasi apakah user boleh login.
        """
        # Ambil email dari akun Google
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

        # Cari user berdasarkan email
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # User tidak ditemukan di database → tolak
            response = redirect('/login/?error=google_not_registered')
            raise ImmediateHttpResponse(response)
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).order_by('-date_joined').first()

        # Cek profile
        try:
            profile = user.profile
        except Exception:
            response = redirect('/login/?error=google_no_profile')
            raise ImmediateHttpResponse(response)

        # Cek is_active
        if not profile.is_active:
            response = redirect('/login/?error=google_inactive')
            raise ImmediateHttpResponse(response)

        # Cek role
        if profile.role not in ('superadmin', 'admin'):
            response = redirect('/login/?error=google_role_denied')
            raise ImmediateHttpResponse(response)

        # Hubungkan social login ke user yang sudah ada
        sociallogin.connect(request, user)
