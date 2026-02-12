from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import RuasJalan, SegmenJalan, Kecelakaan, RekapSegmen, AnalisisZScore


class UserRegistrationForm(UserCreationForm):
    """Form untuk registrasi user baru"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


class RuasJalanForm(forms.ModelForm):
    """Form untuk CRUD Ruas Jalan"""
    
    class Meta:
        model = RuasJalan
        fields = ['nama_ruas', 'jenis_jalan', 'wilayah', 'panjang_km', 'lat_awal', 'lon_awal', 'lat_akhir', 'lon_akhir']
        widgets = {
            'nama_ruas': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nama ruas jalan'
            }),
            'jenis_jalan': forms.Select(attrs={
                'class': 'form-control'
            }),
            'wilayah': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan wilayah'
            }),
            'panjang_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': 'Masukkan panjang dalam km'
            }),
            'lat_awal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Latitude awal',
                'readonly': True
            }),
            'lon_awal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Longitude awal',
                'readonly': True
            }),
            'lat_akhir': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Latitude akhir',
                'readonly': True
            }),
            'lon_akhir': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Longitude akhir',
                'readonly': True
            }),
        }


class SegmenJalanForm(forms.ModelForm):
    """Form untuk CRUD Segmen Jalan"""
    
    class Meta:
        model = SegmenJalan
        fields = ['ruas_jalan', 'km_awal', 'km_akhir']
        widgets = {
            'ruas_jalan': forms.Select(attrs={
                'class': 'form-control'
            }),
            'km_awal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': 'Km awal'
            }),
            'km_akhir': forms.NumberInput(attrs={
                'class': 'form-control',
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
            'jumlah_kecelakaan', 'korban_meninggal', 'korban_luka_berat',
            'korban_luka_ringan', 'kerugian_materi', 'desa', 'kecamatan',
            'kabupaten_kota', 'keterangan'
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'waktu': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Latitude'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Longitude'
            }),
            'jumlah_kecelakaan': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'korban_meninggal': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'korban_luka_berat': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'korban_luka_ringan': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'kerugian_materi': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'desa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama desa'
            }),
            'kecamatan': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama kecamatan'
            }),
            'kabupaten_kota': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama kabupaten/kota'
            }),
            'keterangan': forms.Textarea(attrs={
                'class': 'form-control',
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
                'class': 'form-control'
            }),
            'periode_tahun': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2000',
                'max': '2100'
            }),
        }
