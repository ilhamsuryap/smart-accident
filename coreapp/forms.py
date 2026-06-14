from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import (
    RuasJalan, SegmenJalan, Kecelakaan, RekapSegmen, AnalisisZScore,
    KecelakaanRaw, KecelakaanPreprosesing, Profile, Polres
)

User = get_user_model()


# ========================
# LOGIN FORM (email-based)
# ========================
class LoginForm(forms.Form):
    """Form login menggunakan email dan password"""
    email = forms.EmailField(
        label='Email',
        error_messages={
            'required': 'Email tidak boleh kosong.',
            'invalid': 'Format email tidak valid (contoh: user@example.com).'
        },
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan email Anda',
            'autofocus': True,
            'id': 'id_email',
        })
    )
    password = forms.CharField(
        label='Password',
        error_messages={
            'required': 'Password tidak boleh kosong.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan password Anda',
            'id': 'id_password',
        })
    )


# ========================
# ADMIN MANAGEMENT FORMS (Superadmin only)
# ========================
class AdminCreateForm(forms.ModelForm):
    """Form untuk superadmin membuat akun admin baru"""
    email = forms.EmailField(
        label='Email',
        required=True,
        error_messages={
            'required': 'Email tidak boleh kosong.',
            'invalid': 'Format email tidak valid (contoh:user@example.com).'
        },
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@polres.go.id',
            'id': 'id_email',
        })
    )
    first_name = forms.CharField(
        label='Nama Depan',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nama depan',
            'id': 'id_first_name',
        })
    )
    last_name = forms.CharField(
        label='Nama Belakang',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nama belakang',
            'id': 'id_last_name',
        })
    )
    password1 = forms.CharField(
        label='Password',
        error_messages={
            'required': 'Password tidak boleh kosong.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimal 8 karakter',
            'id': 'id_password1',
        })
    )
    password2 = forms.CharField(
        label='Konfirmasi Password',
        error_messages={
            'required': 'Konfirmasi password tidak boleh kosong.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ulangi password',
            'id': 'id_password2',
        })
    )
    polres = forms.ModelChoiceField(
        label='Polres',
        queryset=Polres.objects.filter(is_active=True),
        required=True,
        error_messages={
            'required': 'Polres harus dipilih.'
        },
        empty_label='-- Pilih Polres --',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_polres',
        })
    )
    role = forms.ChoiceField(
        label='Role',
        choices=User.ROLE_CHOICES,
        initial='admin',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_role',
        })
    )
    is_active = forms.BooleanField(
        label='Akun Aktif',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_is_active',
        })
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Email ini sudah digunakan oleh akun lain.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Password tidak cocok.')
        if len(password1) < 8:
            raise ValidationError('Password minimal 8 karakter.')
        return password2

    def save(self, commit=True):
        email = self.cleaned_data['email'].strip().lower()
        role = self.cleaned_data.get('role', 'admin')
        is_active = self.cleaned_data.get('is_active', True)

        # Generate username unik dari email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            name=f"{self.cleaned_data.get('first_name', '')} {self.cleaned_data.get('last_name', '')}".strip() or email,
            role=role,
            is_active=is_active,
        )
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            # Update profile (dibuat otomatis oleh signal)
            try:
                profile = user.profile
            except Profile.DoesNotExist:
                profile = Profile.objects.create(user=user)
            profile.role = role
            profile.polres = self.cleaned_data.get('polres')
            profile.is_active = is_active
            profile.save()
        return user


class AdminUpdateForm(forms.Form):
    """Form untuk superadmin mengedit akun admin"""
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'id': 'id_email',
        })
    )
    first_name = forms.CharField(
        label='Nama Depan',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_first_name',
        })
    )
    last_name = forms.CharField(
        label='Nama Belakang',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_last_name',
        })
    )
    polres = forms.ModelChoiceField(
        label='Polres',
        queryset=Polres.objects.filter(is_active=True),
        required=False,
        empty_label='-- Pilih Polres --',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_polres',
        })
    )
    role = forms.ChoiceField(
        label='Role',
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_role',
        })
    )
    is_active = forms.BooleanField(
        label='Akun Aktif',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_is_active',
        })
    )
    new_password = forms.CharField(
        label='Password Baru (opsional)',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kosongkan jika tidak ingin mengubah password',
            'id': 'id_new_password',
        })
    )

    def __init__(self, *args, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.user_instance:
            qs = qs.exclude(pk=self.user_instance.pk)
        if qs.exists():
            raise ValidationError('Email ini sudah digunakan oleh akun lain.')
        return email

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password', '')
        if password and len(password) < 8:
            raise ValidationError('Password minimal 8 karakter.')
        return password

    def save(self, user):
        role = self.cleaned_data.get('role', 'admin')
        is_active = self.cleaned_data.get('is_active', True)

        user.email = self.cleaned_data['email'].strip().lower()
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.role = role
        user.is_active = is_active

        new_password = self.cleaned_data.get('new_password', '')
        if new_password:
            user.set_password(new_password)

        user.save()

        # Update profile
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=user)
        profile.role = role
        profile.polres = self.cleaned_data.get('polres')
        profile.is_active = is_active
        profile.save()

        return user


