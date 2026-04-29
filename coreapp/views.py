from urllib import request
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
from .models import Kecelakaan
from .models import Kota, Kecamatan, Kelurahan
from rest_framework import status
import json
import math
import numpy as np
import plotly.graph_objects as go

import requests
import os

from sklearn.decomposition import PCA
from scipy.cluster.hierarchy import dendrogram, linkage
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import base64
from io import BytesIO
from plotly.figure_factory import create_dendrogram
import plotly



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


# Cluster K-Means Views
@login_required(login_url='login')
def cluster_data(request):
    data = Kecelakaan.objects.all()[:50]

    context = {
        'kecelakaan': data
    }

    return render(request, 'coreapp/k-means/data_cluster.html', context)


# ================================
# PREPROCESSING DATA KMEANS
# ================================
@login_required(login_url='login')
def preprocessing(request):

    context = {}
    df = None
    hasil_cluster = None

    # =========================
    # 1️⃣ PROSES UPLOAD (POST)
    # =========================
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
        if file:
            df = pd.read_excel(file)

            df.replace('-', np.nan, inplace=True)

            numeric_cols = ['Umur', 'Jumlah Kejadian']
            numeric_cols = [c for c in numeric_cols if c in df.columns]

            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Handle 'Jumlah Kejadian' - if column doesn't exist, create it with default value 1
            if 'Jumlah Kejadian' in df.columns:
                df['Jumlah Kejadian'] = df['Jumlah Kejadian'].fillna(1)
            else:
                df['Jumlah Kejadian'] = 1

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

            # 5️⃣ Dummy kendaraan (PERBAIKAN)
            kendaraan_cols = ['Motor', 'Mobil', 'Truk/Bus']

            for k in kendaraan_cols:
                df[k] = 0

            if 'Jenis Kendaraan' in df.columns:
                jenis = df['Jenis Kendaraan'].astype(str).str.lower()

                df.loc[jenis.str.contains('motor', na=False), 'Motor'] = df['Jumlah Kejadian']
                df.loc[jenis.str.contains('mobil', na=False), 'Mobil'] = df['Jumlah Kejadian']
                df.loc[jenis.str.contains('truk|bus', na=False), 'Truk/Bus'] = df['Jumlah Kejadian']

        # reset
        df['Faktor Pengemudi'] = 0
        df['Faktor Jalan'] = 0
        df['Faktor Kendaraan'] = 0
        df['Faktor Lingkungan'] = 0

        for i, row in df.iterrows():
            penyebab = str(row['Penyebab_clean']).lower()

            # 🔥 JALAN (lebih spesifik)
            if any(k in penyebab for k in [
                'jalan', 'licin', 'berlubang', 'rusak',
                'lampu', 'penerangan', 'gelap', 'bergelombang'
            ]):
                df.at[i, 'Faktor Jalan'] = row['Jumlah Kejadian']

            # 🔥 KENDARAAN
            if any(k in penyebab for k in [
                'kendaraan', 'rem', 'ban bocor', 'mesin', 'tergelincir','oleng'
            ]):
                df.at[i, 'Faktor Kendaraan'] = row['Jumlah Kejadian']

            # 🔥 LINGKUNGAN
            if any(k in penyebab for k in [
                'cuaca', 'hujan', 'kabut'
            ]):
                df.at[i, 'Faktor Lingkungan'] = row['Jumlah Kejadian']

            # 🔥 PENGEMUDI (terakhir)
            if any(k in penyebab for k in [
                'pengemudi', 'konsentrasi', 'mengantuk', 'lalai',
                'melanggar', 'mendahului', 'jarak', 'menghindari','sein','mendadak',
                'melawan arus','laju','berkecepatan tinggi','jarak','jalur','berhenti',
    
            ]):
                df.at[i, 'Faktor Pengemudi'] = row['Jumlah Kejadian']

            # 7️⃣ Dummy waktu
            waktu_cols = ['Dini Hari', 'Pagi Hari', 'Siang Hari', 'Malam Hari']
            for w in waktu_cols:
                df[w] = (df['Waktu Kejadian'] == w).astype(int) * df['Jumlah Kejadian']

            # 8️⃣ Group by umur dengan semua fitur
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

            # Simpan ke session
            request.session['summary_df'] = summary_df.to_dict(orient='records')
            request.session.modified = True

            context['preview'] = summary_df.to_dict(orient='records')

    # =========================
    # 2️⃣ AMBIL DATA DARI SESSION
    # =========================
    summary_json = request.session.get('summary_df')

    if summary_json:
        # Handle both JSON string and list formats
        if isinstance(summary_json, list):
            df = pd.DataFrame(summary_json)
        else:
            try:
                df = pd.read_json(StringIO(summary_json), orient='records')
            except Exception:
                df = pd.DataFrame(summary_json)
        context['preview'] = df.to_dict(orient='records')

    # 💾 LOAD HASIL CLUSTER DARI SESSION (JIKA ADA)
    hasil_cluster_session = request.session.get('hasil_cluster')
    k_session = request.session.get('k')
    
    if hasil_cluster_session and k_session:
        context['hasil_cluster'] = hasil_cluster_session
        context['k'] = k_session

    # =========================
    # 3️⃣ PROSES CLUSTERING (GET ?k=)
    # =========================
    if df is not None and 'k' in request.GET:

        try:
            k = int(request.GET.get('k', 3))
        except ValueError:
            k = 3

        k = max(1, min(k, 3))

        X = df.select_dtypes(include=['number'])

        if not X.empty and len(X) >= k:

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = KMeans(n_clusters=k, random_state=42, n_init=10)
            model.fit(X_scaled)

            df_cluster = df.copy()
            df_cluster['Cluster'] = model.labels_ + 1  # Cluster mulai dari 1, 2, 3

            hasil_cluster = df_cluster.to_dict(orient='records')
            
            # 💾 SIMPAN KE SESSION UNTUK HALAMAN HASIL
            request.session['hasil_cluster'] = hasil_cluster
            request.session['k'] = k
            request.session.modified = True
            
            context['hasil_cluster'] = hasil_cluster
            context['k'] = k

    return render(request, 'coreapp/k-means/preprocessing.html', context)


