from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
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
from sklearn.discriminant_analysis import StandardScaler
from .models import (
    RuasJalan, SegmenJalan, Kecelakaan, AnalisisZScore, RekapSegmen,
    Kota, Kecamatan, Kelurahan, KMeansData, AIConfig
)
from rest_framework import status
import json
import math
import numpy as np
import requests
from datetime import datetime
import os

import os
import pandas as pd
from sklearn.cluster import KMeans

from django.conf import settings
from django.shortcuts import render, redirect   
from io import StringIO
from django.shortcuts import redirect



from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import StandardScaler, LabelEncoder

from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score




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
    tahun_raw = request.GET.get('tahun')
    if not tahun_raw or tahun_raw == 'None':
        tahun = timezone.now().year
    else:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
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
        
        # Perbaikan otomatis: Jika geometry segmen kosong tapi geometry ruas ada, generate ulang
        if not segmen.geometry and segmen.ruas_jalan.geometry:
            try:
                segmen.geometry = segmen.ruas_jalan._get_segment_geometry(float(segmen.km_awal), float(segmen.km_akhir))
                segmen.save(update_fields=['geometry'])
            except Exception as e:
                print(f"Repair geometry error: {e}")

        # Gunakan geometry yang tersimpan di model
        geometry = None
        if segmen.geometry:
            try:
                geometry = json.loads(segmen.geometry)
            except:
                pass
        
        if geometry:
            # 1. Feature LineString (Garis Jalan)
            feature_line = {
                'type': 'Feature',
                'id': f"line_{segmen.id}",
                'properties': {
                    'type': 'line',
                    'segmen_id': segmen.id,
                    'ruas_nama': segmen.ruas_jalan.nama_ruas,
                    'km_awal': float(segmen.km_awal),
                    'km_akhir': float(segmen.km_akhir),
                    'kategori': kategori,
                    'zscore': zscore,
                    'color': color,
                    'url': f'/kecelakaan/segmen/{segmen.id}/'
                },
                'geometry': geometry
            }
            features.append(feature_line)

            # 2. Feature Point (Marker di tengah segmen)
            if geometry.get('coordinates'):
                coords = geometry['coordinates']
                mid_idx = len(coords) // 2
                mid_point = coords[mid_idx]
                
                feature_point = {
                    'type': 'Feature',
                    'id': f"point_{segmen.id}",
                    'properties': {
                        'type': 'marker',
                        'segmen_id': segmen.id,
                        'ruas_nama': segmen.ruas_jalan.nama_ruas,
                        'km_awal': float(segmen.km_awal),
                        'km_akhir': float(segmen.km_akhir),
                        'kategori': kategori,
                        'color': color
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': mid_point
                    }
                }
                features.append(feature_point)
    
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
def api_geoapify_routing(request):
    """
    API untuk mendapatkan rute jalan dari Geoapify.
    Input: lat_awal, lon_awal, lat_akhir, lon_akhir
    Output: JSON berisi distance_km dan geometry
    """
    lat_awal = request.GET.get('lat_awal')
    lon_awal = request.GET.get('lon_awal')
    lat_akhir = request.GET.get('lat_akhir')
    lon_akhir = request.GET.get('lon_akhir')

    if not all([lat_awal, lon_awal, lat_akhir, lon_akhir]):
        return JsonResponse({'status': 'error', 'message': 'Parameter tidak lengkap'}, status=400)

    api_key = os.getenv('GEOAPIFY_API_KEY')
    if not api_key:
        return JsonResponse({'status': 'error', 'message': 'API Key Geoapify tidak ditemukan di .env'}, status=500)

    url = f"https://api.geoapify.com/v1/routing?waypoints={lat_awal},{lon_awal}|{lat_akhir},{lon_akhir}&mode=drive&apiKey={api_key}"

    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'features' in data and len(data['features']) > 0:
                route_feature = data['features'][0]
                distance_meters = route_feature['properties']['distance']
                distance_km = round(distance_meters / 1000, 3)
                
                return JsonResponse({
                    'status': 'success',
                    'distance_km': distance_km,
                    'geometry': route_feature['geometry']
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Rute tidak ditemukan'}, status=404)
        else:
            return JsonResponse({'status': 'error', 'message': f'API Error: {response.status_code}'}, status=response.status_code)
            
    except requests.exceptions.Timeout:
        return JsonResponse({'status': 'error', 'message': 'API Request timeout'}, status=504)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(['GET'])
@login_required(login_url='login')
def api_geoapify_reverse_geocoding(request):
    """
    API untuk mendapatkan informasi alamat dari koordinat (Geoapify).
    Input: lat, lon
    Output: JSON berisi nama_jalan, wilayah (kota/kab, provinsi)
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not all([lat, lon]):
        return JsonResponse({'status': 'error', 'message': 'Parameter tidak lengkap'}, status=400)

    api_key = os.getenv('GEOAPIFY_API_KEY')
    if not api_key:
        return JsonResponse({'status': 'error', 'message': 'API Key Geoapify tidak ditemukan di .env'}, status=500)

    url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={api_key}"

    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'features' in data and len(data['features']) > 0:
                properties = data['features'][0]['properties']
                
                # Ekstrak informasi yang dibutuhkan
                nama_jalan = properties.get('street', properties.get('name', 'Tidak diketahui'))
                kota = properties.get('city', properties.get('county', ''))
                provinsi = properties.get('state', '')
                
                wilayah = f"{kota}, {provinsi}".strip(", ")
                
                return JsonResponse({
                    'status': 'success',
                    'nama_jalan': nama_jalan,
                    'wilayah': wilayah,
                    'kota_kab': kota,
                    'provinsi': provinsi
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Data lokasi tidak ditemukan'}, status=404)
        else:
            return JsonResponse({'status': 'error', 'message': f'API Error: {response.status_code}'}, status=response.status_code)
            
    except requests.exceptions.Timeout:
        return JsonResponse({'status': 'error', 'message': 'API Request timeout'}, status=504)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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



# ===============================
# AHC VIEWS
# ===============================

# ================================
# HALAMAN DATA
# ================================
@login_required(login_url='login')
def ahc_data(request):
    return render(request, 'coreapp/ahc/data.html')


# ================================
# HALAMAN PROSES
# ================================
@login_required(login_url='login')
def ahc_proses(request):
    context = {}

    # Ambil data preprocessing dari session
    summary_df = request.session.get('summary_df')
    jumlah_data_asli = request.session.get('jumlah_data_asli')

    # Ambil hasil clustering dari session
    hasil_cluster = request.session.get('hasil_cluster')
    summary_cluster = request.session.get('summary_cluster')
    jumlah_cluster = request.session.get('jumlah_cluster')

    # Jika sudah ada preprocessing
    if summary_df:
        context['preview'] = summary_df
        context['jumlah_data'] = len(summary_df)
        context['jumlah_data_asli'] = jumlah_data_asli

    # Jika sudah ada clustering
    if hasil_cluster:
        context['hasil_cluster'] = hasil_cluster
        context['summary_cluster'] = summary_cluster
        context['jumlah_cluster'] = jumlah_cluster

    return render(request, 'coreapp/ahc/proses.html', context)


# ================================
# HALAMAN HASIL
# ================================
@login_required(login_url='login')
def ahc_hasil(request):
    return render(request, 'coreapp/ahc/hasil.html')

# ================================
# PREPROCESSING DATA
# ================================

@login_required(login_url='login')
def preprocessing_data(request):
    context = {}

    if request.method == "POST":
        file = request.FILES.get('file')

        if file:
            # 🔥 RESET SEMUA SESSION LAMA (lebih lengkap)
            for key in [
                'hasil_cluster',
                'summary_cluster',
                'jumlah_cluster',
                'jumlah_data',
                'silhouette_score',
                'X_scaled',
                'summary_df',
                'jumlah_data_asli'
            ]:
                request.session.pop(key, None)

            # ✅ Simpan nama file aktif
            request.session['uploaded_file_name'] = file.name

            # 1️⃣ Baca file
            df = pd.read_excel(file)

            context['preview_asli'] = df.head().to_html(
                classes="table-auto w-full text-sm",
                index=False
            )

            # Simpan jumlah data asli
            request.session['jumlah_data_asli'] = len(df)

            # 2️⃣ Handle missing value
            df.replace('-', np.nan, inplace=True)

            numeric_cols = ['Umur', 'Jumlah Kejadian']
            numeric_cols = [c for c in numeric_cols if c in df.columns]

            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            if 'Jumlah Kejadian' in df.columns:
                df['Jumlah Kejadian'] = df['Jumlah Kejadian'].fillna(1)
            else:
                df['Jumlah Kejadian'] = 1

            # 3️⃣ Hapus umur <= 0
            if 'Umur' in df.columns:
                df = df[df['Umur'] > 0]

            # 4️⃣ Konversi jam ke kategori waktu
            def konversi_waktu(jam):
                try:
                    if isinstance(jam, str) and ':' in jam:
                        jam = int(jam.split(':')[0])
                    else:
                        jam = int(jam)
                except:
                    return "Tidak Diketahui"

                if 0 <= jam < 6:
                    return "Dini Hari"
                elif 6 <= jam < 12:
                    return "Pagi Hari"
                elif 12 <= jam < 18:
                    return "Siang Hari"
                elif 18 <= jam < 24:
                    return "Malam Hari"
                else:
                    return "Tidak Diketahui"

            if 'Jam' in df.columns:
                df['Waktu Kejadian'] = df['Jam'].apply(konversi_waktu)
            else:
                df['Waktu Kejadian'] = 'Tidak Diketahui'

            # 5️⃣ Dummy kendaraan
            kendaraan_cols = ['Motor', 'Mobil', 'Truk/Bus']

            if 'Jenis Kendaraan' in df.columns:
                for k in kendaraan_cols:
                    df[k] = (
                        df['Jenis Kendaraan']
                        .str.strip()
                        .str.lower()
                        .eq(k.lower())
                        .astype(int)
                        * df['Jumlah Kejadian']
                    )
            else:
                for k in kendaraan_cols:
                    df[k] = 0

            # 6️⃣ Faktor penyebab
            if 'Penyebab' in df.columns:
                df['Penyebab_clean'] = df['Penyebab'].str.strip().str.lower()
            else:
                df['Penyebab_clean'] = ''

            df['Faktor Pengemudi'] = df['Jumlah Kejadian']
            df['Faktor Jalan'] = 0
            df['Faktor Kendaraan'] = 0
            df['Faktor Lingkungan'] = 0

            # 7️⃣ Dummy waktu
            waktu_cols = ['Dini Hari', 'Pagi Hari', 'Siang Hari', 'Malam Hari']
            for w in waktu_cols:
                df[w] = (df['Waktu Kejadian'] == w).astype(int) * df['Jumlah Kejadian']

            # 8️⃣ Group by umur
            summary_cols = (
                ['Jumlah Kejadian']
                + kendaraan_cols
                + ['Faktor Pengemudi', 'Faktor Jalan', 'Faktor Kendaraan', 'Faktor Lingkungan']
                + waktu_cols
            )

            if 'Umur' in df.columns:
                summary_df = df.groupby('Umur')[summary_cols].sum().reset_index()
            else:
                summary_df = df[summary_cols].sum().to_frame().T

            summary_df = summary_df.round().astype(int)

            # 9️⃣ Scaling
            fitur_clustering = summary_df.copy()
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(fitur_clustering)

            # 🔟 Simpan ke session
            # 🔟 Simpan hasil preprocessing saja
            request.session['summary_df'] = summary_df.to_dict(orient='records')
            request.session['X_scaled'] = X_scaled.tolist()
            request.session.modified = True

            context['preview'] = summary_df.to_dict(orient='records')
            context['jumlah_data'] = len(summary_df)
            context['jumlah_data_asli'] = request.session.get('jumlah_data_asli')
                # Setelah upload via AHC preprocessing, redirect ke halaman proses AHC
            return redirect('ahc_proses')

            # Untuk GET (atau jika tidak ada file POST), tampilkan halaman proses AHC
            return render(request, 'coreapp/ahc/proses.html', context)

# #########################################################################################
# START K-MEANS SECTION
# #########################################################################################

# #########################################################################################
# START K-MEANS SECTION
# #########################################################################################

# ================================
# PREPROCESSING DATA K-MEANS
# ================================
def _perform_kmeans_preprocessing(df):
    """Helper function to process dataframe for K-Means"""
    df.replace('-', np.nan, inplace=True)
    df.columns = df.columns.str.strip()

    # Rename kolom ke format standar
    col_map = {}
    for col in df.columns:
        low = col.lower().replace(' ', '_')
        if 'jam' in low:               col_map[col] = 'Jam'
        elif 'hari' in low:            col_map[col] = 'Hari'
        elif 'tanggal' in low:         col_map[col] = 'Tanggal'
        elif 'no' == low:              col_map[col] = 'No'
        elif 'umur' in low or 'usia' in low: col_map[col] = 'Umur'
        elif 'tkp' in low or 'lokasi' in low: col_map[col] = 'TKP'
        elif 'penyebab' in low:        col_map[col] = 'Penyebab'
        elif 'jenis_kendaraan' in low or 'jenis kendaraan' == col.lower(): col_map[col] = 'Jenis Kendaraan'
        elif 'tipe_kendaraan' in low or 'tipe kendaraan' == col.lower():  col_map[col] = 'Tipe Kendaraan'
        elif 'kerugian' in low:        col_map[col] = 'Kerugian Material'
    df = df.rename(columns=col_map)

    # Pastikan Umur adalah numerik
    if 'Umur' in df.columns:
        df['Umur'] = pd.to_numeric(df['Umur'], errors='coerce').fillna(0)
    else:
        df['Umur'] = 0

    def jam_ke_numerik(val):
        try:
            s = str(val).strip().replace(',', '.').replace(' ', '')
            if ':' in s:
                parts = s.split(':')
                return float(parts[0]) + float(parts[1]) / 60.0
            elif '.' in s:
                parts = s.split('.')
                return float(parts[0]) + float(parts[1]) / 60.0
            else:
                return float(s)
        except:
            return np.nan

    if 'Jam' in df.columns:
        df['Jam_Numerik'] = df['Jam'].apply(jam_ke_numerik)
    else:
        df['Jam_Numerik'] = 0

    hari_map = {
        'senin': 1, 'selasa': 2, 'rabu': 3,
        'kamis': 4, 'jumat': 5, 'sabtu': 6, 'minggu': 7
    }
    if 'Hari' in df.columns:
        df['Hari_Numerik'] = df['Hari'].str.strip().str.lower().map(hari_map).fillna(0)
    else:
        df['Hari_Numerik'] = 0

    # Filter data yang tidak valid
    df = df.dropna(subset=['Jam_Numerik', 'Hari_Numerik'])
    df = df[df['Hari_Numerik'] > 0]
    df = df.reset_index(drop=True)

    # ─────────────────────────────────────────────────
    # AGREGASI LANJUTAN (Umur, Kendaraan, Faktor)
    # ─────────────────────────────────────────────────
    
    # Faktor mapping
    pengemudi_keywords = ['konsentrasi', 'mengantuk', 'apill', 'arus', 'marka', 'pintu', 'jalur', 'kiri', 'petugas', 'ngerem', 'sein', 'laju', 'utama', 'jarak']
    jalan_keywords = ['lubang', 'gelincir', 'licin', 'rusak']
    kendaraan_keywords = ['ban', 'rem', 'lampu', 'mesin']
    lingkungan_keywords = ['cuaca', 'hujan', 'kabut', 'gelap']

    def get_faktor(p):
        p = str(p).lower()
        if any(k in p for k in pengemudi_keywords): return 'Pengemudi'
        if any(k in p for k in jalan_keywords): return 'Jalan'
        if any(k in p for k in kendaraan_keywords): return 'Kendaraan'
        if any(k in p for k in lingkungan_keywords): return 'Lingkungan'
        return 'Pengemudi' # Default

    df['Faktor'] = df['Penyebab'].apply(get_faktor)
    
    # Kendaraan mapping
    def get_tipe_group(j):
        j = str(j).lower()
        if 'motor' in j: return 'Motor'
        if 'mobil' in j or 'pribadi' in j: return 'Mobil'
        if 'truk' in j or 'bus' in j or 'fuso' in j or 'box' in j: return 'Truk/Bus'
        return 'Lainnya'

    df['Tipe_Group'] = df['Jenis Kendaraan'].apply(get_tipe_group)

    # Jam_Slot (0-23)
    df['Jam_Slot'] = df['Jam_Numerik'].apply(
        lambda x: 0 if int(x) >= 24 else int(x) if pd.notna(x) else 0
    )

    # Hitung aggregasi per slot (Hari, Jam)
    summary_df = df.groupby(['Hari_Numerik', 'Jam_Slot']).agg(
        Jumlah_Kejadian=('Jam_Slot', 'count'),
        Rerata_Umur=('Umur', 'mean'),
        Motor=('Tipe_Group', lambda x: (x == 'Motor').sum()),
        Mobil=('Tipe_Group', lambda x: (x == 'Mobil').sum()),
        Truk_Bus=('Tipe_Group', lambda x: (x == 'Truk/Bus').sum()),
        Faktor_Pengemudi=('Faktor', lambda x: (x == 'Pengemudi').sum()),
        Faktor_Jalan=('Faktor', lambda x: (x == 'Jalan').sum()),
        Faktor_Kendaraan=('Faktor', lambda x: (x == 'Kendaraan').sum()),
        Faktor_Lingkungan=('Faktor', lambda x: (x == 'Lingkungan').sum()),
    ).reset_index()

    # Periode Waktu (Dini, Pagi, Siang, Malam)
    summary_df['Dini Hari']  = summary_df['Jam_Slot'].apply(lambda x: 1 if 0 <= x < 6 else 0)
    summary_df['Pagi Hari']  = summary_df['Jam_Slot'].apply(lambda x: 1 if 6 <= x < 12 else 0)
    summary_df['Siang Hari'] = summary_df['Jam_Slot'].apply(lambda x: 1 if 12 <= x < 18 else 0)
    summary_df['Malam Hari'] = summary_df['Jam_Slot'].apply(lambda x: 1 if 18 <= x < 24 else 0)

    # Label & Formatting
    hari_label = {1:'Senin',2:'Selasa',3:'Rabu',4:'Kamis',5:'Jumat',6:'Sabtu',7:'Minggu'}
    summary_df['Hari'] = summary_df['Hari_Numerik'].map(hari_label)
    summary_df['Jam']  = summary_df['Jam_Slot'].apply(lambda x: f"{x:02d}:00")
    
    # Final column ordering & renaming
    summary_df = summary_df.sort_values(['Hari_Numerik', 'Jam_Slot']).reset_index(drop=True)
    summary_df['No'] = summary_df.index + 1
    
    # Simpan Jam_Numerik asli untuk clustering
    summary_df['Jam_Numerik_Original'] = summary_df['Jam_Slot']
    
    summary_df = summary_df.rename(columns={
        'Jam_Slot': 'Jam_Numerik',
        'Rerata_Umur': 'Umur',
        'Truk_Bus': 'Truk/Bus',
        'Faktor_Pengemudi': 'Faktor Pengemudi',
        'Faktor_Jalan': 'Faktor Jalan',
        'Faktor_Kendaraan': 'Faktor Kendaraan',
        'Faktor_Lingkungan': 'Faktor Lingkungan',
    })

    # Bulatkan Umur
    summary_df['Umur'] = summary_df['Umur'].round(0).astype(int)

    # Re-map Jumlah_Kejadian ke "Jumlah Kejadian" untuk preview
    summary_df['Jumlah Kejadian'] = summary_df['Jumlah_Kejadian']
    
    # Pilih Kolom yang ditampilkan (Sesuai Permintaan User)
    summary_df = summary_df[[
        'No', 'Hari', 'Jam', 'Umur', 'Jumlah Kejadian', 
        'Motor', 'Mobil', 'Truk/Bus', 
        'Faktor Pengemudi', 'Faktor Jalan', 'Faktor Kendaraan', 'Faktor Lingkungan',
        'Dini Hari', 'Pagi Hari', 'Siang Hari', 'Malam Hari',
        'Hari_Numerik', 'Jam_Numerik', 'Jumlah_Kejadian' # Tetap bawa ini untuk proses_cluster
    ]]

    for col in summary_df.columns:
        if pd.api.types.is_datetime64_any_dtype(summary_df[col]):
            summary_df[col] = summary_df[col].dt.strftime('%d %B %Y')
        elif summary_df[col].dtype == object:
            summary_df[col] = summary_df[col].apply(
                lambda x: x.strftime('%d %B %Y') if hasattr(x, 'strftime') else x
            )
            
    return summary_df

@login_required(login_url='login')
def preprocessing(request):
    context = {}
    show_all = request.GET.get('show_all') == '1'
    use_db = request.GET.get('use_db') == '1'

    # =========================
    # 1️⃣ PROSES INPUT (POST/DB)
    # =========================
    df = None
    
    if request.method == "POST" or use_db:
        # Reset session
        for key in ['hasil_cluster', 'summary_cluster', 'jumlah_cluster', 'jumlah_data',
                    'silhouette_score', 'X_scaled', 'summary_df', 'jumlah_data_asli',
                    'ai_dashboard_analysis', 'ai_recommendation_data']:
            request.session.pop(key, None)

        if use_db:
            data_db = KMeansData.objects.all().values()
            if not data_db:
                messages.error(request, "Data di database masih kosong.")
                return redirect('kmeans_data_list')
            df = pd.DataFrame(list(data_db))
            # Map database fields to standard names
            df = df.rename(columns={
                'tkp': 'TKP', 'penyebab': 'Penyebab', 'hari': 'Hari',
                'tanggal': 'Tanggal', 'jam': 'Jam', 'umur': 'Umur',
                'jenis_kendaraan': 'Jenis Kendaraan', 'tipe_kendaraan': 'Tipe Kendaraan',
                'kerugian_material': 'Kerugian Material'
            })
            request.session['uploaded_file_name'] = "Database"
        else:
            file = request.FILES.get('file')
            if file:
                df = pd.read_excel(file)
                request.session['uploaded_file_name'] = file.name

        if df is not None:
            request.session['jumlah_data_asli'] = len(df)
            summary_df = _perform_kmeans_preprocessing(df)
            
            # Simpan ke session
            request.session['summary_df'] = summary_df.to_dict(orient='records')
            request.session['jumlah_data_bersih'] = len(summary_df)
            request.session.modified = True

            preview_df = summary_df.head(10) if not show_all else summary_df
            context['preview'] = preview_df.to_dict(orient='records')
            context['is_full_preview'] = show_all
            context['jumlah_data_bersih'] = len(summary_df)
            context['jumlah_data_awal'] = len(df)

    # ─────────────────────────────────────────────────────
    # 2️⃣ LOAD DARI SESSION (GET request / kembali ke halaman)
    # ─────────────────────────────────────────────────────
    summary_json = request.session.get('summary_df')
    if summary_json:
        if isinstance(summary_json, list):
            df = pd.DataFrame(summary_json)
        else:
            try:
                df = pd.read_json(StringIO(summary_json), orient='records')
            except Exception:
                df = pd.DataFrame(summary_json)

        context['preview']            = df.to_dict(orient='records') if show_all else df.head(10).to_dict(orient='records')
        context['is_full_preview']    = show_all
        context['jumlah_data_bersih'] = len(df)

    # Tampilkan hasil cluster dari session (jika sudah pernah proses)
    hasil_cluster_session = request.session.get('hasil_cluster')
    k_session             = request.session.get('k')
    show_all_hasil        = request.GET.get('show_all_hasil') == '1'

    if hasil_cluster_session and k_session:
        context['hasil_cluster'] = hasil_cluster_session if show_all_hasil else hasil_cluster_session[:10]
        context['is_full_hasil'] = show_all_hasil
        context['k']             = k_session

    return render(request, 'coreapp/k-means/preprocessing.html', context)





# ================================
# RESET K-MEANS
# ================================
@login_required(login_url='login')
def reset_k_means(request):
    keys = ['hasil_cluster', 'summary_cluster', 'jumlah_cluster', 'jumlah_data',
            'silhouette_score', 'X_scaled', 'summary_df', 'uploaded_file_name', 
            'jumlah_data_asli', 'ai_dashboard_analysis', 'ai_recommendation_data']
    for key in keys:
        request.session.pop(key, None)
    return redirect('preprocessing')


# ==========================================
# PROSES K-MEANS CLUSTERING
# ==========================================
@login_required(login_url='login')
def proses_cluster(request):

    if request.method != "GET":
        return redirect('preprocessing')

    try:
        k = int(request.GET.get('k', 3))
    except ValueError:
        k = 3
    k = max(2, min(k, 3))

    summary_json = request.session.get('summary_df')
    if not summary_json:
        return redirect('preprocessing')

    if isinstance(summary_json, list):
        df = pd.DataFrame(summary_json)
    else:
        try:
            df = pd.read_json(StringIO(summary_json), orient='records')
        except Exception:
            df = pd.DataFrame(summary_json)

    if df.empty:
        return redirect('preprocessing')

    # ─────────────────────────────────────────────────────
    # FITUR K-MEANS: Hari + Jam + Jumlah_Kejadian
    # → K-Means mengelompokkan SLOT WAKTU berdasarkan:
    #   (1) posisi dalam minggu (Hari)
    #   (2) posisi dalam hari (Jam)
    #   (3) seberapa sering terjadi kecelakaan (Jumlah_Kejadian)
    # Slot dengan Jumlah_Kejadian tinggi → CLUSTER TINGGI (periode rawan)
    # ─────────────────────────────────────────────────────
    feature_cols = [col for col in ['Hari_Numerik', 'Jam_Numerik', 'Jumlah_Kejadian']
                    if col in df.columns]

    if not feature_cols:
        return redirect('preprocessing')

    X = df[feature_cols].fillna(0)

    if len(X) < k:
        k = len(X)

    try:
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Hitung Data Elbow (Inertia untuk K=1 s/d 10)
        elbow_data = []
        K_limit = min(11, len(X_scaled) + 1)
        for i in range(1, K_limit):
            km_temp = KMeans(n_clusters=i, random_state=42, n_init=10)
            km_temp.fit(X_scaled)
            elbow_data.append(float(km_temp.inertia_))
        request.session['elbow_data'] = elbow_data

        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        df['Cluster'] = model.fit_predict(X_scaled) + 1  # 1,2,3

    except Exception as e:
        print("ERROR CLUSTERING:", e)
        return redirect('preprocessing')

    # ─────────────────────────────────────────────────────
    # LABELING: berdasarkan rata-rata Jumlah_Kejadian per cluster
    # Cluster dengan rata-rata frekuensi TERTINGGI → Tinggi (periode rawan)
    # Cluster dengan rata-rata frekuensi TERENDAH  → Rendah (periode aman)
    # ─────────────────────────────────────────────────────
    if 'Jumlah_Kejadian' in df.columns:
        # Urutkan dari rata-rata frekuensi TERENDAH → TERTINGGI
        sorted_clusters = df.groupby('Cluster')['Jumlah_Kejadian'].mean().sort_values()
    else:
        sorted_clusters = df.groupby('Cluster').size().sort_values()

    kategori = ['Rendah', 'Sedang', 'Tinggi']
    label_map = {}
    for i, cluster_id in enumerate(sorted_clusters.index):
        label_map[cluster_id] = kategori[i] if i < len(kategori) else f"Cluster {cluster_id}"

    df['Kategori'] = df['Cluster'].map(label_map)

    # ─────────────────────────────────────────────────────
    # BERSIHKAN KOLOM UNTUK DISPLAY
    # ─────────────────────────────────────────────────────
    # Simpan versi lengkap di session
    full_df_dict = df.to_dict(orient='records')
    
    # Versi untuk ditampilkan (sembunyikan numerik)
    display_cols = [c for c in df.columns if c not in ['Hari_Numerik', 'Jam_Numerik', 'Jumlah_Kejadian', 'Cluster', 'Kategori']]
    # Pastikan 'Kategori' dan 'Cluster' ada di paling kanan
    df_display = df[display_cols + ['Kategori', 'Cluster']]

    # ─────────────────────────────────────────────────────
    # SIMPAN HASIL
    # ─────────────────────────────────────────────────────
    request.session['hasil_cluster'] = full_df_dict
    request.session['hasil_cluster_display'] = df_display.to_dict(orient='records')
    request.session['k'] = k
    request.session.modified = True

    # ─────────────────────────────────────────────────────
    # Render kembali ke preprocessing.html dengan hasil cluster
    # User bisa lihat hasil di halaman ini, lalu klik "Lihat Analisis Lengkap"
    # ─────────────────────────────────────────────────────
    show_all       = request.GET.get('show_all') == '1'
    show_all_hasil = request.GET.get('show_all_hasil') == '1'

    # Muat kembali preview dari session
    summary_json = request.session.get('summary_df')
    preview_df   = pd.DataFrame()
    if summary_json:
        try:
            preview_df = pd.DataFrame(summary_json) if isinstance(summary_json, list) \
                         else pd.read_json(StringIO(summary_json), orient='records')
        except Exception:
            preview_df = pd.DataFrame()

    hasil_list = request.session.get('hasil_cluster_display', df_display.to_dict(orient='records'))

    return render(request, 'coreapp/k-means/preprocessing.html', {
        'preview'            : (preview_df.to_dict(orient='records') if show_all
                                else preview_df.head(10).to_dict(orient='records'))
                               if not preview_df.empty else [],
        'is_full_preview'    : show_all,
        'jumlah_data_bersih' : len(preview_df) if not preview_df.empty else len(df),
        'jumlah_data_awal'   : request.session.get('jumlah_data_asli'),
        'hasil_cluster'      : hasil_list if show_all_hasil else hasil_list[:10],
        'is_full_hasil'      : show_all_hasil,
        'k'                  : k,
    })


# ==========================================
# HALAMAN HASIL K-MEANS
# ==========================================
@login_required(login_url='login')
def hasil(request):
    data = request.session.get("hasil_cluster")

    if not data:
        # Jika belum ada data, jangan redirect, tapi tampilkan pesan di template
        return render(request, "coreapp/k-means/hasil.html", {"belum_clustering": True})

    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        try:
            df = pd.read_json(StringIO(data), orient='records')
        except Exception:
            df = pd.DataFrame(data)

    if df.empty:
        return render(request, "coreapp/k-means/hasil.html", {"belum_clustering": True})

    # Distribusi per cluster
    cluster_count       = df['Cluster'].value_counts().sort_index()
    cluster_labels      = [f"Cluster {i}" for i in cluster_count.index]
    cluster_values      = [int(v) for v in cluster_count.values]
    total               = sum(cluster_values)
    cluster_percentages = [round((v / total) * 100, 2) if total > 0 else 0 for v in cluster_values]

    # ─────────────────────────────────────────────────────
    # DATA SCATTER: X=Jam_Numerik, Y=Hari_Numerik
    # Ukuran titik = Jumlah_Kejadian (semakin banyak → titik lebih besar)
    # ─────────────────────────────────────────────────────
    scatter_data = []
    for _, row in df.iterrows():
        jam      = row.get('Jam_Numerik', None)
        hari     = row.get('Hari_Numerik', None)
        cluster  = row.get('Cluster', 0)
        kategori = row.get('Kategori', '')
        jumlah   = row.get('Jumlah_Kejadian', 1)   # frekuensi slot ini
        if jam is not None and hari is not None:
            scatter_data.append({
                'x'        : int(jam),                  # jam slot (0-23)
                'y'        : float(hari),
                'cluster'  : int(cluster),
                'kategori' : str(kategori),
                'jumlah'   : int(jumlah),               # untuk ukuran titik
            })


    x_col = 'Jam_Numerik'
    y_col = 'Hari_Numerik'

    jumlah_data_awal   = request.session.get('jumlah_data_asli')
    jumlah_data_bersih = len(df)

    hasil_cluster_list = df.to_dict(orient='records')
    show_all           = request.GET.get('show_all') == '1'

    context = {
        "hasil_cluster":      hasil_cluster_list if show_all else hasil_cluster_list[:10],
        "is_full_preview":    show_all,
        "jumlah_data_bersih": jumlah_data_bersih,
        "hasil_cluster_json": json.dumps(hasil_cluster_list),
        "cluster_labels":      json.dumps(cluster_labels),
        "cluster_values":      cluster_values,
        "cluster_values_json": json.dumps(cluster_values),
        "cluster_percentages": cluster_percentages,
        "chart_data":         json.dumps(scatter_data),
        "chart_data_json":    json.dumps(scatter_data),
        "x_col_name":         "Jam (0-24)",
        "y_col_name":         "Hari (1=Senin...7=Minggu)",
        "jumlah_data_awal":    jumlah_data_awal,
        "jumlah_data_bersih":  jumlah_data_bersih,
        "elbow_data_json":     json.dumps(request.session.get('elbow_data', [])),
    }

    return render(request, "coreapp/k-means/hasil.html", context)


# ==========================================
# REKOMENDASI KEBIJAKAN (RUMUSAN MASALAH 2)
# ==========================================
@login_required(login_url='login')
def rekomendasi_kebijakan(request):
    data = request.session.get("hasil_cluster")
    # 1. Pastikan sudah ada hasil clustering
    if not data:
        return render(request, "coreapp/k-means/rekomendasi.html", {"belum_clustering": True})

    # 2. Pastikan sudah klik tombol Rekomendasi AI (data AI ada di session)
    ai_data = request.session.get("ai_recommendation_data")
    if not ai_data:
        return render(request, "coreapp/k-means/rekomendasi.html", {"belum_ai": True})

    df = pd.DataFrame(data)
    tinggi_df = df[df['Kategori'].str.lower() == 'tinggi'].sort_values(by='Jumlah_Kejadian', ascending=False)
    
    # 2. Ringkasan Top 10 Slot Paling Berbahaya
    critical_hours = tinggi_df.head(10).to_dict(orient='records')
    
    # 3. Statistik untuk Justifikasi
    total_slots = 168
    count_tinggi = len(df[df['Kategori'].str.lower() == 'tinggi'])
    count_sedang = len(df[df['Kategori'].str.lower() == 'sedang'])
    pct_tinggi = round((count_tinggi / total_slots) * 100, 1)
    
    context = {
        "critical_hours": critical_hours,
        "pct_tinggi": pct_tinggi,
        "count_tinggi": count_tinggi,
        "count_sedang": count_sedang,
        "k": request.session.get('k', 3),
        "today": pd.Timestamp.now().strftime('%d %B %Y'),
        "ai_data": request.session.get('ai_recommendation_data')
    }
    
    return render(request, "coreapp/k-means/rekomendasi.html", context)


# ==========================================
# AJAX: GET AI RECOMMENDATION (GEMINI)
# ==========================================
import requests

@login_required(login_url='login')
def get_ai_recommendation(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)

    data = request.session.get("hasil_cluster")
    if not data:
        return JsonResponse({"success": False, "message": "Data cluster tidak ditemukan"}, status=400)

    df = pd.DataFrame(data)
    
    # Ringkasan data untuk prompt
    total = len(df)
    tinggi = len(df[df['Kategori'].str.lower() == 'tinggi'])
    persen = round((tinggi / total) * 100, 1)
    
    # Ambil 20 data teratas (High Risk) untuk context AI
    tinggi_df = df[df['Kategori'].str.lower() == 'tinggi'].sort_values(by='Jumlah_Kejadian', ascending=False)
    cluster_sample = tinggi_df.head(20).to_dict(orient='records')
    
    waktu_rawan = "Beberapa titik kritis teridentifikasi"
    if not tinggi_df.empty:
        peak = tinggi_df.iloc[0]
        waktu_rawan = f"{peak['Hari']} pukul {peak['Jam']}"

    # Ambil API KEY dari Database
    config = AIConfig.objects.filter(tipe='kmeans').first()
    if not config or not config.api_key:
        return JsonResponse({"success": False, "message": "API Key belum dikonfigurasi di menu Data."}, status=400)
    
    api_key = config.api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

    # PROMPT CONSTRUCTION
    prompt = f"""
    Anda adalah asisten analis kecelakaan lalu lintas untuk Polres Madiun.
    
    DATA CLUSTERING (Sample Top 20 High Risk):
    {json.dumps(cluster_sample)}
    
    STATISTIK TOTAL:
    - Total: {total} slot waktu dianalisis
    - Risiko Tinggi: {tinggi} slot ({persen}%)
    - Waktu terawan utama: {waktu_rawan}
    INSTRUKSI:
    Buatkan usulan penanganan rawan kecelakaan dalam format JSON murni:
    {{
      "ringkasan": "2-3 kalimat temuan utama",
      "prioritas_tinggi": [
        {{
          "waktu": "Hari, rentang jam",
          "kejadian": 100,
          "tindakan": {{
            "patroli": "deskripsi spesifik",
            "infrastruktur": ["item1", "item2"],
            "sosialisasi": ["item1", "item2"]
          }}
        }}
      ],
      "prioritas_sedang": [],
      "prioritas_rendah": [],
      "jadwal_patroli": [
        {{
          "hari": "Hari",
          "jam": "Jam",
          "unit": 2,
          "fokus": "deskripsi fokus patroli"
        }}
      ],
      "program": {{
        "jangka_pendek": [],
        "jangka_menengah": [],
        "jangka_panjang": []
      }},
      "target_kpi": {{
        "pengurangan": "target %",
        "indikator": ["indikator1", "indikator2"]
      }},
      "catatan": "catatan penutup"
    }}
    
    PENTING: Berikan response hanya JSON murni tanpa karakter markdown atau backticks.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, json=payload, timeout=30)
        res_json = response.json()
        raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()
        ai_data = json.loads(clean_text)
        request.session['ai_recommendation_data'] = ai_data
        request.session.modified = True
        return JsonResponse({"success": True, "data": ai_data})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# ==========================================
# AJAX: GET AI DASHBOARD ANALYSIS (GEMINI)
# ==========================================
@login_required(login_url='login')
def analyze_accident_clustering(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)

    # Persistensi: Cek apakah sudah ada di session
    cached_analysis = request.session.get('ai_dashboard_analysis')
    if cached_analysis and request.POST.get('force') != '1':
        return JsonResponse({"success": True, "analysis": cached_analysis})

    data = request.session.get("hasil_cluster")
    if not data:
        return JsonResponse({"success": False, "message": "Data cluster tidak ditemukan"}, status=400)

    df = pd.DataFrame(data)
    total_incidents = int(df['Jumlah_Kejadian'].sum())
    total_slots = len(df)

    # 1. Agregasi Bar Chart
    clusters = []
    for kat in ['Rendah', 'Sedang', 'Tinggi']:
        count = int(df[df['Kategori'] == kat]['Jumlah_Kejadian'].sum())
        pct = round((count / total_incidents) * 100, 1) if total_incidents > 0 else 0
        clusters.append({"name": kat, "count": count, "percentage": pct})

    # 2. Agregasi Scatter Plot (Hotspots)
    hotspots = df.sort_values('Jumlah_Kejadian', ascending=False).head(5)
    hotspot_list = []
    for _, row in hotspots.iterrows():
        hotspot_list.append({
            "day": row['Hari'], "hour": row['Jam'], 
            "count": int(row['Jumlah_Kejadian']), "cluster": row['Kategori']
        })

    # 3. Agregasi Line Chart (Peaks & Transitions)
    hourly_avg = df.groupby('Jam_Numerik')['Jumlah_Kejadian'].mean()
    peaks = []
    if not hourly_avg.empty:
        max_idx = hourly_avg.idxmax()
        peaks.append({"label": "Puncak", "hour": f"{int(max_idx):02d}:00", "val": round(float(hourly_avg[max_idx]), 1)})

    # Construct Prompt
    prompt = f"""
    Analisis data clustering K-Means kecelakaan berikut (Total {total_incidents} kejadian):

    1. DISTRIBUSI CLUSTER:
    {json.dumps(clusters)}

    2. HOTSPOTS (Titik Tertinggi):
    {json.dumps(hotspot_list)}

    3. TREN 24 JAM (Rata-rata Kejadian):
    {hourly_avg.to_dict()}

    INSTRUKSI:
    Berikan analisis untuk 3 chart (Bar Chart, Scatter Plot, Line Chart) dalam format JSON murni:
    {{
      "barChart": {{ "summary": "...", "insights": [{{ "text": "...", "dataPoint": "...", "emphasis": "high/medium/low" }}] }},
      "scatterPlot": {{ "summary": "...", "insights": [...] }},
      "lineChart": {{ "summary": "...", "insights": [...] }}
    }}
    - Summary 1-2 kalimat.
    - 3-4 insight per chart dengan angka spesifik.
    - Bahasa Indonesia profesional.
    - Tanpa saran/rekomendasi.
    """

    # Ambil API KEY dari Database
    config = AIConfig.objects.filter(tipe='kmeans').first()
    if not config or not config.api_key:
        return JsonResponse({"success": False, "message": "API Key belum dikonfigurasi di menu Data."}, status=400)

    api_key = config.api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, timeout=30)
        res_json = response.json()
        
        raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
        # Pembersihan jika ada markdown
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()
        analysis_data = json.loads(clean_text)

        # Simpan di session untuk persistensi
        request.session['ai_dashboard_analysis'] = analysis_data
        request.session.modified = True

        return JsonResponse({"success": True, "analysis": analysis_data})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

