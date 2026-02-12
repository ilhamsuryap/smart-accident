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
    
    # API
    path('api/segmen/geojson/', views.api_segmen_geojson, name='api_segmen_geojson'),
    path('api/kecelakaan/geojson/', views.api_kecelakaan_geojson, name='api_kecelakaan_geojson'),
    path('api/analisis/statistik/', views.api_analisis_statistik, name='api_analisis_statistik'),
]