@login_required(login_url='login')
def reset_k_means(request):
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

    return redirect('preprocessing')


# ===============================
# KMEANS VIEWS
# ===============================

@login_required(login_url='login')
def kmeans_data(request):
    return render(request, 'coreapp/kmeans/data.html')


@login_required(login_url='login')
def kmeans_proses(request):
    return render(request, 'coreapp/kmeans/proses.html')


@login_required(login_url='login')
def kmeans_hasil(request):
    return render(request, 'coreapp/kmeans/hasil.html')


# ==========================================
# PROSES K-MEANS CLUSTERING
# ==========================================
@login_required(login_url='login')
def proses_cluster(request):

    if request.method != "GET":
        return redirect('preprocessing')

    # Ambil nilai k
    try:
        k = int(request.GET.get('k', 3))
    except ValueError:
        k = 3

    k = max(1, min(k, 3))

    # Ambil data summary dari session
    summary_json = request.session.get('summary_df')

    if not summary_json:
        print("Session summary_df kosong")
        return redirect('preprocessing')

    # Load dataframe - handle both JSON string and list formats
    if isinstance(summary_json, list):
        df = pd.DataFrame(summary_json)
    else:
        try:
            df = pd.read_json(StringIO(summary_json), orient='records')
        except Exception:
            df = pd.DataFrame(summary_json)

    if df.empty:
        print("DataFrame kosong")
        return redirect('preprocessing')

    # Ambil hanya kolom numerik (kecuali Umur)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

    if 'Umur' in numeric_cols:
        numeric_cols.remove('Umur')

    if not numeric_cols:
        print("Tidak ada fitur numerik untuk clustering")
        return redirect('preprocessing')

    X = df[numeric_cols]

    # Jika jumlah data < k
    if len(X) < k:
        k = len(X)

    try:
        # Scaling
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # KMeans
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        df['Cluster'] = model.fit_predict(X_scaled) + 1  # Cluster mulai dari 1, 2, 3

        # Mapping label cluster biar lebih jelas
        label_map = {
            0: 'Cluster 1 (Rendah)',
            1: 'Cluster 2 (Sedang)',
            2: 'Cluster 3 (Tinggi)'
        }

        df['Cluster_Label'] = df['Cluster'].map(label_map)

    except Exception as e:
        print("ERROR SAAT CLUSTERING:", e)
        return redirect('preprocessing')

    # ========================
    # Interpretasi Cluster
    # ========================

    cluster_summary = df.groupby('Cluster')[numeric_cols].mean().mean(axis=1)
    sorted_cluster = cluster_summary.sort_values()

    kategori = ['Rendah', 'Sedang', 'Tinggi']
    label_map = {}

    for i, cluster_id in enumerate(sorted_cluster.index):
        if i < len(kategori):
            label_map[cluster_id] = kategori[i]
        else:
            label_map[cluster_id] = f"Cluster {cluster_id}"

    df['Kategori_Cluster'] = df['Cluster'].map(label_map)

    # SIMPAN HASIL CLUSTER KE SESSION (INI KUNCI)
    request.session['hasil_cluster'] = df.to_dict(orient='records')
    request.session['k'] = k
    request.session.modified = True

    return render(request, 'coreapp/k-means/preprocessing.html', {
        'hasil_cluster': df.to_dict(orient='records'),
        'k': k
    })


@login_required(login_url='login')
def hasil(request):

    data = request.session.get("hasil_cluster")

    if not data:
        return redirect("preprocessing")

    # data sudah HASIL CLUSTER, bukan summary
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        try:
            df = pd.read_json(StringIO(data), orient='records')
        except Exception:
            df = pd.DataFrame(data)

    context = {
        "hasil_cluster": df.to_dict(orient='records'),
        "k": request.session.get("k")
    }

    return render(request, "coreapp/k-means/hasil.html", context)

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
# PREPROCESSING DATA AHC
# ================================

