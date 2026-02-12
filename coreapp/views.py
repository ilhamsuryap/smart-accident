from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import math

from .models import RuasJalan, SegmenJalan, Kecelakaan, RekapSegmen, AnalisisZScore
from .forms import (
    UserRegistrationForm, RuasJalanForm, SegmenJalanForm, 
    KecelakaanForm, RekapSegmenForm
)


# Helper function
def is_admin(user):
    return user.is_staff or user.is_superuser


# Authentication Views
def register_view(request):
    """View untuk registrasi user baru"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registrasi berhasil! Silakan login.')
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    
    context = {'form': form}
    return render(request, 'registration/register.html', context)


def login_view(request):
    """View untuk login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Selamat datang, {user.first_name or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Username atau password salah.')
    
    return render(request, 'registration/login.html')


def logout_view(request):
    """View untuk logout"""
    logout(request)
    messages.success(request, 'Anda telah logout.')
    return redirect('login')


# Dashboard Views
@login_required(login_url='login')
def dashboard_view(request):
    """Dashboard utama"""
    context = {
        'total_ruas': RuasJalan.objects.count(),
        'total_segmen': SegmenJalan.objects.count(),
        'total_kecelakaan': Kecelakaan.objects.count(),
        'total_korban': Kecelakaan.objects.aggregate(
            total=Sum('korban_meninggal') + Sum('korban_luka_berat') + Sum('korban_luka_ringan')
        )['total'] or 0,
    }
    
    # Statistik tahun ini
    tahun_ini = timezone.now().year
    context['kecelakaan_tahun_ini'] = Kecelakaan.objects.filter(
        tanggal__year=tahun_ini
    ).count()
    
    # Segmen dengan kecelakaan terbanyak
    context['top_segmen'] = SegmenJalan.objects.annotate(
        jumlah_kecelakaan=Count('kecelakaan')
    ).order_by('-jumlah_kecelakaan')[:5]
    
    return render(request, 'coreapp/dashboard.html', context)


# Ruas Jalan Views
@login_required(login_url='login')
def ruas_jalan_list(request):
    """Daftar ruas jalan"""
    ruas_jalan = RuasJalan.objects.all()
    
    if request.GET.get('search'):
        search = request.GET.get('search')
        ruas_jalan = ruas_jalan.filter(
            Q(nama_ruas__icontains=search) |
            Q(wilayah__icontains=search)
        )
    
    context = {
        'ruas_jalan': ruas_jalan,
        'is_admin': is_admin(request.user)
    }
    return render(request, 'coreapp/ruas_jalan/list.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def ruas_jalan_create(request):
    """Buat ruas jalan baru"""
    if request.method == 'POST':
        form = RuasJalanForm(request.POST)
        if form.is_valid():
            ruas = form.save()
            # Auto-generate segmen jalan
            ruas.generate_segmen()
            messages.success(request, f'Ruas jalan "{ruas.nama_ruas}" berhasil ditambahkan dan segmen otomatis dibuat.')
            return redirect('ruas_jalan_list')
    else:
        form = RuasJalanForm()
    
    context = {'form': form, 'title': 'Tambah Ruas Jalan'}
    return render(request, 'coreapp/ruas_jalan/form.html', context)


@login_required(login_url='login')
def ruas_jalan_detail(request, pk):
    """Detail ruas jalan"""
    ruas = get_object_or_404(RuasJalan, pk=pk)
    segmen = ruas.segmen_jalan.all()
    
    context = {
        'ruas': ruas,
        'segmen': segmen,
        'is_admin': is_admin(request.user)
    }
    return render(request, 'coreapp/ruas_jalan/detail.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def ruas_jalan_update(request, pk):
    """Update ruas jalan"""
    ruas = get_object_or_404(RuasJalan, pk=pk)
    
    if request.method == 'POST':
        form = RuasJalanForm(request.POST, instance=ruas)
        if form.is_valid():
            ruas = form.save()
            # Auto-regenerate segmen jalan saat update
            ruas.generate_segmen()
            messages.success(request, f'Ruas jalan "{ruas.nama_ruas}" berhasil diperbarui dan segmen otomatis dibuat ulang.')
            return redirect('ruas_jalan_detail', pk=ruas.pk)
    else:
        form = RuasJalanForm(instance=ruas)
    
    context = {'form': form, 'ruas': ruas, 'title': 'Edit Ruas Jalan'}
    return render(request, 'coreapp/ruas_jalan/form.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def ruas_jalan_delete(request, pk):
    """Hapus ruas jalan"""
    ruas = get_object_or_404(RuasJalan, pk=pk)
    
    if request.method == 'POST':
        nama = ruas.nama_ruas
        ruas.delete()
        messages.success(request, f'Ruas jalan "{nama}" berhasil dihapus.')
        return redirect('ruas_jalan_list')
    
    context = {'ruas': ruas}
    return render(request, 'coreapp/ruas_jalan/confirm_delete.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def generate_segmen(request, pk):
    """Generate segmen otomatis"""
    ruas = get_object_or_404(RuasJalan, pk=pk)
    ruas.generate_segmen()
    messages.success(request, f'Segmen untuk "{ruas.nama_ruas}" berhasil dibuat.')
    return redirect('ruas_jalan_detail', pk=pk)


# Kecelakaan Views
@login_required(login_url='login')
def kecelakaan_list(request):
    """Daftar kecelakaan"""
    kecelakaan = Kecelakaan.objects.all()
    
    if request.GET.get('search'):
        search = request.GET.get('search')
        kecelakaan = kecelakaan.filter(
            Q(desa__icontains=search) |
            Q(kecamatan__icontains=search) |
            Q(kabupaten_kota__icontains=search)
        )
    
    if request.GET.get('tahun'):
        tahun = request.GET.get('tahun')
        kecelakaan = kecelakaan.filter(tanggal__year=tahun)
    
    context = {
        'kecelakaan': kecelakaan[:100],  # Limit untuk performa
        'is_admin': is_admin(request.user),
        'tahun_options': range(2020, timezone.now().year + 1)
    }
    return render(request, 'coreapp/kecelakaan/list.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def kecelakaan_create(request):
    """Tambah data kecelakaan"""
    if request.method == 'POST':
        form = KecelakaanForm(request.POST)
        if form.is_valid():
            kecelakaan = form.save()
            messages.success(request, 'Data kecelakaan berhasil ditambahkan.')
            return redirect('kecelakaan_list')
    else:
        form = KecelakaanForm()
    
    context = {'form': form, 'title': 'Tambah Kecelakaan'}
    return render(request, 'coreapp/kecelakaan/form.html', context)


@login_required(login_url='login')
def kecelakaan_detail(request, pk):
    """Detail kecelakaan"""
    kecelakaan = get_object_or_404(Kecelakaan, pk=pk)
    
    context = {
        'kecelakaan': kecelakaan,
        'is_admin': is_admin(request.user)
    }
    return render(request, 'coreapp/kecelakaan/detail.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def kecelakaan_update(request, pk):
    """Update kecelakaan"""
    kecelakaan = get_object_or_404(Kecelakaan, pk=pk)
    
    if request.method == 'POST':
        form = KecelakaanForm(request.POST, instance=kecelakaan)
        if form.is_valid():
            kecelakaan = form.save()
            messages.success(request, 'Data kecelakaan berhasil diperbarui.')
            return redirect('kecelakaan_detail', pk=kecelakaan.pk)
    else:
        form = KecelakaanForm(instance=kecelakaan)
    
    context = {'form': form, 'kecelakaan': kecelakaan, 'title': 'Edit Kecelakaan'}
    return render(request, 'coreapp/kecelakaan/form.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def kecelakaan_delete(request, pk):
    """Hapus kecelakaan"""
    kecelakaan = get_object_or_404(Kecelakaan, pk=pk)
    
    if request.method == 'POST':
        kecelakaan.delete()
        messages.success(request, 'Data kecelakaan berhasil dihapus.')
        return redirect('kecelakaan_list')
    
    context = {'kecelakaan': kecelakaan}
    return render(request, 'coreapp/kecelakaan/confirm_delete.html', context)


# Map Views
@login_required(login_url='login')
def map_view(request):
    """Tampilkan peta interaktif"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    # Hitung Z-Score jika belum ada
    if not AnalisisZScore.objects.filter(tahun=tahun).exists():
        AnalisisZScore.calculate_zscore(tahun)
    
    context = {
        'tahun': tahun,
        'tahun_options': range(2020, timezone.now().year + 1)
    }
    return render(request, 'coreapp/map/map.html', context)


# API Views
@api_view(['GET'])
@login_required(login_url='login')
def api_segmen_geojson(request):
    """API untuk mendapatkan GeoJSON segmen jalan"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    segmen_list = SegmenJalan.objects.select_related('ruas_jalan').all()
    
    features = []
    for segmen in segmen_list:
        # Cari analisis Z-Score
        try:
            analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
            kategori = analisis.kategori
            zscore = float(analisis.nilai_zscore)
            color = analisis.get_kategori_display_color()
        except AnalisisZScore.DoesNotExist:
            kategori = 'unknown'
            zscore = 0
            color = '#999999'
        
        # Tanpa geometry spatial, gunakan data lat/lon dari kecelakaan
        kecelakaan_list = segmen.kecelakaan.filter(
            tanggal__year=tahun
        ).values_list('latitude', 'longitude')
        
        if kecelakaan_list:
            # Buat LineString dari koordinat kecelakaan
            coords = [[float(lon), float(lat)] for lat, lon in kecelakaan_list]
            
            feature = {
                'type': 'Feature',
                'id': segmen.id,
                'properties': {
                    'segmen_id': segmen.id,
                    'ruas_nama': segmen.ruas_jalan.nama_ruas,
                    'km_awal': float(segmen.km_awal),
                    'km_akhir': float(segmen.km_akhir),
                    'kategori': kategori,
                    'zscore': zscore,
                    'color': color,
                    'url': f'/kecelakaan/segmen/{segmen.id}/'
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coords
                }
            }
            features.append(feature)
    
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    return Response(geojson)


@api_view(['GET'])
@login_required(login_url='login')
def api_kecelakaan_geojson(request):
    """API untuk mendapatkan GeoJSON kecelakaan"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    kecelakaan = Kecelakaan.objects.filter(
        tanggal__year=tahun,
        latitude__isnull=False,
        longitude__isnull=False
    )
    
    features = []
    for k in kecelakaan:
        feature = {
            'type': 'Feature',
            'id': k.id,
            'properties': {
                'kecelakaan_id': k.id,
                'tanggal': k.tanggal.isoformat(),
                'waktu': k.waktu.isoformat(),
                'lokasi': f"{k.desa}, {k.kecamatan}",
                'korban_meninggal': k.korban_meninggal,
                'korban_luka_berat': k.korban_luka_berat,
                'korban_luka_ringan': k.korban_luka_ringan,
                'total_korban': k.total_korban,
                'kerugian': float(k.kerugian_materi),
                'url': f'/kecelakaan/{k.id}/'
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [float(k.longitude), float(k.latitude)]
            }
        }
        features.append(feature)
    
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    return Response(geojson)


@api_view(['GET'])
@login_required(login_url='login')
def api_analisis_statistik(request):
    """API untuk mendapatkan statistik analisis"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    analisis = AnalisisZScore.objects.filter(tahun=tahun)
    
    statistik = {
        'sangat_tinggi': analisis.filter(kategori='sangat_tinggi').count(),
        'tinggi': analisis.filter(kategori='tinggi').count(),
        'sedang': analisis.filter(kategori='sedang').count(),
        'rendah': analisis.filter(kategori='rendah').count(),
        'sangat_rendah': analisis.filter(kategori='sangat_rendah').count(),
    }
    
    return Response({
        'tahun': tahun,
        'total_segmen': analisis.count(),
        'kategori': statistik
    })


# Analisis Views
@login_required(login_url='login')
def analisis_view(request):
    """Halaman analisis"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    # Hitung ulang analisis
    if request.method == 'POST' and is_admin(request.user):
        RekapSegmen.update_rekap(tahun)
        AnalisisZScore.calculate_zscore(tahun)
        messages.success(request, f'Analisis untuk tahun {tahun} berhasil dihitung.')
    
    # Ambil analisis
    analisis = AnalisisZScore.objects.filter(tahun=tahun).order_by('-nilai_zscore')
    
    # Statistik
    statistik = {
        'sangat_tinggi': analisis.filter(kategori='sangat_tinggi'),
        'tinggi': analisis.filter(kategori='tinggi'),
        'sedang': analisis.filter(kategori='sedang'),
        'rendah': analisis.filter(kategori='rendah'),
        'sangat_rendah': analisis.filter(kategori='sangat_rendah'),
    }
    
    context = {
        'analisis': analisis,
        'statistik': statistik,
        'tahun': tahun,
        'tahun_options': range(2020, timezone.now().year + 1),
        'is_admin': is_admin(request.user)
    }
    
    return render(request, 'coreapp/analisis/analisis.html', context)


@login_required(login_url='login')
def segmen_kecelakaan_detail(request, segmen_id):
    """Detail kecelakaan per segmen"""
    segmen = get_object_or_404(SegmenJalan, pk=segmen_id)
    tahun = request.GET.get('tahun', timezone.now().year)
    
    kecelakaan = Kecelakaan.objects.filter(
        segmen_jalan=segmen,
        tanggal__year=tahun
    )
    
    try:
        analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
    except AnalisisZScore.DoesNotExist:
        analisis = None
    
    context = {
        'segmen': segmen,
        'kecelakaan': kecelakaan,
        'analisis': analisis,
        'tahun': tahun
    }
    
    return render(request, 'coreapp/analisis/segmen_detail.html', context)
