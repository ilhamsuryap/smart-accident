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
    Kota, Kecamatan, Kelurahan, ClusterData, AIConfig
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

from .models import RuasJalan, SegmenJalan, Kecelakaan, RekapSegmen, AnalisisZScore, KecelakaanRaw, KecelakaanPreprosesing, LakaMentah
from django.core.paginator import Paginator
from .forms import (
    UserRegistrationForm, RuasJalanForm, SegmenJalanForm, 
    KecelakaanForm, RekapSegmenForm, UploadKecelakaanRawForm, UploadKecelakaanPreprosesForm
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


# Homepage View
def homepage_view(request):
    """Halaman homepage untuk user biasa"""
    context = {
        'total_ruas': RuasJalan.objects.count(),
        'total_segmen': SegmenJalan.objects.count(),
        'total_kecelakaan': KecelakaanPreprosesing.objects.count(),
        'total_korban': KecelakaanPreprosesing.objects.aggregate(
            total=Sum('korban_meninggal') + Sum('korban_luka_berat') + Sum('korban_luka_ringan')
        )['total'] or 0,
    }
    return render(request, 'homepage.html', context)


# Dashboard Views
@login_required(login_url='login')
def dashboard_view(request):
    """Dashboard utama - untuk admin/user yang login"""
    context = {
        'total_ruas': RuasJalan.objects.count(),
        'total_segmen': SegmenJalan.objects.count(),
        'total_kecelakaan': KecelakaanPreprosesing.objects.count(),
        'total_korban': KecelakaanPreprosesing.objects.aggregate(
            total=Sum('korban_meninggal') + Sum('korban_luka_berat') + Sum('korban_luka_ringan')
        )['total'] or 0,
    }
    
    # Statistik tahun ini
    tahun_ini = timezone.now().year
    context['kecelakaan_tahun_ini'] = KecelakaanPreprosesing.objects.filter(
        tanggal__year=tahun_ini
    ).count()
    
    # Segmen dengan kecelakaan terbanyak
    context['top_segmen'] = SegmenJalan.objects.annotate(
        jumlah_kecelakaan=Count('kecelakaan_preprosesing')
    ).order_by('-jumlah_kecelakaan')[:5]

    # --- Statistik Data Cluster (Non-AHC Parameters) ---
    cluster_data = ClusterData.objects.all()
    context['total_cluster_data'] = cluster_data.count()
    
    # 1. Distribusi Jenis Kendaraan (Semua data)
    context['top_vehicles'] = list(cluster_data.values('jenis_kendaraan').annotate(
        count=Count('id')
    ).order_by('-count'))
    
    # 2. Distribusi Hari (Top Days)
    context['day_dist'] = list(cluster_data.values('hari').annotate(
        count=Count('id')
    ).order_by('-count'))
    
    # 3. Top 5 TKP
    context['top_tkp'] = list(cluster_data.values('tkp').annotate(
        count=Count('id')
    ).order_by('-count')[:5])
    
    # 4. Top 5 Jam (Sesi Waktu)
    context['top_hours'] = list(cluster_data.values('jam').annotate(
        count=Count('id')
    ).order_by('-count')[:5])

    # 5. Distribusi Penyebab (Cleaned)
    all_cluster_data = list(cluster_data)
    causes_map = {}
    for item in all_cluster_data:
        cause = item.penyebab.strip().lower() if item.penyebab else 'tidak diketahui'
        causes_map[cause] = causes_map.get(cause, 0) + 1
        
    sorted_causes = [{'penyebab': k, 'count': v} for k, v in sorted(causes_map.items(), key=lambda x: x[1], reverse=True)]
    context['causes_dist'] = sorted_causes
    
    if sorted_causes:
        context['dominant_cause'] = sorted_causes[0]['penyebab']
        context['dominant_cause_count'] = sorted_causes[0]['count']
    else:
        context['dominant_cause'] = 'N/A'
        context['dominant_cause_count'] = 0
        
    # 6. Distribusi Umur (7 Groups)
    age_groups = {
        '< 15': 0,
        '15-24': 0,
        '25-34': 0,
        '35-44': 0,
        '45-54': 0,
        '55-64': 0,
        '65+': 0
    }
    
    for item in all_cluster_data:
        age = item.umur
        if age < 15:
            age_groups['< 15'] += 1
        elif 15 <= age <= 24:
            age_groups['15-24'] += 1
        elif 25 <= age <= 34:
            age_groups['25-34'] += 1
        elif 35 <= age <= 44:
            age_groups['35-44'] += 1
        elif 45 <= age <= 54:
            age_groups['45-54'] += 1
        elif 55 <= age <= 64:
            age_groups['55-64'] += 1
        else:
            age_groups['65+'] += 1
            
    context['age_dist'] = [{'range': k, 'count': v} for k, v in age_groups.items()]
    
    # Find top age range
    top_age_range = max(age_groups, key=age_groups.get) if age_groups else 'N/A'
    context['top_age_range'] = top_age_range
    context['top_age_range_count'] = age_groups.get(top_age_range, 0)

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


# Profil Views
@login_required
def profile_view(request):
    user = request.user

    if request.method == "POST":
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")

        full_name = request.POST.get("full_name")
        if full_name:
            nama = full_name.split(" ", 1)
            user.first_name = nama[0]
            user.last_name = nama[1] if len(nama) > 1 else ""

        user.save()

        return redirect('profile')

    return render(request, 'profile.html')


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
    
    context = {'kecelakaan': kecelakaan, 'cancel_url': 'kecelakaan_list'}
    return render(request, 'coreapp/kecelakaan/confirm_delete.html', context)

# Map Views
@login_required(login_url='login')
def map_view(request):
    """Tampilkan peta interaktif untuk admin (dengan sidebar)"""
    tahun_param = request.GET.get('tahun')
    tahun = timezone.now().year
    
    if tahun_param:
        try:
            tahun = int(tahun_param)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
    # Hitung Z-Score jika belum ada
    try:
        if not AnalisisZScore.objects.filter(tahun=tahun).exists():
            AnalisisZScore.calculate_zscore(tahun)
    except Exception as e:
        print(f"Warning: Could not calculate Z-Score for {tahun}: {e}")
    
    context = {
        'tahun': tahun,
        'tahun_options': range(2020, timezone.now().year + 1)
    }
    return render(request, 'coreapp/map/map.html', context)


def peta_user_view(request):
    """Tampilkan peta interaktif untuk user biasa (tanpa sidebar, standalone)"""
    tahun_param = request.GET.get('tahun')
    tahun = timezone.now().year
    
    if tahun_param:
        try:
            tahun = int(tahun_param)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
    # Hitung Z-Score jika belum ada
    try:
        if not AnalisisZScore.objects.filter(tahun=tahun).exists():
            AnalisisZScore.calculate_zscore(tahun)
    except Exception as e:
        print(f"Warning: Could not calculate Z-Score for {tahun}: {e}")
    
    context = {
        'tahun': tahun,
        'tahun_options': range(2020, timezone.now().year + 1)
    }
    return render(request, 'peta_user.html', context)


# API Views
@api_view(['GET'])
def api_segmen_geojson(request):
    """API untuk mendapatkan GeoJSON segmen jalan dengan Z-Score atau default blue untuk no accidents"""
    tahun_raw = request.GET.get('tahun')
    if not tahun_raw or tahun_raw == 'None':
        tahun = timezone.now().year
    else:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
    print(f"\n{'='*80}")
    print(f"📍 API: api_segmen_geojson called for tahun={tahun}")
    print(f"{'='*80}")
    
    # Ensure Z-Score calculation exists for this year
    if not AnalisisZScore.objects.filter(tahun=tahun).exists():
        try:
            AnalisisZScore.calculate_zscore(tahun)
            print(f"✓ Auto-calculated Z-Score for {tahun}")
        except Exception as e:
            print(f"⚠ Could not auto-calculate Z-Score: {e}")
    
    segmen_list = SegmenJalan.objects.select_related('ruas_jalan').all()
    print(f"📊 Found {segmen_list.count()} segments in database")
    
    features = []
    line_count = 0
    marker_count = 0
    
    for segmen in segmen_list:
        # Hitung jumlah kecelakaan di segmen ini untuk tahun tertentu
        accident_count = KecelakaanPreprosesing.objects.filter(
            segmen_jalan=segmen,
            tanggal__year=tahun
        ).count()
        
        # PENTING: Jika tidak ada kecelakaan, selalu set AMAN (ignore Z-Score jika ada)
        if accident_count == 0:
            kategori = 'aman'
            zscore = -2.0
            color = '#1976d2'  # Blue
        else:
            # Ada kecelakaan - cari analisis Z-Score
            try:
                analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
                kategori = analisis.kategori
                zscore = float(analisis.nilai_zscore)
                color = analisis.get_kategori_display_color()
            except AnalisisZScore.DoesNotExist:
                # Ada kecelakaan tapi belum ada Z-Score → coba hitung
                try:
                    AnalisisZScore.calculate_zscore(tahun)
                    analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
                    kategori = analisis.kategori
                    zscore = float(analisis.nilai_zscore)
                    color = analisis.get_kategori_display_color()
                except Exception:
                    kategori = 'unknown'
                    zscore = 0
                    color = '#999999'
        
        # PENTING: Generate geometry dari lat/lon jika kosong
        geometry = None
        if segmen.geometry:
            try:
                parsed_geom = json.loads(segmen.geometry)
                # Convert MultiLineString to LineString untuk rendering yang lebih baik
                if parsed_geom.get('type') == 'MultiLineString':
                    coords = []
                    for line in parsed_geom.get('coordinates', []):
                        coords.extend(line)
                    geometry = {'type': 'LineString', 'coordinates': coords}
                    print(f"✓ Converted MultiLineString to LineString for segmen {segmen.id}")
                else:
                    geometry = parsed_geom
            except Exception as e:
                print(f"⚠ Error parsing geometry for segmen {segmen.id}: {e}")
                geometry = None
        
        # Fallback: Jika geometry kosong, buat dari lat/lon awal-akhir
        if not geometry:
            if segmen.lat_awal and segmen.lon_awal and segmen.lat_akhir and segmen.lon_akhir:
                geometry = {
                    'type': 'LineString',
                    'coordinates': [
                        [float(segmen.lon_awal), float(segmen.lat_awal)],
                        [float(segmen.lon_akhir), float(segmen.lat_akhir)]
                    ]
                }
                print(f"✓ Generated fallback geometry for segmen {segmen.id} from lat/lon")
            else:
                # Coba ambil dari ruas_jalan geometry
                if segmen.ruas_jalan.geometry:
                    try:
                        ruas_geom = json.loads(segmen.ruas_jalan.geometry)
                        if ruas_geom.get('type') == 'Feature':
                            ruas_geom = ruas_geom.get('geometry', {})
                        
                        if ruas_geom.get('type') == 'LineString':
                            geometry = ruas_geom
                        elif ruas_geom.get('type') == 'MultiLineString':
                            coords = []
                            for line in ruas_geom.get('coordinates', []):
                                coords.extend(line)
                            geometry = {'type': 'LineString', 'coordinates': coords}
                        
                        if geometry:
                            print(f"✓ Generated geometry for segmen {segmen.id} from ruas_jalan")
                    except Exception as e:
                        print(f"⚠ Error getting ruas geometry for segmen {segmen.id}: {e}")
        
        if geometry:
            # 1. Feature LineString (Garis Jalan)
            feature_line = {
                'type': 'Feature',
                'id': f"line_{segmen.id}",
                'properties': {
                    'type': 'line',
                    'segmen_id': segmen.id,
                    'ruas_id': segmen.ruas_jalan.id,
                    'ruas_nama': segmen.ruas_jalan.nama_ruas,
                    'km_awal': float(segmen.km_awal),
                    'km_akhir': float(segmen.km_akhir),
                    'panjang': float(segmen.panjang_segmen),
                    'kategori': kategori,
                    'zscore': zscore,
                    'color': color,
                    'accident_count': accident_count,
                    'nama_segmen': segmen.nama_segmen or f"Segmen {segmen.km_awal}-{segmen.km_akhir}",
                    'keterangan': segmen.keterangan or '',
                    'url': f'/kecelakaan/segmen/{segmen.id}/'
                },
                'geometry': geometry
            }
            features.append(feature_line)
            line_count += 1

            # 2. Feature Point - Marker AWAL segmen
            if geometry.get('coordinates') and len(geometry['coordinates']) > 0:
                coords = geometry['coordinates']
                start_point = coords[0]
                end_point = coords[-1]
                
                # Marker awal segmen
                feature_point_start = {
                    'type': 'Feature',
                    'id': f"point_start_{segmen.id}",
                    'properties': {
                        'type': 'segment_marker',
                        'marker_type': 'start',
                        'segmen_id': segmen.id,
                        'ruas_id': segmen.ruas_jalan.id,
                        'ruas_nama': segmen.ruas_jalan.nama_ruas,
                        'km_awal': float(segmen.km_awal),
                        'km_akhir': float(segmen.km_akhir),
                        'panjang': float(segmen.panjang_segmen),
                        'kategori': kategori,
                        'zscore': zscore,
                        'color': color,
                        'accident_count': accident_count,
                        'nama_segmen': segmen.nama_segmen or f"Segmen {segmen.km_awal}-{segmen.km_akhir}",
                        'keterangan': segmen.keterangan or '',
                        'url': f'/kecelakaan/segmen/{segmen.id}/'
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': start_point
                    }
                }
                features.append(feature_point_start)
                marker_count += 1
                
                # Marker akhir segmen
                feature_point_end = {
                    'type': 'Feature',
                    'id': f"point_end_{segmen.id}",
                    'properties': {
                        'type': 'segment_marker',
                        'marker_type': 'end',
                        'segmen_id': segmen.id,
                        'ruas_id': segmen.ruas_jalan.id,
                        'ruas_nama': segmen.ruas_jalan.nama_ruas,
                        'km_awal': float(segmen.km_awal),
                        'km_akhir': float(segmen.km_akhir),
                        'panjang': float(segmen.panjang_segmen),
                        'kategori': kategori,
                        'zscore': zscore,
                        'color': color,
                        'accident_count': accident_count,
                        'nama_segmen': segmen.nama_segmen or f"Segmen {segmen.km_awal}-{segmen.km_akhir}",
                        'keterangan': segmen.keterangan or '',
                        'url': f'/kecelakaan/segmen/{segmen.id}/'
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': end_point
                    }
                }
                features.append(feature_point_end)
                marker_count += 1
        else:
            print(f"❌ Segmen {segmen.id} ({segmen.ruas_jalan.nama_ruas}) - NO geometry available!")
    
    # Add markers untuk start/end dari setiap ruas jalan
    ruas_segments = {}
    for segmen in segmen_list:
        if segmen.ruas_jalan.id not in ruas_segments:
            ruas_segments[segmen.ruas_jalan.id] = []
        ruas_segments[segmen.ruas_jalan.id].append(segmen)
    
    # Create markers untuk ruas jalan start/end
    for ruas_id, segments in ruas_segments.items():
        # Sort by km_awal to find first and last segment
        sorted_segments = sorted(segments, key=lambda s: float(s.km_awal))
        if sorted_segments:
            ruas_jalan = sorted_segments[0].ruas_jalan
            
            # Marker untuk AWAL ruas jalan
            first_segmen = sorted_segments[0]
            if first_segmen.geometry:
                try:
                    geom = json.loads(first_segmen.geometry)
                    if geom.get('type') == 'LineString' and geom.get('coordinates'):
                        start_coord = geom['coordinates'][0]
                        feature_ruas_start = {
                            'type': 'Feature',
                            'id': f"ruas_start_{ruas_id}",
                            'properties': {
                                'type': 'segment_marker',
                                'marker_type': 'ruas_start',
                                'ruas_id': ruas_id,
                                'ruas_nama': ruas_jalan.nama_ruas,
                                'label': f'Awal Ruas: {ruas_jalan.nama_ruas}'
                            },
                            'geometry': {
                                'type': 'Point',
                                'coordinates': start_coord
                            }
                        }
                        features.append(feature_ruas_start)
                        marker_count += 1
                except Exception as e:
                    print(f"⚠ Error creating ruas start marker for {ruas_jalan.nama_ruas}: {e}")
            
            # Marker untuk AKHIR ruas jalan
            last_segmen = sorted_segments[-1]
            if last_segmen.geometry:
                try:
                    geom = json.loads(last_segmen.geometry)
                    if geom.get('type') == 'LineString' and geom.get('coordinates'):
                        end_coord = geom['coordinates'][-1]
                        feature_ruas_end = {
                            'type': 'Feature',
                            'id': f"ruas_end_{ruas_id}",
                            'properties': {
                                'type': 'segment_marker',
                                'marker_type': 'ruas_end',
                                'ruas_id': ruas_id,
                                'ruas_nama': ruas_jalan.nama_ruas,
                                'label': f'Akhir Ruas: {ruas_jalan.nama_ruas}'
                            },
                            'geometry': {
                                'type': 'Point',
                                'coordinates': end_coord
                            }
                        }
                        features.append(feature_ruas_end)
                        marker_count += 1
                except Exception as e:
                    print(f"⚠ Error creating ruas end marker for {ruas_jalan.nama_ruas}: {e}")
    
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    print(f"✅ Response: {line_count} lines, {marker_count} markers - {len(features)} total features")
    print(f"{'='*80}\n")
    
    return Response(geojson)


@api_view(['GET'])
def api_threshold_data(request):
    """API untuk mendapatkan threshold data per ruas jalan untuk dynamic legend"""
    from django.db.models import Avg, StdDev
    
    tahun_raw = request.GET.get('tahun')
    if not tahun_raw or tahun_raw == 'None':
        tahun = timezone.now().year
    else:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
    # Ensure Z-Score calculation exists
    if not AnalisisZScore.objects.filter(tahun=tahun).exists():
        try:
            AnalisisZScore.calculate_zscore(tahun)
        except Exception as e:
            print(f"Warning: Could not auto-calculate Z-Score: {e}")
    
    ruas_jalan_list = RuasJalan.objects.all().distinct()
    threshold_data = {}
    
    for ruas_jalan in ruas_jalan_list:
        segments_in_ruas = SegmenJalan.objects.filter(ruas_jalan=ruas_jalan)
        
        # Get all z-scores for this ruas jalan
        analisis_list = AnalisisZScore.objects.filter(
            tahun=tahun,
            segmen_jalan__in=segments_in_ruas
        )
        
        if analisis_list.exists():
            zscore_values = [float(a.nilai_zscore) for a in analisis_list]
            z_max = max(zscore_values)
            z_min = min(zscore_values)
            
            # Calculate interval
            if z_max != z_min:
                interval = (z_max - z_min) / 5
            else:
                interval = 1
            
            # Calculate thresholds
            t1 = z_min + (1 * interval)
            t2 = z_min + (2 * interval)
            t3 = z_min + (3 * interval)
            t4 = z_min + (4 * interval)
            
            # Count segments per kategori
            kategori_counts = {
                'sangat_tinggi': analisis_list.filter(kategori='sangat_tinggi').count(),
                'tinggi': analisis_list.filter(kategori='tinggi').count(),
                'sedang': analisis_list.filter(kategori='sedang').count(),
                'rendah': analisis_list.filter(kategori='rendah').count(),
                'sangat_rendah': analisis_list.filter(kategori='sangat_rendah').count(),
            }
            
            threshold_data[ruas_jalan.id] = {
                'nama': ruas_jalan.nama_ruas,
                'z_max': round(z_max, 3),
                'z_min': round(z_min, 3),
                'interval': round(interval, 3),
                't4': round(t4, 3),  # sangat_tinggi threshold
                't3': round(t3, 3),  # tinggi threshold
                't2': round(t2, 3),  # sedang threshold
                't1': round(t1, 3),  # rendah threshold
                'kategori_counts': kategori_counts,
                'total_segments': segments_in_ruas.count(),
            }
    
    return Response({
        'tahun': tahun,
        'ruas_data': threshold_data
    })


@api_view(['GET'])
@login_required(login_url='login')
def api_kecelakaan_geojson(request):
    """API untuk mendapatkan GeoJSON kecelakaan"""
    tahun = request.GET.get('tahun', timezone.now().year)
    
    kecelakaan = KecelakaanPreprosesing.objects.filter(
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


def api_data_update_check(request):
    """
    API untuk mengecek apakah ada update data terbaru
    Mengembalikan timestamp dari last update KecelakaanPreprosesing
    Frontend bisa compare dengan last known timestamp untuk trigger refresh
    """
    from django.db.models import Max
    
    tahun = request.GET.get('tahun')
    if not tahun:
        tahun = timezone.now().year
    else:
        try:
            tahun = int(tahun)
        except (ValueError, TypeError):
            tahun = timezone.now().year
    
    try:
        # Get latest updated_at from KecelakaanPreprosesing for this year
        latest_kecelakaan = KecelakaanPreprosesing.objects.filter(
            tanggal__year=tahun
        ).aggregate(
            latest_update=Max('updated_at'),
            latest_create=Max('created_at')
        )
        
        # Get latest update timestamp
        latest_update = latest_kecelakaan['latest_update'] or latest_kecelakaan['latest_create']
        
        # Get latest AnalisisZScore calculation timestamp
        latest_zscore = AnalisisZScore.objects.filter(tahun=tahun).values('id').last()
        
        return JsonResponse({
            'status': 'success',
            'tahun': tahun,
            'last_data_update': latest_update.timestamp() if latest_update else None,
            'has_zscore': latest_zscore is not None
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


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
    
    kecelakaan = KecelakaanPreprosesing.objects.filter(
        segmen_jalan=segmen,
        tanggal__year=tahun
    )
    
    # Calculate totals for the summary section
    rekap = kecelakaan.aggregate(
        total_meninggal=Sum('korban_meninggal'),
        total_luka_berat=Sum('korban_luka_berat'),
        total_luka_ringan=Sum('korban_luka_ringan')
    )
    
    total_meninggal = rekap['total_meninggal'] or 0
    total_luka = (rekap['total_luka_berat'] or 0) + (rekap['total_luka_ringan'] or 0)
    
    try:
        analisis = AnalisisZScore.objects.get(segmen_jalan=segmen, tahun=tahun)
    except AnalisisZScore.DoesNotExist:
        analisis = None
    
    context = {
        'segmen': segmen,
        'kecelakaan': kecelakaan,
        'analisis': analisis,
        'tahun': tahun,
        'tahun_options': range(2020, timezone.now().year + 1),
        'total_meninggal': total_meninggal,
        'total_luka': total_luka,
        'is_admin': is_admin(request.user)
    }
    
    return render(request, 'coreapp/analisis/segmen_detail.html', context)


@login_required(login_url='login')
def kecelakaan_raw_detail(request, pk):
    """Detail kecelakaan raw"""
    kecelakaan = get_object_or_404(KecelakaanRaw, pk=pk)
    return render(request, 'coreapp/kecelakaan/detail.html', {'kecelakaan': kecelakaan, 'type': 'Raw'})


@login_required(login_url='login')
def kecelakaan_preprosesing_detail(request, pk):
    """Detail kecelakaan preprocessing"""
    kecelakaan = get_object_or_404(KecelakaanPreprosesing, pk=pk)
    return render(request, 'coreapp/kecelakaan/detail.html', {'kecelakaan': kecelakaan, 'type': 'Preprocessing'})


@login_required(login_url='login')
@user_passes_test(is_admin)
def kecelakaan_raw_delete(request, pk):
    """Hapus data kecelakaan raw"""
    kecelakaan = get_object_or_404(KecelakaanRaw, pk=pk)
    if request.method == 'POST':
        kecelakaan.delete()
        messages.success(request, 'Data kecelakaan raw berhasil dihapus.')
        return redirect('kecelakaan_raw_list')
    return render(request, 'coreapp/kecelakaan/confirm_delete.html', {'kecelakaan': kecelakaan, 'type': 'Raw', 'cancel_url': 'kecelakaan_raw_list'})


@login_required(login_url='login')
@user_passes_test(is_admin)
def kecelakaan_preprosesing_delete(request, pk):
    """Hapus data kecelakaan preprocessing"""
    kecelakaan = get_object_or_404(KecelakaanPreprosesing, pk=pk)
    if request.method == 'POST':
        kecelakaan.delete()
        messages.success(request, 'Data kecelakaan preprocessing berhasil dihapus.')
        return redirect('kecelakaan_preprosesing_list')
    return render(request, 'coreapp/kecelakaan/confirm_delete.html', {'kecelakaan': kecelakaan, 'type': 'Preprocessing', 'cancel_url': 'kecelakaan_preprosesing_list'})


# Cluster K-Means Views
@login_required(login_url='login')
def cluster_data(request):
    data = Kecelakaan.objects.all()[:50]

    context = {
        'kecelakaan': data
    }

    return render(request, 'coreapp/data_cluster/cluster.html', context)




# ================================
# PREPROCESSING DATA
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


# ===============================
# AHC VIEWS
# ===============================

# ================================
# HALAMAN DATA
# ================================

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
            data_db = ClusterData.objects.all().values()
            if not data_db:
                messages.error(request, "Data di database masih kosong.")
                return redirect('cluster_data_list')
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

    # Ambil API KEY dari Database (Prioritas: Config DB > .env)
    config = AIConfig.objects.filter(tipe='kmeans').first()
    api_key_db = config.api_key.strip() if (config and config.api_key) else None
    api_key_env = os.environ.get('GEMINI_API_KEY', '').strip()
    api_key = api_key_db or api_key_env

    if not api_key:
        return JsonResponse({"success": False, "message": "API Key belum dikonfigurasi."}, status=400)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }
    
    print("\n" + "="*50)
    print(" [AI REQUEST DEBUG] - KMEANS REKOMENDASI")
    print(f" URL: {url.split('?')[0]}")
    print(f" Using Key: {api_key[:6]}...{api_key[-4:]} (Source: {'DB' if api_key_db else 'ENV'})")

    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer): return int(obj)
            if isinstance(obj, np.floating): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            return super(NpEncoder, self).default(obj)

    prompt = f"""
    Sebagai AI Ahli Keselamatan Jalan, berikan rekomendasi kebijakan berdasarkan data clustering K-Means berikut.
    
    DATA RINGKASAN:
    - Total Unit Analisis: {total} slot waktu (Hari + Jam)
    - Slot Risiko Tinggi (Cluster Tinggi): {tinggi} titik ({persen}%)
    - Titik Terkritis: {waktu_rawan}
    
    SAMPEL DATA CLUSTER TINGGI (High Risk):
    {json.dumps(cluster_sample, cls=NpEncoder)}
    
    INSTRUKSI ANALISIS:
    1. Identifikasi pola temporal (hari/jam) yang menjadi hotspot kecelakaan.
    2. Berikan matriks intervensi yang spesifik dan terukur (patroli, infrastruktur, regulasi).
    3. Targetkan pengurangan angka kecelakaan berdasarkan densitas cluster tinggi.
    
    FORMAT OUTPUT (HARUS JSON VALID MURNI):
    {{
        "ringkasan": "Analisis kritis terhadap korelasi hari/jam dan frekuensi kejadian.",
        "prioritas_tinggi": [
            {{ 
                "waktu": "Hari X Pukul Y", 
                "kejadian": "Z kejadian", 
                "tindakan": {{ 
                    "patroli": "Tindakan pengawasan spesifik", 
                    "infrastruktur": ["Perbaikan rambu/lampu", "Markah jalan"] 
                }} 
            }}
        ],
        "jadwal_patroli": [
            {{ "hari": "...", "jam": "...", "fokus": "Aspek utama yang diawasi", "unit": "X" }}
        ],
        "target_kpi": {{
            "pengurangan": "Estimasi % pengurangan jika rekomendasi dijalankan",
            "indikator": ["Key Performance Indicator 1", "KPI 2"]
        }},
        "program": {{
            "jangka_pendek": ["Langkah darurat 1 bulan"],
            "jangka_menengah": ["Pembangunan/Regulasi 6-12 bulan"]
        }},
        "catatan": "Pesan penutup strategis."
    }}
    - Bahasa Indonesia formal.
    - Tanpa penjelasan markdown di luar JSON.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    print("\n" + "="*50)
    print(" [AI REQUEST DEBUG] - KMEANS REKOMENDASI")
    print(f" URL: {url.split('?')[0]}")
    print(f" Using Key: {api_key[:6]}...{api_key[-4:]} (Source: {'DB' if api_key_db else 'ENV'})")
    
    import time
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f" Status Code: {response.status_code}")
        print(f" Time Taken: {round(time.time() - start_time, 2)}s")
        
        res_json = response.json()
        
        if response.status_code != 200:
            print(f" ERROR RESPONSE: {json.dumps(res_json, indent=2)}")
        else:
            print(" RESPONSE: Success")
            
        print("="*50 + "\n")
        
        if 'candidates' not in res_json or not res_json['candidates']:
            error_msg = res_json.get('error', {}).get('message', 'Gemini API tidak mengembalikan hasil.')
            http_code = response.status_code
            # Jika error dari sisi Google (5xx/429), jangan propagate sebagai 400
            friendly = "Server AI sedang sibuk atau overload. Silakan coba beberapa saat lagi." \
                if http_code in (429, 503, 500, 502, 504) else f"AI Error: {error_msg}"
            return JsonResponse({"success": False, "message": friendly}, status=200)

        raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()
        
        try:
            ai_data = json.loads(clean_text)
        except json.JSONDecodeError:
            # Fallback jika AI tidak memberikan JSON murni meskipun sudah diinstruksikan
            return JsonResponse({"success": False, "message": "AI tidak mengembalikan format data yang valid."}, status=500)

        request.session['ai_recommendation_data'] = ai_data
        request.session.modified = True
        return JsonResponse({"success": True, "data": ai_data})
    except requests.exceptions.Timeout:
        return JsonResponse({"success": False, "message": "Koneksi ke AI (Gemini) timeout."}, status=504)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"System Error: {str(e)}"}, status=500)

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
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer): return int(obj)
            if isinstance(obj, np.floating): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            return super(NpEncoder, self).default(obj)

    prompt = f"""
    Analisis data clustering K-Means kecelakaan berikut (Total {total_incidents} kejadian):

    1. DISTRIBUSI CLUSTER:
    {json.dumps(clusters, cls=NpEncoder)}

    2. HOTSPOTS (Titik Tertinggi):
    {json.dumps(hotspot_list, cls=NpEncoder)}

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

    # Ambil API KEY dari Database (Prioritas: Config DB > .env)
    config = AIConfig.objects.filter(tipe='kmeans').first()
    api_key_db = config.api_key.strip() if (config and config.api_key) else None
    api_key_env = os.environ.get('GEMINI_API_KEY', '').strip()
    api_key = api_key_db or api_key_env

    if not api_key:
        return JsonResponse({"success": False, "message": "API Key belum dikonfigurasi."}, status=400)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }
    
    print("\n" + "="*50)
    print(" [AI REQUEST DEBUG] - KMEANS ANALISIS")
    print(f" URL: {url.split('?')[0]}")
    print(f" Using Key: {api_key[:6]}...{api_key[-4:]} (Source: {'DB' if api_key_db else 'ENV'})")
    print(f" Model: gemini-flash-latest")
    
    import time
    start_time = time.time()
    
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f" Status Code: {response.status_code}")
        print(f" Time Taken: {round(time.time() - start_time, 2)}s")
        
        res_json = response.json()
        
        if response.status_code != 200:
            print(f" ERROR RESPONSE: {json.dumps(res_json, indent=2)}")
        else:
            print(" RESPONSE: Success")

        print("="*50 + "\n")
        
        if 'candidates' not in res_json or not res_json['candidates']:
            error_msg = res_json.get('error', {}).get('message', 'Gemini API tidak mengembalikan hasil.')
            http_code = response.status_code
            friendly = "Server AI sedang sibuk atau overload. Silakan coba beberapa saat lagi." \
                if http_code in (429, 503, 500, 502, 504) else f"AI Error: {error_msg}"
            return JsonResponse({"success": False, "message": friendly}, status=200)
            
        raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
        # Pembersihan jika ada markdown
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()
        
        try:
            analysis_data = json.loads(clean_text)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "AI tidak mengembalikan format analisis yang valid."}, status=500)

        # Simpan di session untuk persistensi
        request.session['ai_dashboard_analysis'] = analysis_data
        request.session.modified = True

        return JsonResponse({"success": True, "analysis": analysis_data})
    except requests.exceptions.Timeout:
        return JsonResponse({"success": False, "message": "Koneksi ke AI (Gemini) timeout."}, status=504)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"System Error: {str(e)}"}, status=500)

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
def cluster_data_list(request):
    all_data = ClusterData.objects.all()
    total_count = all_data.count()
    
    # Hitung duplikasi (data yang isinya persis sama di semua kolom utama)
    duplicate_groups = ClusterData.objects.values(
        'no_referensi', 'umur', 'tkp', 'penyebab', 'hari', 'tanggal', 'jam', 
        'jenis_kendaraan', 'tipe_kendaraan', 'kerugian_material'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    jumlah_duplikat = sum(group['count'] - 1 for group in duplicate_groups)

    # Ambil detail data duplikat untuk ditampilkan di modal
    duplicate_data_details = []
    for group in duplicate_groups:
        # Ambil satu contoh data untuk setiap grup duplikat
        example = ClusterData.objects.filter(
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
        'ai_config_ahc': AIConfig.objects.filter(tipe='ahc').first(),
    }
    return render(request, 'coreapp/data_cluster/list.html', context)

@login_required(login_url='login')
def cluster_data_tambah(request):
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

        ClusterData.objects.create(
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
        return redirect('cluster_data_list')

    # Dropdown data: Ambil unik, hilangkan yang kosong/null, urutkan
    def get_unique_choices(field):
        # Ambil dari DB
        raw_choices = ClusterData.objects.exclude(**{f"{field}__isnull": True}).exclude(**{f"{field}": ""}).values_list(field, flat=True).distinct()
        
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
    return render(request, 'coreapp/data_cluster/tambah.html', context)

@login_required(login_url='login')
def cluster_data_edit(request, pk):
    from django.shortcuts import get_object_or_404
    data = get_object_or_404(ClusterData, pk=pk)
    
    if request.method == "POST":
        umur = request.POST.get('umur')
        tkp = request.POST.get('tkp')
        penyebab = request.POST.get('penyebab')
        tanggal_raw = request.POST.get('tanggal')
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

        data.umur = umur
        data.tkp = str(tkp).strip()
        data.penyebab = str(penyebab).strip()
        data.hari = str(hari).strip()
        data.tanggal = tanggal_raw
        data.jam = normalize_jam(jam)
        data.jenis_kendaraan = str(jenis_kendaraan).strip()
        data.tipe_kendaraan = str(tipe_kendaraan).strip()
        data.kerugian_material = kerugian_material
        data.save()
        
        messages.success(request, "Data berhasil diupdate.")
        return redirect('cluster_data_list')

    # Dropdown data: Ambil unik, hilangkan yang kosong/null, urutkan
    def get_unique_choices(field):
        raw_choices = ClusterData.objects.exclude(**{f"{field}__isnull": True}).exclude(**{f"{field}": ""}).values_list(field, flat=True).distinct()
        cleaned = set()
        for c in raw_choices:
            if c:
                cleaned.add(str(c).strip())
        return sorted(list(cleaned))

    context = {
        'data': data,
        'tkp_choices': get_unique_choices('tkp'),
        'penyebab_choices': get_unique_choices('penyebab'),
        'jenis_choices': get_unique_choices('jenis_kendaraan'),
        'tipe_choices': get_unique_choices('tipe_kendaraan'),
    }
    return render(request, 'coreapp/data_cluster/edit.html', context)

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
def cluster_data_import(request):
    if request.method == "POST":
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Silakan pilih file excel.")
            return redirect('cluster_data_list')
        
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
                    
                    ClusterData.objects.create(
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
            
        return redirect('cluster_data_list')
    
    return redirect('cluster_data_list')

@login_required(login_url='login')
def cluster_data_hapus(request, pk):
    ClusterData.objects.filter(pk=pk).delete()
    messages.success(request, "Data berhasil dihapus.")
    return redirect('cluster_data_list')

@login_required(login_url='login')
def cluster_data_hapus_semua(request):
    ClusterData.objects.all().delete()
    messages.success(request, "Semua data berhasil dihapus.")
    return redirect('cluster_data_list')

@login_required(login_url='login')
def cluster_data_hapus_duplikat(request):
    if request.method == "POST":
        duplicate_groups = ClusterData.objects.values(
            'no_referensi', 'umur', 'tkp', 'penyebab', 'hari', 'tanggal', 'jam', 
            'jenis_kendaraan', 'tipe_kendaraan', 'kerugian_material'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        deleted_count = 0
        for group in duplicate_groups:
            ids = list(ClusterData.objects.filter(
                no_referensi=group['no_referensi'],
                umur=group['umur'], tkp=group['tkp'], penyebab=group['penyebab'],
                hari=group['hari'], tanggal=group['tanggal'], jam=group['jam'],
                jenis_kendaraan=group['jenis_kendaraan'], tipe_kendaraan=group['tipe_kendaraan'],
                kerugian_material=group['kerugian_material']
            ).values_list('id', flat=True))
            
            # Keep one, delete the rest
            ids_to_delete = ids[1:]
            ClusterData.objects.filter(id__in=ids_to_delete).delete()
            deleted_count += len(ids_to_delete)
            
        messages.success(request, f"Berhasil menghapus {deleted_count} data duplikat.")
        return redirect('cluster_data_list')
    return redirect('cluster_data_list')

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
    return render(request, 'coreapp/data_cluster/tambah_kejadian.html')

def tambah_data_view(request):
    kota_list = Kota.objects.all()  # ambil semua kota
    return render(request, 'coreapp/data_cluster/tambah_kejadian.html', {
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


# ======================== Upload Kecelakaan Views ========================

@login_required(login_url='login')
@user_passes_test(is_admin)
def upload_kecelakaan_raw(request):
    """Upload data kecelakaan raw dari Excel/CSV"""
    if request.method == 'POST':
        form = UploadKecelakaanRawForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            try:
                # Parse Excel/CSV file
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file, encoding='utf-8-sig')
                else:
                    df = pd.read_excel(file)
                
                # Validasi kolom yang diperlukan
                required_columns = ['tanggal', 'waktu', 'latitude', 'longitude', 
                                   'korban_meninggal', 'korban_luka_berat', 
                                   'korban_luka_ringan', 'kerugian_materi', 
                                   'desa', 'kecamatan', 'kabupaten_kota', 'keterangan']
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f'Kolom yang hilang: {", ".join(missing_columns)}')
                    return render(request, 'coreapp/kecelakaan/upload_raw.html', {'form': form})
                
                # Check apakah nomor_kecelakaan ada (opsional)
                has_nomor = 'nomor_kecelakaan' in df.columns
                
                # Import data
                count = 0
                errors = []
                for idx, row in df.iterrows():
                    try:
                        # Parse waktu - handle berbagai format
                        waktu_obj = None
                        if pd.notna(row['waktu']):
                            waktu_val = row['waktu']
                            # Jika sudah dalam format time object
                            if isinstance(waktu_val, type(pd.Timestamp.now().time())):
                                waktu_obj = waktu_val
                            # Jika string
                            elif isinstance(waktu_val, str):
                                try:
                                    waktu_obj = pd.to_datetime(waktu_val).time()
                                except:
                                    raise ValueError(f"Format waktu '{waktu_val}' tidak valid (gunakan HH:MM:SS)")
                            # Jika Timestamp/datetime
                            else:
                                try:
                                    waktu_obj = pd.to_datetime(waktu_val).time()
                                except:
                                    raise ValueError(f"Kolom waktu berisi tanggal bukan jam. Gunakan format HH:MM:SS")
                        
                        # Build create dict with nomor_kecelakaan jika available
                        create_data = {
                            'tanggal': pd.to_datetime(row['tanggal']),
                            'waktu': waktu_obj,
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude']),
                            'korban_meninggal': int(row['korban_meninggal']) if pd.notna(row['korban_meninggal']) else 0,
                            'korban_luka_berat': int(row['korban_luka_berat']) if pd.notna(row['korban_luka_berat']) else 0,
                            'korban_luka_ringan': int(row['korban_luka_ringan']) if pd.notna(row['korban_luka_ringan']) else 0,
                            'kerugian_materi': float(row['kerugian_materi']) if pd.notna(row['kerugian_materi']) else 0,
                            'desa': str(row['desa']) if pd.notna(row['desa']) else '',
                            'kecamatan': str(row['kecamatan']) if pd.notna(row['kecamatan']) else '',
                            'kabupaten_kota': str(row['kabupaten_kota']) if pd.notna(row['kabupaten_kota']) else '',
                            'keterangan': str(row['keterangan']) if pd.notna(row['keterangan']) else ''
                        }
                        
                        # Tambah nomor_kecelakaan jika ada di file
                        if has_nomor and pd.notna(row['nomor_kecelakaan']):
                            create_data['nomor_kecelakaan'] = str(row['nomor_kecelakaan']).strip()
                        
                        KecelakaanRaw.objects.create(**create_data)
                        count += 1
                    except Exception as e:
                        errors.append(f"Baris {idx + 2}: {str(e)}")
                
                if errors and len(errors) <= 10:
                    messages.warning(request, f'Berhasil import {count} data, tapi ada beberapa error:\n' + '\n'.join(errors[:5]))
                else:
                    messages.success(request, f'Berhasil import {count} data kecelakaan raw.')
                
                return redirect('kecelakaan_raw_list')
            except Exception as e:
                messages.error(request, f'Error saat memproses file: {str(e)}')
    else:
        form = UploadKecelakaanRawForm()
    
    return render(request, 'coreapp/kecelakaan/upload_raw.html', {'form': form})


@login_required(login_url='login')
def kecelakaan_raw_list(request):
    """Daftar data kecelakaan raw"""
    kecelakaan = KecelakaanRaw.objects.all()
    
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
        'kecelakaan': kecelakaan[:100],
        'is_admin': is_admin(request.user),
        'tahun_options': range(2020, timezone.now().year + 1),
        'title': 'Data Kecelakaan Raw'
    }
    return render(request, 'coreapp/kecelakaan/list_raw.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin)
def upload_kecelakaan_preprosesing(request):
    """Upload data kecelakaan preprocessing dari Excel/CSV"""
    if request.method == 'POST':
        form = UploadKecelakaanPreprosesForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            try:
                # Parse Excel/CSV file
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file, encoding='utf-8-sig')
                else:
                    df = pd.read_excel(file)
                
                # Validasi kolom yang diperlukan
                required_columns = ['tanggal', 'waktu', 'latitude', 'longitude', 
                                   'korban_meninggal', 'korban_luka_berat', 
                                   'korban_luka_ringan', 'kerugian_materi', 
                                   'desa', 'kecamatan', 'kabupaten_kota', 'keterangan']
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f'Kolom yang hilang: {", ".join(missing_columns)}')
                    return render(request, 'coreapp/kecelakaan/upload_preprosesing.html', {'form': form})
                
                # Check apakah nomor_kecelakaan ada (opsional)
                has_nomor = 'nomor_kecelakaan' in df.columns
                
                # Import data
                count = 0
                errors = []
                for idx, row in df.iterrows():
                    try:
                        # Parse waktu - handle berbagai format
                        waktu_obj = None
                        if pd.notna(row['waktu']):
                            waktu_val = row['waktu']
                            # Jika sudah dalam format time object
                            if isinstance(waktu_val, type(pd.Timestamp.now().time())):
                                waktu_obj = waktu_val
                            # Jika string
                            elif isinstance(waktu_val, str):
                                try:
                                    waktu_obj = pd.to_datetime(waktu_val).time()
                                except:
                                    raise ValueError(f"Format waktu '{waktu_val}' tidak valid (gunakan HH:MM:SS)")
                            # Jika Timestamp/datetime
                            else:
                                try:
                                    waktu_obj = pd.to_datetime(waktu_val).time()
                                except:
                                    raise ValueError(f"Kolom waktu berisi tanggal bukan jam. Gunakan format HH:MM:SS")
                        
                        # Build create dict with nomor_kecelakaan jika available
                        create_data = {
                            'tanggal': pd.to_datetime(row['tanggal']),
                            'waktu': waktu_obj,
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude']),
                            'korban_meninggal': int(row['korban_meninggal']) if pd.notna(row['korban_meninggal']) else 0,
                            'korban_luka_berat': int(row['korban_luka_berat']) if pd.notna(row['korban_luka_berat']) else 0,
                            'korban_luka_ringan': int(row['korban_luka_ringan']) if pd.notna(row['korban_luka_ringan']) else 0,
                            'kerugian_materi': float(row['kerugian_materi']) if pd.notna(row['kerugian_materi']) else 0,
                            'desa': str(row['desa']) if pd.notna(row['desa']) else '',
                            'kecamatan': str(row['kecamatan']) if pd.notna(row['kecamatan']) else '',
                            'kabupaten_kota': str(row['kabupaten_kota']) if pd.notna(row['kabupaten_kota']) else '',
                            'keterangan': str(row['keterangan']) if pd.notna(row['keterangan']) else ''
                        }
                        
                        # Tambah nomor_kecelakaan jika ada di file
                        if has_nomor and pd.notna(row['nomor_kecelakaan']):
                            create_data['nomor_kecelakaan'] = str(row['nomor_kecelakaan']).strip()
                        
                        KecelakaanPreprosesing.objects.create(**create_data)
                        count += 1
                    except Exception as e:
                        errors.append(f"Baris {idx + 2}: {str(e)}")
                
                if errors and len(errors) <= 10:
                    messages.warning(request, f'Berhasil import {count} data, tapi ada beberapa error:\n' + '\n'.join(errors[:5]))
                else:
                    messages.success(request, f'Berhasil import {count} data kecelakaan preprocessing.')
                
                return redirect('kecelakaan_preprosesing_list')
            except Exception as e:
                messages.error(request, f'Error saat memproses file: {str(e)}')
    else:
        form = UploadKecelakaanPreprosesForm()
    
    return render(request, 'coreapp/kecelakaan/upload_preprosesing.html', {'form': form})


@login_required(login_url='login')
def kecelakaan_preprosesing_list(request):
    """Daftar data kecelakaan preprocessing"""
    kecelakaan = KecelakaanPreprosesing.objects.all()
    
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
        'kecelakaan': kecelakaan[:100],
        'is_admin': is_admin(request.user),
        'tahun_options': range(2020, timezone.now().year + 1),
        'title': 'Data Kecelakaan Preprosesing'
    }
    return render(request, 'coreapp/kecelakaan/list_preprosesing.html', context)

# ===============================
# AHC VIEWS (Imported from utils_ahc.py)
# ===============================
from .utils_ahc import (
    ahc_data, 
    ahc_proses, 
    preprocessing_data, 
    proses_ahc, 
    ahc_hasil, 
    reset_ahc,
    ahc_ai_explain,
    ahc_rekomendasi
)


#profile view
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Profile

@login_required
def profile(request):
    user = request.user

    # 🔥 PASTIKAN PROFILE ADA
    profile, created = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')

        full_name = request.POST.get('full_name').split(" ")
        user.first_name = full_name[0]
        user.last_name = " ".join(full_name[1:])

        user.save()

        profile.alamat = request.POST.get('alamat')

        if request.FILES.get('foto'):
            profile.foto = request.FILES.get('foto')

        profile.save()

        return redirect('profile')

    return render(request, 'profile.html')


# ==========================================
# DATA LAKA MENTAH MANAGEMENT (CLUSTERING RAW DATA)
# ==========================================

@login_required(login_url='login')
def laka_mentah_list(request):
    all_data = LakaMentah.objects.all()
    
    # Pencarian
    search = request.GET.get('search')
    if search:
        all_data = all_data.filter(
            Q(lap_pol__icontains=search) |
            Q(tanggal__icontains=search) |
            Q(tkp__icontains=search) |
            Q(uraian_kejadian__icontains=search)
        )
    
    total_count = all_data.count()
    
    # Hitung duplikasi berdasarkan Nomor Laporan Polisi (LAP. POL) yang tidak kosong
    duplicate_groups = LakaMentah.objects.exclude(lap_pol='').exclude(lap_pol__isnull=True).values(
        'lap_pol'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    jumlah_duplikat = sum(group['count'] - 1 for group in duplicate_groups)

    # Ambil rincian data duplikat untuk modal
    duplicate_data_details = []
    for group in duplicate_groups:
        example = LakaMentah.objects.filter(lap_pol=group['lap_pol']).first()
        if example:
            duplicate_data_details.append({
                'example': example,
                'count': group['count']
            })

    data_list = all_data.order_by('-id')  # data terbaru di atas

    # Paginasi 20 item per halaman
    paginator = Paginator(data_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'data_list': page_obj,
        'total_data': total_count,
        'jumlah_duplikat': jumlah_duplikat,
        'duplicate_data_details': duplicate_data_details,
        'search_query': search or '',
    }
    return render(request, 'coreapp/laka_mentah/list.html', context)


@login_required(login_url='login')
def laka_mentah_tambah(request):
    if request.method == "POST":
        LakaMentah.objects.create(
            tanggal=request.POST.get('tanggal', '').strip(),
            lap_pol=request.POST.get('lap_pol', '').strip(),
            uraian_kejadian=request.POST.get('uraian_kejadian', '').strip(),
            tkp=request.POST.get('tkp', '').strip(),
            terlapor=request.POST.get('terlapor', '').strip(),
            korban=request.POST.get('korban', '').strip(),
            bb=request.POST.get('bb', '').strip(),
            ket=request.POST.get('ket', '').strip()
        )
        messages.success(request, "Data Laka Mentah berhasil ditambahkan secara manual.")
        return redirect('laka_mentah_list')

    return render(request, 'coreapp/laka_mentah/tambah.html')


@login_required(login_url='login')
def laka_mentah_edit(request, pk):
    data = get_object_or_404(LakaMentah, pk=pk)
    
    if request.method == "POST":
        data.tanggal = request.POST.get('tanggal', '').strip()
        data.lap_pol = request.POST.get('lap_pol', '').strip()
        data.uraian_kejadian = request.POST.get('uraian_kejadian', '').strip()
        data.tkp = request.POST.get('tkp', '').strip()
        data.terlapor = request.POST.get('terlapor', '').strip()
        data.korban = request.POST.get('korban', '').strip()
        data.bb = request.POST.get('bb', '').strip()
        data.ket = request.POST.get('ket', '').strip()
        data.save()
        
        messages.success(request, "Data Laka Mentah berhasil diperbarui.")
        return redirect('laka_mentah_list')

    return render(request, 'coreapp/laka_mentah/edit.html', {'data': data})


@login_required(login_url='login')
def laka_mentah_import(request):
    if request.method == "POST":
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Silakan pilih file Excel terlebih dahulu.")
            return redirect('laka_mentah_list')
        
        try:
            # 1. Cari baris header secara dinamis (mencari baris yang mengandung 'LAP. POL' atau 'TANGGAL')
            df_raw = pd.read_excel(file, header=None)
            header_row_idx = None
            for idx, row in df_raw.iterrows():
                row_strs = [str(val).strip().upper() for val in row.values if pd.notna(val)]
                # Periksa kecocokan nama kolom utama
                if any('LAP. POL' in s or 'LAP.POL' in s or 'LAP POL' in s or 'LAPORAN POLISI' in s for s in row_strs):
                    header_row_idx = idx
                    break
            
            # Jika ditemukan, baca ulang file dengan baris header tersebut
            if header_row_idx is not None:
                df = pd.read_excel(file, header=header_row_idx)
            else:
                # Fallback default ke baris ke-6 (0-indexed)
                df = pd.read_excel(file, header=6)
            
            df.columns = df.columns.str.strip()
            
            # 2. Mapping kolom agar sesuai dengan database (case-insensitive & clean)
            col_map = {}
            mapped_targets = set()
            for col in df.columns:
                low = str(col).lower()
                target = None
                if 'tanggal' in low and 'tanggal' not in mapped_targets:
                    target = 'tanggal'
                elif ('lap' in low or 'pol' in low) and 'lap_pol' not in mapped_targets:
                    target = 'lap_pol'
                elif ('uraian' in low or 'kejadian' in low) and 'uraian_kejadian' not in mapped_targets:
                    target = 'uraian_kejadian'
                elif ('tkp' in low or 'lokasi' in low) and 'tkp' not in mapped_targets:
                    target = 'tkp'
                elif 'terlapor' in low and 'terlapor' not in mapped_targets:
                    target = 'terlapor'
                elif 'korban' in low and 'korban' not in mapped_targets:
                    target = 'korban'
                elif ('bb' in low or 'bukti' in low) and 'bb' not in mapped_targets:
                    target = 'bb'
                elif 'ket' in low and 'ket' not in mapped_targets:
                    target = 'ket'
                
                if target:
                    col_map[col] = target
                    mapped_targets.add(target)
            
            df = df.rename(columns=col_map)
            
            # 3. Masukkan data literal baris demi baris secara aman
            count = 0
            for _, row in df.iterrows():
                # Helper untuk mendapatkan nilai tunggal secara aman (mengantisipasi Series duplikat)
                def get_row_value(col_name):
                    val = row.get(col_name)
                    if isinstance(val, pd.Series):
                        non_null = val.dropna()
                        val = non_null.iloc[0] if not non_null.empty else None
                    return val

                tanggal_val = get_row_value('tanggal')
                lap_pol_val = get_row_value('lap_pol')
                tkp_val = get_row_value('tkp')

                # Cek baris kosong atau baris penutup halaman excel
                if (tanggal_val is None or pd.isna(tanggal_val) or str(tanggal_val).strip() == '') and \
                   (lap_pol_val is None or pd.isna(lap_pol_val) or str(lap_pol_val).strip() == '') and \
                   (tkp_val is None or pd.isna(tkp_val) or str(tkp_val).strip() == ''):
                    continue
                
                # Helper untuk membersihkan nilai text/nan
                def clean_val(val):
                    if pd.isna(val) or val is None or str(val).strip().upper() in ['NAN', 'NAT', '-']:
                        return ''
                    return str(val).strip()

                LakaMentah.objects.create(
                    tanggal=clean_val(tanggal_val),
                    lap_pol=clean_val(lap_pol_val),
                    uraian_kejadian=clean_val(get_row_value('uraian_kejadian')),
                    tkp=clean_val(tkp_val),
                    terlapor=clean_val(get_row_value('terlapor')),
                    korban=clean_val(get_row_value('korban')),
                    bb=clean_val(get_row_value('bb')),
                    ket=clean_val(get_row_value('ket'))
                )
                count += 1
            
            messages.success(request, f"Berhasil mengimpor {count} data Laka Mentah secara literal.")
        except Exception as e:
            messages.error(request, f"Gagal mengimpor data: {str(e)}")
            import traceback
            traceback.print_exc()
            
        return redirect('laka_mentah_list')
    
    return redirect('laka_mentah_list')


@login_required(login_url='login')
def laka_mentah_hapus(request, pk):
    LakaMentah.objects.filter(pk=pk).delete()
    messages.success(request, "Data Laka Mentah berhasil dihapus.")
    return redirect('laka_mentah_list')


@login_required(login_url='login')
def laka_mentah_hapus_semua(request):
    LakaMentah.objects.all().delete()
    messages.success(request, "Seluruh data Laka Mentah berhasil dibersihkan.")
    return redirect('laka_mentah_list')


@login_required(login_url='login')
def laka_mentah_hapus_duplikat(request):
    if request.method == "POST":
        duplicate_groups = LakaMentah.objects.exclude(lap_pol='').exclude(lap_pol__isnull=True).values(
            'lap_pol'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        deleted_count = 0
        for group in duplicate_groups:
            ids = list(LakaMentah.objects.filter(lap_pol=group['lap_pol']).values_list('id', flat=True))
            
            # Pertahankan data pertama (ids[0]), hapus selebihnya
            ids_to_delete = ids[1:]
            LakaMentah.objects.filter(id__in=ids_to_delete).delete()
            deleted_count += len(ids_to_delete)
            
        messages.success(request, f"Berhasil membersihkan {deleted_count} data duplikat berdasarkan Nomor Laporan Polisi.")
    return redirect('laka_mentah_list')