@login_required(login_url='login')
def preprocessing_data(request):
    context = {}

    if request.method == "POST":
        file = request.FILES.get('file')

        if file:
            # Reset session
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

            # Simpan nama file aktif
            request.session['uploaded_file_name'] = file.name

            # ================================
            # 1. BACA DATA
            # ================================
            df = pd.read_excel(file)

            context['preview_asli'] = df.head().to_html( 
                classes="table-auto w-full text-sm", 
                index=False
            )

            # Simpan jumlah data asli
            request.session['jumlah_data_asli'] = len(df)

            # Handle missing value
            df.replace('-', np.nan, inplace=True)

            numeric_cols = ['Umur', 'Jumlah Kejadian']
            numeric_cols = [c for c in numeric_cols if c in
    df.columns]
            
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            if 'Jumlah Kejadian' in df.columns:
                df['Jumlah Kejadian'] = df['Jumlah Kejadian'].fillna(1)
            else:
                df['Jumlah Kejadian'] = 1  

            # ================================
            # 2. NUMERIC
            # ================================
            df['Umur'] = pd.to_numeric(df['Umur'], errors='coerce')
            df['Jumlah Kejadian'] = pd.to_numeric(df['Jumlah Kejadian'], errors='coerce').fillna(1)

            df = df[df['Umur'] > 0]

            # ================================
            # 3. WAKTU
            # ================================
            def konversi_waktu(jam):
                try:
                    jam = str(jam).strip()

                    # ubah 19.00 → 19:00
                    jam = jam.replace('.', ':')

                    # ambil jam saja
                    jam = int(jam.split(':')[0])

                except:
                    return "Tidak Diketahui"

                if 0 <= jam < 6:
                    return "Dini Hari"
                elif 6 <= jam < 12:
                    return "Pagi Hari"
                elif 12 <= jam < 18:
                    return "Siang Hari"
                else:
                    return "Malam Hari"

            df.columns = df.columns.str.strip()

            if 'Jam' in df.columns:
                df['Waktu Kejadian'] = df['Jam'].apply(konversi_waktu)
            else:
                df['Waktu Kejadian'] = 'Tidak Diketahui'


            # ================================
            # 4. KENDARAAN
            # ================================
            kendaraan_cols = ['Motor', 'Mobil', 'Truk/Bus']
            df[kendaraan_cols] = 0

            jenis = df['Jenis Kendaraan'].astype(str).str.lower()

            df.loc[jenis.str.contains('motor'), 'Motor'] = df['Jumlah Kejadian']
            df.loc[jenis.str.contains(r'mobil|pick\s*up|pickup', na=False), 'Mobil'] = df['Jumlah Kejadian']
            df.loc[jenis.str.contains('truk|bus'), 'Truk/Bus'] = df['Jumlah Kejadian']

            # ================================
            # FAKTOR PENYEBAB
            # ================================
            df['Penyebab_clean'] = df['Penyebab'].astype(str).str.lower().str.strip()

            df['Faktor Pengemudi'] = 0
            df['Faktor Jalan'] = 0
            df['Faktor Kendaraan'] = 0
            df['Faktor Lingkungan'] = 0

            for i, row in df.iterrows():
                penyebab = row['Penyebab_clean']
                jumlah = row['Jumlah Kejadian']

                # JALAN
                if any(k in penyebab for k in ['licin', 'jalan berlubang', 'penerangan','genangan air']):
                    df.at[i, 'Faktor Jalan'] += jumlah

                # KENDARAAN
                if any(k in penyebab for k in ['kendaraan ban bocor', 'kendaraan oleng','tergelincir','lampu depan mati','roda bermasalah','batu']):
                    df.at[i, 'Faktor Kendaraan'] += jumlah

                # LINGKUNGAN
                if any(k in penyebab for k in ['cuaca hujan','kabut','pohon tumbang']):
                    df.at[i, 'Faktor Lingkungan'] += jumlah

                # PENGEMUDI 
                if any(k in penyebab for k in [
                    'kurang konsentrasi',
                    'konsentrasi',
                    'lalai',
                    'mengantuk',
                    'mendahului sebelah kiri',
                    'berkecepatan tinggi',
                    'membuka pintu mendadak'
                    'melanggar Apill',
                    'melebihi marka',
                    'tidak mengutamakan jalur utama',
                    'mengerem mendadak',
                    'tidak menyalakan lampu sein',
                    'melawan arus',
                    'berkecepatan tinggi',
                    'berkendara menggunakan hp',
                    'tidak menguasai laju',
                    'tidak menjaga jarak aman',
                    'pengaruh alkohol'
                    'gerobak lepas dari sepeda motor'
                ]):
                    df.at[i, 'Faktor Pengemudi'] += jumlah

                # fallback
                if (
                    df.at[i, 'Faktor Pengemudi'] == 0 and
                    df.at[i, 'Faktor Jalan'] == 0 and
                    df.at[i, 'Faktor Kendaraan'] == 0 and
                    df.at[i, 'Faktor Lingkungan'] == 0
                ):
                    df.at[i, 'Faktor Pengemudi'] = jumlah

            # ================================
            # 6. WAKTU
            # ================================
            waktu_cols = ['Dini Hari', 'Pagi Hari', 'Siang Hari', 'Malam Hari']
            for w in waktu_cols:
                df[w] = (df['Waktu Kejadian'] == w).astype(int) * df['Jumlah Kejadian']

            # ================================
            # 7. GROUP BY UMUR
            # ================================
            summary_cols = (
                ['Jumlah Kejadian'] +
                kendaraan_cols +
                ['Faktor Pengemudi','Faktor Jalan','Faktor Kendaraan','Faktor Lingkungan'] +
                waktu_cols
            )

            summary_df = df.groupby('Umur')[summary_cols].sum().reset_index()
            summary_df = summary_df.round().astype(int)

            # ================================
            # 8. SCALING
            # ================================
            fitur_clustering = summary_df.copy()
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(fitur_clustering)

            # ================================
            # 9. SIMPAN SESSION
            # ================================
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


    # ================================
    # FUNGSI UNTUK MENENTUKAN K TERBAIK (SILHOUETTE SCORE)
    # ================================
