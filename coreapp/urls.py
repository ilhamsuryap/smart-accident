from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Ruas Jalan
    path('ruas-jalan/', views.ruas_jalan_list, name='ruas_jalan_list'),
    path('ruas-jalan/create/', views.ruas_jalan_create, name='ruas_jalan_create'),
    path('ruas-jalan/<int:pk>/', views.ruas_jalan_detail, name='ruas_jalan_detail'),
    path('ruas-jalan/<int:pk>/update/', views.ruas_jalan_update, name='ruas_jalan_update'),
    path('ruas-jalan/<int:pk>/delete/', views.ruas_jalan_delete, name='ruas_jalan_delete'),
    path('ruas-jalan/<int:pk>/generate-segmen/', views.generate_segmen, name='generate_segmen'),
    
    # Kecelakaan
    path('kecelakaan/', views.kecelakaan_list, name='kecelakaan_list'),
    path('kecelakaan/create/', views.kecelakaan_create, name='kecelakaan_create'),
    path('kecelakaan/<int:pk>/', views.kecelakaan_detail, name='kecelakaan_detail'),
    path('kecelakaan/<int:pk>/update/', views.kecelakaan_update, name='kecelakaan_update'),
    path('kecelakaan/<int:pk>/delete/', views.kecelakaan_delete, name='kecelakaan_delete'),
    path('kecelakaan/segmen/<int:segmen_id>/', views.segmen_kecelakaan_detail, name='segmen_kecelakaan_detail'),
    
    # Analisis
    path('analisis/', views.analisis_view, name='analisis'),
    
    # Map 
    path('peta/', views.map_view, name='map'),

    # ================= KMEANS =================
    path('kmeans/data/', views.kmeans_data, name='kmeans_data'),
    path('kmeans/proses/', views.kmeans_proses, name='kmeans_proses'),
    path('kmeans/hasil/', views.kmeans_hasil, name='kmeans_hasil'),

    # ================= AHC =================   

    # AHC URLS
    path('ahc/data/', views.ahc_data, name='ahc_data'),
    path('ahc/proses/', views.ahc_proses, name='ahc_proses'),
    path('ahc/preprocessing/', views.preprocessing_data, name='preprocessing_data'),
    path('ahc/hasil/', views.ahc_hasil, name='ahc_hasil'),
    path('proses-ahc/', views.proses_ahc, name='proses_ahc'),
    path('ahc/reset/', views.reset_ahc, name='reset_ahc'),
  

    
    # Cluster K-Means
    path('k-means/data_cluster/', views.cluster_data, name='cluster_data'),
    path('k-means/tambah/', views.tambah_data, name='tambah_data'),
    # path('k-means/hasil/', views.hasil_cluster, name='hasil_cluster'),
    path('k-means/preprocessing/', views.preprocessing, name='preprocessing'),
    path('k-means/hasil/', views.hasil, name='hasil'),
    path('k-means/reset/', views.reset_k_means, name='reset_k_means'),

    # path('tambah-data/', views.tambah_data, name='tambah_data'),
    path('ajax/load-kecamatan/', views.load_kecamatan, name='ajax_load_kecamatan'),
    path('ajax/load-kelurahan/', views.load_kelurahan, name='ajax_load_kelurahan'),


    # API
    path('api/segmen/geojson/', views.api_segmen_geojson, name='api_segmen_geojson'),
    path('api/kecelakaan/geojson/', views.api_kecelakaan_geojson, name='api_kecelakaan_geojson'),
    path('api/analisis/statistik/', views.api_analisis_statistik, name='api_analisis_statistik'),
    
    # Geoapify API
    path('api/geoapify/routing/', views.api_geoapify_routing, name='api_geoapify_routing'),
    path('api/geoapify/reverse-geocoding/', views.api_geoapify_reverse_geocoding, name='api_geoapify_reverse_geocoding'),
]
