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

import os
import pandas as pd
from sklearn.cluster import KMeans

from django.conf import settings
from django.shortcuts import render, redirect   
from io import StringIO



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


# Cluster K-Means Views
@login_required(login_url='login')
def cluster_data(request):
    data = Kecelakaan.objects.all()[:50]

    context = {
        'kecelakaan': data
    }

    return render(request, 'coreapp/k-means/data_cluster.html', context)


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
@login_required(login_url='login')
def ahc_data(request):
    return render(request, 'coreapp/ahc/data.html')


# ================================
# HALAMAN PROSES
# ================================
@login_required(login_url='login')
def ahc_proses(request):
    return render(request, 'coreapp/ahc/proses.html')


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

            df = pd.read_excel(file)


            # 🔥 RESET SEMUA SESSION LAMA
            for key in ['hasil_cluster', 'summary_cluster', 'jumlah_cluster', 'jumlah_data', 'silhouette_score']:
                request.session.pop(key, None)

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


            df['Jumlah Kejadian'] = df.get('Jumlah Kejadian', 1).fillna(1)

            if 'Umur' in df.columns:
                df = df[df['Umur'] > 0]

            # Contoh summary
            if 'Umur' in df.columns:
                summary_df = df.groupby('Umur')['Jumlah Kejadian'].sum().reset_index()
            else:
                summary_df = df[['Jumlah Kejadian']]

            # Simpan ke session
            request.session['summary_df'] = summary_df.to_json(orient='records')
            request.session.modified = True

            context['preview'] = summary_df.to_dict(orient='records')

    # =========================
    # 2️⃣ AMBIL DATA DARI SESSION
    # =========================
    summary_json = request.session.get('summary_df')

    if summary_json:
        df = pd.read_json(StringIO(summary_json), orient='records')
        context['preview'] = df.to_dict(orient='records')

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
            df_cluster['Cluster'] = model.labels_

            hasil_cluster = df_cluster.to_dict(orient='records')
            context['hasil_cluster'] = hasil_cluster
            context['k'] = k

    return render(request, 'coreapp/k-means/preprocessing.html', context)
    

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

    # Load dataframe
    df = pd.read_json(StringIO(summary_json), orient='records')

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
        df['Cluster'] = model.fit_predict(X_scaled)

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

    return render(request, 'coreapp/k-means/preprocessing.html', {
        'hasil_cluster': df.to_dict(orient='records'),
        'k': k
    })

@login_required(login_url='login')
def proses_kmeans(request):

    if request.method != "GET":
        return redirect("preprocessing")

    # Ambil hasil preprocessing dari session
    data = request.session.get("processed_data")

    if not data:
        return redirect("preprocessing")

    df = pd.DataFrame(data)

    # Pastikan semua numerik
    df = df.apply(pd.to_numeric, errors='coerce').fillna(0)

    # Ambil fitur (kecuali Umur jika mau dipisah)
    fitur = df.drop(columns=["Umur"], errors="ignore")

    # K-Means dengan 3 cluster
    kmeans = KMeans(n_clusters=3, random_state=42)
    df["Cluster"] = kmeans.fit_predict(fitur)

    # Simpan ke session jika perlu
    request.session["hasil_kmeans"] = df.to_dict(orient="records")

    context = {
        "hasil": df.to_dict(orient="records"),
        "jumlah_cluster": 3
    }

    return render(request, "kmeans/hasil.html", context)

@login_required(login_url='login')
def hasil(request):

    data = request.session.get("summary_df")

    if not data:
        return redirect("preprocessing")

    df = pd.read_json(StringIO(data), orient='records')

    # Ambil fitur numerik kecuali Umur
    fitur = df.select_dtypes(include=['number']).drop(columns=['Umur'], errors='ignore')

    # KMeans 3 cluster
    model = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['Cluster'] = model.fit_predict(fitur) + 1   # mulai dari 1

    context = {
        "hasil_cluster": df.to_dict(orient='records'),
        "k": 3
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
    request.session['X_scaled'] = X_scaled.tolist()
    request.session['summary_df'] = summary_df.to_dict(orient='records')

    context['preview'] = summary_df.to_dict(orient='records')
    context['jumlah_data'] = len(summary_df)
    context['jumlah_data_asli'] = request.session.get('jumlah_data_asli')

    return render(request, 'coreapp/ahc/proses.html', context)


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
def hasil_ahc(request):
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