def find_best_cluster(X, max_k=5):
    best_k = 2
    best_score = -1

    for k in range(2, max_k + 1):
        model = AgglomerativeClustering(n_clusters=k, linkage='ward')
        labels = model.fit_predict(X)

        score = silhouette_score(X, labels)

        if score > best_score:
            best_score = score
            best_k = k

    return best_k

    # ================================
    # PROSES AHC
    # ================================
@login_required(login_url='login')
def proses_ahc(request):

    import io, base64
    import matplotlib.pyplot as plt
    import plotly.express as px

    from sklearn.decomposition import PCA
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    from scipy.cluster.hierarchy import linkage
    from plotly.figure_factory import create_dendrogram

    # ================================
    # 1. AMBIL DATA
    # ================================
    X_scaled = request.session.get('X_scaled')
    summary_df = request.session.get('summary_df')

    if not X_scaled or not summary_df:
        return render(request, 'coreapp/ahc/proses.html', {
            "error": "Silakan lakukan preprocessing terlebih dahulu."
        })

    X_scaled = np.array(X_scaled)
    df = pd.DataFrame(summary_df)

    df['Jumlah Kejadian'] = pd.to_numeric(df['Jumlah Kejadian'], errors='coerce').fillna(0)
    df['Umur'] = pd.to_numeric(df['Umur'], errors='coerce').fillna(0)

    # ================================
    # PILIH CLUSTER
    # ================================
    
    # AUTO (berdasarkan data)
    n_cluster = find_best_cluster(X_scaled, max_k=3)

    # MANUAL (ditentukan sendiri)
    #n_cluster = 3

    # ================================
    # MODEL AHC
    # ================================

    model = AgglomerativeClustering(n_clusters=n_cluster, linkage='ward')
    labels = model.fit_predict(X_scaled)

    # HITUNG SILHOUETTE (SETELAH ADA LABELS)
    sil_score = round(float(silhouette_score(X_scaled, labels)), 4)

    # ================================
    # PCA VISUAL
    # ================================

    from sklearn.decomposition import PCA
    import plotly.express as px

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)

    df_pca = df.copy()
    df_pca['PC1'] = X_pca[:, 0]
    df_pca['PC2'] = X_pca[:, 1]
    df_pca['Cluster'] = labels + 1

    fig_scatter = px.scatter(
        df_pca,
        x='PC1',
        y='PC2',
        color=df_pca['Cluster'].astype(str),
        title='Visualisasi Cluster (PCA)',
    )

    scatter_html = fig_scatter.to_html(full_html=False)

    df['Cluster'] = labels + 1
    cluster_counts = df['Cluster'].value_counts().sort_index()
    sil_score = round(float(silhouette_score(X_scaled, labels)), 4)

    # ================================
    # 3. BAR CHART
    # ================================
    bar_df = pd.DataFrame({
        "Cluster": [f"Cluster {i}" for i in cluster_counts.index],
        "Jumlah": cluster_counts.values
    })

    fig_bar = px.bar(
        bar_df,
        x="Cluster",
        y="Jumlah",
        text="Jumlah",
        title="Jumlah Data pada Setiap Cluster"
    )

    # interaksi hover & click
    fig_bar.update_traces(
        hovertemplate="Cluster: %{x}<br>Jumlah: %{y}<extra></extra>",
        customdata=cluster_counts.index
    )

    bar_chart = fig_bar.to_html(full_html=False)
    request.session['bar_chart'] = bar_chart

    # ================================
    # 3B. FAKTOR PENYEBAB (GLOBAL)
    # ================================

    faktor_cols = ["Faktor Pengemudi", "Faktor Jalan", "Faktor Kendaraan", "Faktor Lingkungan"]

    # ambil dari hasil_cluster
    df_all = df.copy()

    faktor_total = {}

    for col in faktor_cols:
        if col in df_all.columns:
            faktor_total[col] = int(df_all[col].sum())

        faktor_labels = list(faktor_total.keys())
        faktor_values = list(faktor_total.values())


    # # ================================
    # # GROUPED DATA (UMUR vs FAKTOR)
    # # ================================
    # faktor_cols = ["Faktor Pengemudi", "Faktor Jalan", "Faktor Kendaraan", "Faktor Lingkungan"]

    # grouped = df_all.groupby('Kelompok Umur')[faktor_cols].sum().reset_index()

    # umur_labels = grouped['Kelompok Umur'].tolist()

    # faktor_pengemudi = grouped['Faktor Pengemudi'].tolist() if 'Faktor Pengemudi' in grouped else []
    # faktor_jalan = grouped['Faktor Jalan'].tolist() if 'Faktor Jalan' in grouped else []
    # faktor_kendaraan = grouped['Faktor Kendaraan'].tolist() if 'Faktor Kendaraan' in grouped else []
    # faktor_lingkungan = grouped['Faktor Lingkungan'].tolist() if 'Faktor Lingkungan' in grouped else []

    # ================================
    # 4. DENDROGRAM (MATPLOTLIB FIX)
    # ================================

    import plotly.graph_objects as go
    from plotly.figure_factory import create_dendrogram

    Z = linkage(X_scaled, method='ward')

    max_d = Z[:, 2].max()
    threshold = 0.6 * max_d

    fig = create_dendrogram(
        X_scaled,
        linkagefun=lambda x: Z,
        color_threshold=threshold
    )

    # ambil range X
    x_min = min([min(t['x']) for t in fig['data'] if 'x' in t])
    x_max = max([max(t['x']) for t in fig['data'] if 'x' in t])

    # garis merah
    fig.add_trace(
        go.Scatter(
            x=[x_min, x_max],
            y=[threshold, threshold],
            mode='lines',
            line=dict(color='red', width=5, dash='dash'),
            name='Cut-off'
        )
    )

    fig.update_layout(
        title="Dendrogram Hierarchical Clustering",
        width=900,
        height=500
    )

    dendrogram_html = fig.to_html(full_html=False)
    

    # ================================
    # 6. SUMMARY CLUSTER
    # ================================
    summary = []
    total_kejadian_all = int(df['Jumlah Kejadian'].sum())

    faktor_cols = ["Faktor Pengemudi", "Faktor Jalan", "Faktor Kendaraan", "Faktor Lingkungan"]
    waktu_cols = ["Dini Hari", "Pagi Hari", "Siang Hari", "Malam Hari"]

    for cluster_id in sorted(df['Cluster'].unique()):
        cluster_data = df[df['Cluster'] == cluster_id]

        jumlah = int(cluster_data['Jumlah Kejadian'].sum())
        persentase = round((jumlah / total_kejadian_all) * 100, 2)

        umur_min = int(cluster_data['Umur'].min())
        umur_max = int(cluster_data['Umur'].max())

        if "Penyebab_clean" in cluster_data.columns:
            faktor_dominan = cluster_data["Penyebab_clean"].mode()[0]
        else:
            faktor_exist = [c for c in faktor_cols if c in cluster_data.columns]
            faktor_dominan = cluster_data[faktor_exist].sum().idxmax() if faktor_exist else "-"

        waktu_exist = [c for c in waktu_cols if c in cluster_data.columns]
        waktu_dominan = cluster_data[waktu_exist].sum().idxmax() if waktu_exist else "-"

        summary.append({
            "cluster": int(cluster_id),
            "jumlah": jumlah,
            "persentase": persentase,
            "rata_umur": f"{umur_min}-{umur_max}",
            "faktor_dominan": faktor_dominan,
            "waktu_dominan": waktu_dominan,
        })

    # ================================
    # 7. SESSION SAVE
    # ================================
    request.session['hasil_cluster'] = df.to_dict('records')
    request.session['summary_cluster'] = summary
    request.session['jumlah_cluster'] = n_cluster
    request.session['jumlah_data'] = len(df)
    request.session['silhouette_score'] = sil_score
    request.session['total_kejadian'] = total_kejadian_all
    request.session['dendrogram_html'] = dendrogram_html
    request.session['scatter_html'] = scatter_html
    request.session['bar_chart'] = bar_chart

    return redirect('ahc_hasil')


    # ================================
    # HASIL AHC
    # ================================