@login_required(login_url='login')
def save_ai_config(request):
    if request.method == "POST":
        tipe = request.POST.get('tipe', 'kmeans')
        api_key = request.POST.get('api_key')
        
        config, created = AIConfig.objects.get_or_create(tipe=tipe)
        config.api_key = api_key
        config.save()
        
        return JsonResponse({"success": True, "message": "API Key berhasil disimpan"})
    
    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


# ==========================================
# K-MEANS DATA MANAGEMENT
# ==========================================

from django.core.paginator import Paginator

def normalize_jam(jam_str):
    if not jam_str:
        return "00:00"
    jam_str = str(jam_str).strip().replace('.', ':')
    if ':' in jam_str:
        parts = jam_str.split(':')
        if len(parts) >= 2:
            h = parts[0].zfill(2)
            m = parts[1].ljust(2, '0')[:2]
            return f"{h}:{m}"
    if jam_str.isdigit():
        return f"{jam_str.zfill(2)}:00"
    return jam_str

@login_required(login_url='login')
def kmeans_data_list(request):
    all_data = KMeansData.objects.all()
    total_count = all_data.count()
    
    # Hitung duplikasi (data yang isinya persis sama di semua kolom utama)
    duplicate_groups = KMeansData.objects.values(
        'no_referensi', 'umur', 'tkp', 'penyebab', 'hari', 'tanggal', 'jam', 
        'jenis_kendaraan', 'tipe_kendaraan', 'kerugian_material'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    jumlah_duplikat = sum(group['count'] - 1 for group in duplicate_groups)

    # Ambil detail data duplikat untuk ditampilkan di modal
    duplicate_data_details = []
    for group in duplicate_groups:
        # Ambil satu contoh data untuk setiap grup duplikat
        example = KMeansData.objects.filter(
            no_referensi=group['no_referensi'],
            umur=group['umur'], tkp=group['tkp'], penyebab=group['penyebab'],
            hari=group['hari'], tanggal=group['tanggal'], jam=group['jam'],
            jenis_kendaraan=group['jenis_kendaraan'], tipe_kendaraan=group['tipe_kendaraan'],
            kerugian_material=group['kerugian_material']
        ).first()
        if example:
            duplicate_data_details.append({
                'example': example,
                'count': group['count']
            })

    data_list = all_data.order_by('-tanggal', '-jam')
    
    # Normalize jam for display (existing data might have 19:0)
    for d in data_list:
        d.jam = normalize_jam(d.jam)

    # Paginasi 20 item per halaman
    paginator = Paginator(data_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'data_list': page_obj,
        'total_data': total_count,
        'jumlah_duplikat': jumlah_duplikat,
        'duplicate_data_details': duplicate_data_details,
        'ai_config': AIConfig.objects.filter(tipe='kmeans').first(),
    }
    return render(request, 'coreapp/k-means/data_list.html', context)

@login_required(login_url='login')
def kmeans_data_tambah(request):
    if request.method == "POST":
        umur = request.POST.get('umur')
        tkp = request.POST.get('tkp')
        penyebab = request.POST.get('penyebab')
        tanggal_raw = request.POST.get('tanggal') # Format YYYY-MM-DD
        jam = request.POST.get('jam')
        jenis_kendaraan = request.POST.get('jenis_kendaraan')
        tipe_kendaraan = request.POST.get('tipe_kendaraan')
        kerugian_material = request.POST.get('kerugian_material')

        if kerugian_material:
            kerugian_material = kerugian_material.upper().replace('RP', '').replace('.', '').replace(',', '').replace(' ', '').strip()

        tanggal_obj = datetime.strptime(tanggal_raw, '%Y-%m-%d')
        hari_en = tanggal_obj.strftime('%A')
        hari_map = {
            'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
            'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
        }
        hari = hari_map.get(hari_en, hari_en)

        KMeansData.objects.create(
            umur=umur,
            tkp=str(tkp).strip(),
            penyebab=str(penyebab).strip(),
            hari=str(hari).strip(),
            tanggal=tanggal_raw,
            jam=normalize_jam(jam),
            jenis_kendaraan=str(jenis_kendaraan).strip(),
            tipe_kendaraan=str(tipe_kendaraan).strip(),
            kerugian_material=kerugian_material
        )
        messages.success(request, "Data berhasil ditambahkan.")
        return redirect('kmeans_data_list')

    # Dropdown data: Ambil unik, hilangkan yang kosong/null, urutkan
    def get_unique_choices(field):
        # Ambil dari DB
        raw_choices = KMeansData.objects.exclude(**{f"{field}__isnull": True}).exclude(**{f"{field}": ""}).values_list(field, flat=True).distinct()
        
        # Bersihkan whitespace dan pastikan unik di Python (case-insensitive check or normalization)
        cleaned = set()
        for c in raw_choices:
            if c:
                cleaned.add(str(c).strip())
        
        return sorted(list(cleaned))

    context = {
        'tkp_choices': get_unique_choices('tkp'),
        'penyebab_choices': get_unique_choices('penyebab'),
        'jenis_choices': get_unique_choices('jenis_kendaraan'),
        'tipe_choices': get_unique_choices('tipe_kendaraan'),
    }
    return render(request, 'coreapp/k-means/data_tambah.html', context)

def _parse_indo_date(date_str):
    """Helper to parse Indonesian date strings like '1 Januari 2024'"""
    if not date_str or pd.isna(date_str):
        return None
    
    if isinstance(date_str, (datetime, pd.Timestamp)):
        return date_str.date()
        
    date_str = str(date_str).strip()
    months_map = {
        'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
    }
    
    try:
        # Split '1 Januari 2024'
        parts = date_str.split()
        if len(parts) == 3:
            day = int(parts[0])
            month_str = parts[1].lower()
            year = int(parts[2])
            month = months_map.get(month_str)
            if month:
                return datetime(year, month, day).date()
    except:
        pass
    
    # Try common formats using pandas
    try:
        return pd.to_datetime(date_str).date()
    except:
        return None

@login_required(login_url='login')
def kmeans_data_import(request):
    if request.method == "POST":
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Silakan pilih file excel.")
            return redirect('kmeans_data_list')
        
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()
            
            # Mapping kolom
            col_map = {}
            for col in df.columns:
                low = col.lower().replace(' ', '_')
                if 'jam' in low:               col_map[col] = 'jam'
                elif 'hari' in low:            col_map[col] = 'hari'
                elif 'tanggal' in low:         col_map[col] = 'tanggal'
                elif 'no' == low:              col_map[col] = 'no'
                elif 'umur' in low or 'usia' in low: col_map[col] = 'umur'
                elif 'tkp' in low or 'lokasi' in low: col_map[col] = 'tkp'
                elif 'penyebab' in low:        col_map[col] = 'penyebab'
                elif 'jenis_kendaraan' in low or 'jenis kendaraan' == col.lower(): col_map[col] = 'jenis_kendaraan'
                elif 'tipe_kendaraan' in low or 'tipe kendaraan' == col.lower():  col_map[col] = 'tipe_kendaraan'
                elif 'kerugian' in low:        col_map[col] = 'kerugian_material'
            
            df = df.rename(columns=col_map)
            
            count = 0
            hari_map_indo = {
                'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
                'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
            }

            for _, row in df.iterrows():
                try:
                    # Clean kerugian
                    kerugian = str(row.get('kerugian_material', 0))
                    kerugian = kerugian.upper().replace('RP', '').replace('.', '').replace(',', '').replace(' ', '').strip()
                    if kerugian == 'NAN' or not kerugian or kerugian == '-': kerugian = 0

                    # Handle tanggal
                    tgl = _parse_indo_date(row.get('tanggal'))
                    if not tgl:
                        continue # Skip invalid date rows
                    
                    # Ensure hari is correct
                    hari = row.get('hari')
                    if pd.isna(hari) or not hari:
                        hari_en = tgl.strftime('%A')
                        hari = hari_map_indo.get(hari_en, hari_en)
                    
                    # Ensure jam format
                    jam = str(row.get('jam', '')).replace('.', ':') # normalize 19.00 to 19:00 if needed, but the user example shows 19.00
                    if jam == 'nan': jam = "00:00"
                    
                    KMeansData.objects.create(
                        umur=row.get('umur', 0),
                        tkp=str(row.get('tkp', '')).strip(),
                        penyebab=str(row.get('penyebab', '')).strip(),
                        hari=str(hari).strip(),
                        tanggal=tgl,
                        jam=normalize_jam(row.get('jam', '')),
                        jenis_kendaraan=str(row.get('jenis_kendaraan', '')).strip(),
                        tipe_kendaraan=str(row.get('tipe_kendaraan', '')).strip(),
                        kerugian_material=kerugian
                    )
                    count += 1
                except Exception as e:
                    import traceback
                    print(f"Error importing row: {e}")
                    traceback.print_exc()
            
            messages.success(request, f"Berhasil mengimport {count} data.")
        except Exception as e:
            messages.error(request, f"Gagal mengimport data: {str(e)}")
            
        return redirect('kmeans_data_list')
    
    return redirect('kmeans_data_list')

@login_required(login_url='login')
def kmeans_data_hapus(request, pk):
    KMeansData.objects.filter(pk=pk).delete()
    messages.success(request, "Data berhasil dihapus.")
    return redirect('kmeans_data_list')

@login_required(login_url='login')
def kmeans_data_hapus_semua(request):
    KMeansData.objects.all().delete()
    messages.success(request, "Semua data berhasil dihapus.")
    return redirect('kmeans_data_list')

@login_required(login_url='login')
def kmeans_data_hapus_duplikat(request):
    if request.method == "POST":
        duplicate_groups = KMeansData.objects.values(
            'no_referensi', 'umur', 'tkp', 'penyebab', 'hari', 'tanggal', 'jam', 
            'jenis_kendaraan', 'tipe_kendaraan', 'kerugian_material'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        deleted_count = 0
        for group in duplicate_groups:
            ids = list(KMeansData.objects.filter(
                no_referensi=group['no_referensi'],
                umur=group['umur'], tkp=group['tkp'], penyebab=group['penyebab'],
                hari=group['hari'], tanggal=group['tanggal'], jam=group['jam'],
                jenis_kendaraan=group['jenis_kendaraan'], tipe_kendaraan=group['tipe_kendaraan'],
                kerugian_material=group['kerugian_material']
            ).values_list('id', flat=True))
            
            # Keep one, delete the rest
            ids_to_delete = ids[1:]
            KMeansData.objects.filter(id__in=ids_to_delete).delete()
            deleted_count += len(ids_to_delete)
            
        messages.success(request, f"Berhasil menghapus {deleted_count} data duplikat.")
        return redirect('kmeans_data_list')
    return redirect('kmeans_data_list')

# ==========================================
# END K-MEANS SECTION
# ==========================================

# View Tambah Data Kecelakaan
# =========================
@login_required(login_url='login')
def tambah_data(request):
    if request.method == "POST":
        # ambil data dari form
        tanggal = request.POST.get('tanggal')
        waktu = request.POST.get('waktu')
        meninggal = request.POST.get('meninggal') or 0
        luka_berat = request.POST.get('luka_berat') or 0
        luka_ringan = request.POST.get('luka_ringan') or 0
        kerugian = request.POST.get('kerugian') or 0
        kota = request.POST.get('kota')
        kecamatan = request.POST.get('kecamatan')
        kelurahan = request.POST.get('kelurahan')

        # simpan ke database
        Kecelakaan.objects.create(
            tanggal=tanggal,
            waktu=waktu,
            meninggal=meninggal,
            luka_berat=luka_berat,
            luka_ringan=luka_ringan,
            kerugian=kerugian,
            kota=kota,
            kecamatan=kecamatan,
            kelurahan=kelurahan
        )

        return redirect('data_cluster')  # kembali ke dashboard

    # Jika GET request → tampilkan halaman form
    return render(request, 'coreapp/k-means/tambah_data.html')

def tambah_data_view(request):
    kota_list = Kota.objects.all()  # ambil semua kota
    return render(request, 'coreapp/k-means/tambah_data.html', {
        'kota_list': kota_list
    })

def load_kecamatan(request):
    kota_id = request.GET.get('kota_id')
    kecamatan = list(Kecamatan.objects.filter(kota_id=kota_id).values('id', 'nama'))
    return JsonResponse({'kecamatan': kecamatan})

def load_kelurahan(request):
    kecamatan_id = request.GET.get('kecamatan_id')
    kelurahan = list(Kelurahan.objects.filter(kecamatan_id=kecamatan_id).values('id', 'nama'))
    return JsonResponse({'kelurahan': kelurahan})


# ================================
# PROSES AHC
# ================================

@login_required(login_url='login')
def proses_ahc(request):
    context = {}

    X_scaled = request.session.get('X_scaled')
    summary_df = request.session.get('summary_df')

    if not X_scaled or not summary_df:
        context['error'] = "Silakan lakukan preprocessing terlebih dahulu."
        return render(request, 'coreapp/ahc/proses.html', context)

    X_scaled = np.array(X_scaled)
    df = pd.DataFrame(summary_df)

    n_cluster = int(request.GET.get('cluster', 3))

    model = AgglomerativeClustering(
        n_clusters=n_cluster,
        linkage='ward'
    )

    labels = model.fit_predict(X_scaled)
    sil_score = silhouette_score(X_scaled, labels)
    sil_score = round(float(sil_score), 4)
    df['Cluster'] = labels

    total_data = len(df)
    summary = []

    faktor_cols = [
        "Faktor Pengemudi",
        "Faktor Jalan",
        "Faktor Kendaraan",
        "Faktor Lingkungan"
    ]

    waktu_cols = [
        "Dini Hari",
        "Pagi Hari",
        "Siang Hari",
        "Malam Hari"
    ]

    for cluster_id in sorted(df['Cluster'].unique()):
        cluster_data = df[df['Cluster'] == cluster_id]

        jumlah = len(cluster_data)
        persentase = round((jumlah / total_data) * 100, 2)
        rata_umur = round(cluster_data['Umur'].mean(), 1)

        faktor_dominan = cluster_data[faktor_cols].sum().idxmax()
        waktu_dominan = cluster_data[waktu_cols].sum().idxmax()

        summary.append({
            "cluster": int(cluster_id),
            "jumlah": jumlah,
            "persentase": persentase,
            "rata_umur": rata_umur,
            "faktor_dominan": faktor_dominan,
            "waktu_dominan": waktu_dominan,
        })

    # Simpan untuk halaman hasil
    request.session['hasil_cluster'] = df.to_dict(orient="records")
    request.session['summary_cluster'] = summary
    request.session['jumlah_cluster'] = n_cluster
    request.session['jumlah_data'] = total_data
    request.session['silhouette_score'] = sil_score

    # 🔥 Kirim ulang preview preprocessing agar tidak hilang
    context['preview'] = summary_df
    context['jumlah_data'] = len(summary_df)
    context['jumlah_data_asli'] = request.session.get('jumlah_data_asli')

    # 🔥 Tambahkan hasil clustering
    context['hasil_cluster'] = df.to_dict(orient="records")
    context['summary_cluster'] = summary
    context['jumlah_cluster'] = n_cluster

    return render(request, 'coreapp/ahc/proses.html', context)


# ================================
# HALAMAN HASIL
# ================================

@login_required(login_url='login')
def ahc_hasil(request):
    hasil_cluster = request.session.get('hasil_cluster', [])
    summary_cluster = request.session.get('summary_cluster', [])
    jumlah_cluster = request.session.get('jumlah_cluster')
    jumlah_data = request.session.get('jumlah_data')
    silhouette = request.session.get('silhouette_score')

    # Jika belum ada data cluster
    belum_clustering = len(hasil_cluster) == 0

    context = {
        "hasil_cluster": hasil_cluster,
        "summary_cluster": summary_cluster,
        "jumlah_cluster": jumlah_cluster,
        "jumlah_data": jumlah_data,
        "silhouette_score": silhouette,
        "belum_clustering": belum_clustering,
    }

    return render(request, 'coreapp/ahc/hasil.html', context)


@login_required(login_url='login')
def reset_ahc(request):
    keys_to_clear = [
        'hasil_cluster',
        'summary_cluster',
        'jumlah_cluster',
        'jumlah_data',
        'silhouette_score',
        'X_scaled',
        'summary_df',
        'uploaded_file_name',
        'jumlah_data_asli'
    ]

    for key in keys_to_clear:
        request.session.pop(key, None)

    return redirect('ahc_proses')