# ========================
# POLRES MANAGEMENT FORM (Superadmin only)
# ========================
class PolresForm(forms.ModelForm):
    """Form untuk superadmin mengelola data Polres"""

    class Meta:
        model = Polres
        fields = ['nama', 'kode', 'alamat', 'telepon', 'is_active']
        error_messages = {
            'nama': {
                'required': 'Nama Polres tidak boleh kosong.'
            },
            'kode': {
                'required': 'Kode Polres tidak boleh kosong.'  
            }
        }
        widgets = {
            'nama': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: Polres Madiun',
                'id': 'id_nama',
            }),
            'kode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: polres_madiun',
                'id': 'id_kode',
            }),
            'alamat': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Masukkan alamat polres',
                'id': 'id_alamat',
            }),
            'telepon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: (0351) 123456',
                'id': 'id_telepon',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_is_active',
            }),
        }

    def clean_kode(self):
        kode = self.cleaned_data.get('kode', '').strip().lower().replace(' ', '_')
        return kode


# ========================
# RUAS JALAN & KECELAKAAN FORMS (existing)
# ========================
class RuasJalanForm(forms.ModelForm):
    """Form untuk CRUD Ruas Jalan"""    

    class Meta:
        model = RuasJalan
        fields = ['nama_ruas', 'jenis_jalan', 'wilayah', 'panjang_km', 'lat_awal', 'lon_awal', 'lat_akhir', 'lon_akhir', 'geometry']
        error_messages = {
            'nama_ruas': {
                'required': 'Nama ruas jalan tidak boleh kosong.'
            },
            'jenis_jalan': {
                'required': 'Jenis jalan harus dipilih.'
            },
            'wilayah': {
                'required': 'Wilayah tidak boleh kosong.'
            },
        }
        widgets = {
            'geometry': forms.HiddenInput(),
            'nama_ruas': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'placeholder': 'Masukkan nama ruas jalan'
            }),
            'jenis_jalan': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500'
            }),
            'wilayah': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'placeholder': 'Masukkan wilayah'
            }),
            'panjang_km': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.001',
                'placeholder': 'Masukkan panjang dalam km',
                'readonly': True
            }),
            'lat_awal': forms.HiddenInput(),
            'lon_awal': forms.HiddenInput(),
            'lat_akhir': forms.HiddenInput(),
            'lon_akhir': forms.HiddenInput(),
        }


class SegmenJalanForm(forms.ModelForm):
    """Form untuk CRUD Segmen Jalan"""

    class Meta:
        model = SegmenJalan
        fields = ['ruas_jalan', 'km_awal', 'km_akhir']
        widgets = {
            'ruas_jalan': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500'
            }),
            'km_awal': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.001',
                'placeholder': 'Km awal'
            }),
            'km_akhir': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.001',
                'placeholder': 'Km akhir'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        km_awal = cleaned_data.get('km_awal')
        km_akhir = cleaned_data.get('km_akhir')

        if km_awal and km_akhir and km_awal >= km_akhir:
            raise forms.ValidationError(
                'Km akhir harus lebih besar dari km awal'
            )

        return cleaned_data


class KecelakaanForm(forms.ModelForm):
    """Form untuk CRUD Kecelakaan"""

    class Meta:
        model = Kecelakaan
        fields = [
            'tanggal', 'waktu', 'latitude', 'longitude',
            'korban_meninggal', 'korban_luka_berat',
            'korban_luka_ringan', 'kerugian_materi', 'desa', 'kecamatan',
            'kabupaten_kota', 'keterangan'
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'type': 'date'
            }),
            'waktu': forms.TimeInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'type': 'time'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.000001',
                'placeholder': 'Latitude'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.000001',
                'placeholder': 'Longitude'
            }),
            'korban_meninggal': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'min': '0'
            }),
            'korban_luka_berat': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'min': '0'
            }),
            'korban_luka_ringan': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'min': '0'
            }),
            'kerugian_materi': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'desa': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'placeholder': 'Nama desa'
            }),
            'kecamatan': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'placeholder': 'Nama kecamatan'
            }),
            'kabupaten_kota': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'placeholder': 'Nama kabupaten/kota'
            }),
            'keterangan': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'rows': 4,
                'placeholder': 'Keterangan tambahan'
            }),
        }


class RekapSegmenForm(forms.ModelForm):
    """Form untuk viewing Rekap Segmen (read-only mostly)"""

    class Meta:
        model = RekapSegmen
        fields = ['segmen_jalan', 'periode_tahun']
        widgets = {
            'segmen_jalan': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500'
            }),
            'periode_tahun': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
                'min': '2000',
                'max': '2100'
            }),
        }


class UploadKecelakaanRawForm(forms.Form):
    """Form untuk upload data kecelakaan raw dari Excel/CSV"""
    file = forms.FileField(
        label='Upload File',
        help_text='Format: Excel (.xlsx, .xls) atau CSV (.csv)',
        widget=forms.FileInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
            'accept': '.xlsx,.xls,.csv',
            'id': 'id_file'
        })
    )


class UploadKecelakaanPreprosesForm(forms.Form):
    """Form untuk upload data kecelakaan preprocessing dari Excel/CSV"""
    file = forms.FileField(
        label='Upload File',
        help_text='Format: Excel (.xlsx, .xls) atau CSV (.csv)',
        widget=forms.FileInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500',
            'accept': '.xlsx,.xls,.csv',
            'id': 'id_file'
        })
    )