@login_required(login_url='login')
def ahc_hasil(request):

    hasil_cluster = request.session.get('hasil_cluster', [])
    df = pd.DataFrame(hasil_cluster)
    summary_cluster = request.session.get('summary_cluster', [])
    jumlah_cluster = request.session.get('jumlah_cluster')
    jumlah_data = request.session.get('jumlah_data')
    silhouette = request.session.get('silhouette_score')
    scatter_html = request.session.get('scatter_html')
    dendrogram_html = request.session.get('dendrogram_html')
    bar_chart = request.session.get('bar_chart')
    faktor_chart = request.session.get('faktor_chart')

    belum_clustering = len(hasil_cluster) == 0

    # ================================
    # AI INTELLIGENT ANALYSIS (GLOBAL)
    # ================================
    ai_global = generate_ai_insight(summary_cluster, silhouette)

    # ================================
    # CHART DATA
    # ================================
    cluster_labels = [
        f"Cluster {s['cluster']}" for s in summary_cluster
    ]
    cluster_counts = [
        s['jumlah'] for s in summary_cluster
    ]

    # ================================
    # DETAIL CLUSTER
    # ================================
    cluster_detail = {}

    for s in summary_cluster:
        cid = s['cluster']
        data_cluster = [r for r in hasil_cluster if r['Cluster'] == cid]

        cluster_detail[f"Cluster {cid}"] = [
            f"Umur: {d.get('Umur','-')}, Jumlah: {d.get('Jumlah Kejadian',0)}"
            for d in data_cluster
        ]

    # ================================
    # TOTAL KEJADIAN
    # ================================
    total_kejadian = sum(
        r.get('Jumlah Kejadian', 0) for r in hasil_cluster
    )

    # ================================
    # FAKTOR PENYEBAB (GLOBAL)
    # ================================

    faktor_cols = ["Faktor Pengemudi", "Faktor Jalan", "Faktor Kendaraan", "Faktor Lingkungan"]

    df_all = df.copy()

    faktor_total = {}

    for col in faktor_cols:
        if col in df_all.columns:
            faktor_total[col] = int(df_all[col].sum())

    # INI WAJIB ADA
    faktor_labels = list(faktor_total.keys())
    faktor_values = list(faktor_total.values())

    print("FAKTOR LABEL:", faktor_labels)

    # ================================
    # FIX ERROR umur_labels
    # ================================
    try:
        df_all = df.copy()

        def kategori_umur(u):
            try:
                u = int(u)
            except:
                return "Tidak Diketahui"

            if u <= 11:
                return "5-11 (Kanak-kanak)"
            elif u <= 16:
                return "12-16 (Remaja Awal)"
            elif u <= 25:
                return "17-25 (Remaja Akhir)"
            elif u <= 35:
                return "26-35 (Dewasa Awal)"
            elif u <= 45:
                return "36-45 (Dewasa Akhir)"
            elif u <= 55:
                return "46-55 (Lansia Awal)"
            elif u <= 65:
                return "56-65 (Lansia Akhir)"
            else:
                return "66-90 (Manula)"

        if not df_all.empty and 'Umur' in df_all.columns:

            # 🔥 pastikan tidak ada null
            df_all['Umur'] = pd.to_numeric(df_all['Umur'], errors='coerce').fillna(0)

            # 🔥 buat kolom dulu
            df_all['Kelompok Umur'] = df_all['Umur'].apply(kategori_umur)

            # 🔥 CEK dulu sebelum groupby
            if 'Kelompok Umur' in df_all.columns:

                faktor_cols = [
                    "Faktor Pengemudi",
                    "Faktor Jalan",
                    "Faktor Kendaraan",
                    "Faktor Lingkungan"
                ]

                grouped = df_all.groupby('Kelompok Umur')[faktor_cols].sum().reset_index()

                umur_labels = grouped['Kelompok Umur'].tolist()
                faktor_pengemudi = grouped['Faktor Pengemudi'].tolist()
                faktor_jalan = grouped['Faktor Jalan'].tolist()
                faktor_kendaraan = grouped['Faktor Kendaraan'].tolist()
                faktor_lingkungan = grouped['Faktor Lingkungan'].tolist()

            else:
                umur_labels = []
                faktor_pengemudi = []
                faktor_jalan = []
                faktor_kendaraan = []
                faktor_lingkungan = []

        else:
            umur_labels = []
            faktor_pengemudi = []
            faktor_jalan = []
            faktor_kendaraan = []
            faktor_lingkungan = []

    except Exception as e:
        print("ERROR UMUR CHART:", e)
        umur_labels = []
        faktor_pengemudi = []
        faktor_jalan = []
        faktor_kendaraan = []
        faktor_lingkungan = []

    # ================================
    # AI PER VISUAL 
    # ================================

    # AI BAR CHART (ENHANCED)

    if summary_cluster:

        total = sum(s['jumlah'] for s in summary_cluster)

        terbesar = max(summary_cluster, key=lambda x: x['jumlah'])
        terkecil = min(summary_cluster, key=lambda x: x['jumlah'])

        ai_bar = "<b>ANALISIS DISTRIBUSI CLUSTER (BAR CHART)</b><br><br>"

        for s in sorted(summary_cluster, key=lambda x: x['cluster']):
            persentase = round((s['jumlah'] / total) * 100, 2)

            ai_bar += (
                f"• <b>Cluster {s['cluster']}</b>: "
                f"<b>{s['jumlah']}</b> kejadian "
                f"(<b>{persentase}%</b>) → "
            )

            if s['jumlah'] == terbesar['jumlah']:
                ai_bar += "<b style='color:#dc2626'>Dominan (tertinggi)</b><br>"
            elif s['jumlah'] == terkecil['jumlah']:
                ai_bar += "<b style='color:#2563eb'>Terendah</b><br>"
            else:
                ai_bar += "Kategori <b>Sedang</b><br>"

        # KESIMPULAN

        ai_bar += "<br><b>Kesimpulan:</b><br>"

        ai_bar += (
            f"Cluster <b style='color:#dc2626'>{terbesar['cluster']}</b> "
            f"merupakan cluster dengan jumlah kejadian tertinggi, "
            f"sedangkan cluster <b style='color:#2563eb'>{terkecil['cluster']}</b> "
            f"memiliki jumlah kejadian paling rendah. "
            f"Hal ini menunjukkan adanya perbedaan distribusi kejadian yang cukup signifikan antar cluster."
        )

    else:
        ai_bar = "Belum ada data untuk analisis bar chart."

    # ================================
    # AI PCA
    # ================================
    ai_pca = (
        "<b>ANALISIS VISUALISASI PCA (PRINCIPAL COMPONENT ANALYSIS)</b><br><br>"
        
        "Visualisasi PCA digunakan untuk mereduksi data ke dalam dua dimensi utama "
        "(<b>Principal Component 1</b> dan <b>Principal Component 2</b>) agar pola data lebih mudah dianalisis.<br><br>"
        "Setiap titik merepresentasikan satu data dalam cluster tertentu. "
        "Semakin jauh jarak antar cluster, maka perbedaan karakteristik semakin jelas sehingga hasil clustering dapat dianggap "
        "<b style='color:#16a34a'>baik</b>.<br><br>"
        "Sebaliknya, jika terjadi <i>overlap</i>, maka menunjukkan adanya kemiripan antar data sehingga pemisahan cluster belum optimal.<br><br>"
        
        "<b>Kesimpulan:</b> PCA membantu mengevaluasi kualitas clustering melalui visualisasi pemisahan antar cluster."
    )
    
    # ================================
    # AI DENDROGRAM (ENHANCED)
    # ================================
    ai_dendrogram = f"<b>ANALISIS DENDROGRAM HIERARCHICAL CLUSTERING</b>\n\n" \
    "Dendrogram menunjukkan proses pengelompokan data berdasarkan tingkat kemiripan antar data.\n\n" \
    "Pada awalnya, setiap data dianggap sebagai satu cluster, kemudian secara bertahap digabungkan dengan data lain yang memiliki kemiripan paling tinggi.\n\n" \
    "Garis <b style='color:#dc2626'>cut-off</b> digunakan sebagai batas untuk menentukan jumlah cluster yang terbentuk.\n" \
    f"Pada hasil ini, pemotongan dendrogram menghasilkan sebanyak <b style='color:#2563eb'>{jumlah_cluster} cluster</b>.\n\n" \
    "Semakin tinggi posisi cut-off, maka jumlah cluster semakin sedikit.\n" \
    "Sebaliknya, semakin rendah cut-off, maka jumlah cluster semakin banyak dan lebih detail.\n\n" \
    "<b>Kesimpulan:</b>\n" \
    f"Pembagian data ke dalam <b style='color:#2563eb'>{jumlah_cluster} cluster</b> sudah sesuai dengan pola kemiripan data, sehingga proses clustering dapat dianggap <b>optimal</b>."
    # ================================
    # AI FAKTOR PENYEBAB (GLOBAL)
    # ================================
    if faktor_values:
        max_index = faktor_values.index(max(faktor_values))
        faktor_tertinggi = faktor_labels[max_index]

        ai_faktor = "ANALISIS FAKTOR PENYEBAB KECELAKAAN\n\n"

        ai_faktor += "Distribusi faktor penyebab:\n"

        for i in range(len(faktor_labels)):
            ai_faktor += (
                f"- <b>{faktor_labels[i]}</b>: "
                f"<b>{faktor_values[i]}</b> kejadian\n"
            )

        ai_faktor += (
            "\nFaktor paling dominan adalah "
            f"<b style='color:#dc2626'>{faktor_tertinggi}</b>.\n"
        )

        if faktor_tertinggi == "Faktor Pengemudi":
            ai_faktor += (
                "Hal ini menunjukkan bahwa <b>kesalahan manusia</b> "
                "menjadi penyebab utama kecelakaan."
            )
        elif faktor_tertinggi == "Faktor Jalan":
            ai_faktor += (
                "Hal ini menunjukkan bahwa <b>kondisi jalan</b> "
                "menjadi faktor utama kecelakaan."
            )
        elif faktor_tertinggi == "Faktor Kendaraan":
            ai_faktor += (
                "Hal ini menunjukkan bahwa <b>kondisi kendaraan</b> "
                "memiliki kontribusi besar terhadap kecelakaan."
            )
        else:
            ai_faktor += (
                "Hal ini menunjukkan bahwa <b>faktor lingkungan</b> "
                "berpengaruh terhadap kecelakaan."
            )

        ai_faktor += (
            "\n\nKesimpulan:\n"
            f"Faktor <b style='color:#dc2626'>{faktor_tertinggi}</b> "
            "merupakan penyebab utama kecelakaan dan perlu menjadi fokus utama dalam upaya pencegahan."
        )

    else:
        ai_faktor = "Belum ada data faktor."

    # ================================
    # AI UMUR vs FAKTOR (ENHANCED)
    # ================================

    ai_umur = "Belum ada data umur."

    if umur_labels:

        total_per_umur = []

        for i in range(len(umur_labels)):
            total = (
                faktor_pengemudi[i] +
                faktor_jalan[i] +
                faktor_kendaraan[i] +
                faktor_lingkungan[i]
            )
            total_per_umur.append(total)

        max_index = total_per_umur.index(max(total_per_umur))
        umur_tertinggi = umur_labels[max_index]

        # 🔥 cari faktor dominan pada umur tertinggi
        idx = max_index
        faktor_list = [
            ("Faktor Pengemudi", faktor_pengemudi[idx]),
            ("Faktor Jalan", faktor_jalan[idx]),
            ("Faktor Kendaraan", faktor_kendaraan[idx]),
            ("Faktor Lingkungan", faktor_lingkungan[idx])
        ]
        faktor_dominan = max(faktor_list, key=lambda x: x[1])[0]

        # ================================
        # BUILD TEXT
        # ================================
        ai_umur = "<b>ANALISIS HUBUNGAN UMUR DAN FAKTOR KECELAKAAN</b>\n\n"

        ai_umur += (
            f"Kelompok umur dengan kejadian tertinggi adalah "
            f"<b style='color:#2563eb'>{umur_tertinggi}</b>.\n\n"
        )

        ai_umur += "Distribusi faktor pada setiap kelompok umur:\n"

        for i in range(len(umur_labels)):
            ai_umur += (
                f"\n• <b>Umur {umur_labels[i]}</b>\n"
                f"  - Pengemudi   : <b>{faktor_pengemudi[i]}</b>\n"
                f"  - Jalan       : <b>{faktor_jalan[i]}</b>\n"
                f"  - Kendaraan   : <b>{faktor_kendaraan[i]}</b>\n"
                f"  - Lingkungan  : <b>{faktor_lingkungan[i]}</b>\n"
            )

        # ================================
        # KESIMPULAN
        # ================================
        ai_umur += (
            "\nKesimpulan:\n"
            f"Kelompok umur <b style='color:#2563eb'>{umur_tertinggi}</b> "
            f"merupakan kelompok dengan tingkat kecelakaan tertinggi, "
            f"dengan faktor dominan yaitu "
            f"<b style='color:#dc2626'>{faktor_dominan}</b>.\n\n"
        )

        # ================================
        # REKOMENDASI (BONUS 🔥)
        # ================================
        ai_umur += (
            "Rekomendasi:\n"
            "Perlu dilakukan peningkatan edukasi keselamatan berkendara "
            "terutama pada kelompok umur dominan guna mengurangi risiko kecelakaan."
        )
                
    # ================================
    # CONTEXT
    # ================================
    context = {
        "hasil_cluster": hasil_cluster,
        "summary_cluster": summary_cluster,
        "jumlah_cluster": jumlah_cluster,
        "jumlah_data": jumlah_data,
        "total_kejadian": total_kejadian,
        "silhouette_score": silhouette,
        "belum_clustering": belum_clustering,
        "scatter_html": scatter_html,
        "dendrogram_html": dendrogram_html,
        "bar_chart": bar_chart,
        "faktor_chart": faktor_chart,
        "faktor_labels": faktor_labels,
        "faktor_values": faktor_values,
        "umur_labels": umur_labels,
        "faktor_pengemudi": faktor_pengemudi,
        "faktor_jalan": faktor_jalan,
        "faktor_kendaraan": faktor_kendaraan,
        "faktor_lingkungan": faktor_lingkungan,
        "ai_faktor": ai_faktor,
        "ai_umur": ai_umur,

        "cluster_labels": cluster_labels,
        "cluster_counts": cluster_counts,
        "cluster_detail": cluster_detail,

        # AI OUTPUT
        "ai_global": ai_global,
        "ai_bar": ai_bar,
        "ai_pca": ai_pca,
        "ai_dendrogram": ai_dendrogram,
    }

    return render(request, 'coreapp/ahc/hasil.html', context)

# ================================
# AI ENGINE
# ================================
def generate_ai_insight(summary_cluster, silhouette):

    if not summary_cluster:
        return "Belum ada data untuk dianalisis."

    total_data = sum(s['jumlah'] for s in summary_cluster)
    jumlah_cluster = len(summary_cluster)

    max_cluster = max(summary_cluster, key=lambda x: x['jumlah'])
    min_cluster = min(summary_cluster, key=lambda x: x['jumlah'])

    insight = "🧠 INTELLIGENT CLUSTER ANALYSIS\n"
    insight += "=" * 50 + "\n\n"

    insight += (
        f"Dataset terdiri dari {total_data} data dan terbagi menjadi "
        f"{jumlah_cluster} cluster.\n\n"
    )

    insight += (
        f"Cluster terbesar adalah {max_cluster['cluster']} "
        f"({max_cluster['jumlah']} data).\n"
        f"Cluster terkecil adalah {min_cluster['cluster']} "
        f"({min_cluster['jumlah']} data).\n\n"
    )

    for s in summary_cluster:
        insight += (
            f"- Cluster {s['cluster']}: {s['jumlah']} data, "
            f"umur {s['rata_umur']}, faktor {s['faktor_dominan']}, "
            f"waktu {s['waktu_dominan']}\n"
        )

    insight += "\n"

    if silhouette is not None:
        insight += f"Silhouette Score: {silhouette}\n"

        if silhouette > 0.5:
            insight += "Kualitas clustering sangat baik.\n"
        elif silhouette > 0.25:
            insight += "Kualitas clustering cukup.\n"
        else:
            insight += "Kualitas clustering kurang optimal.\n"

    return insight


# ================================
# RESET
# ================================
@login_required(login_url='login')
def reset_ahc(request):

    keys = [
        'hasil_cluster',
        'summary_cluster',
        'jumlah_cluster',
        'jumlah_data',
        'silhouette_score',
        'X_scaled',
        'summary_df'
    ]

    for k in keys:
        request.session.pop(k, None)

    return redirect('ahc_proses')