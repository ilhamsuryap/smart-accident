#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from django.test import RequestFactory
from coreapp.views import api_segmen_geojson
import json

print("\n" + "="*80)
print("TESTING API RESPONSE WITH PER-RUAS Z-SCORE")
print("="*80 + "\n")

# Create a fake request
factory = RequestFactory()
request = factory.get('/api/segmen/geojson/?tahun=2026')

# Call the view
response = api_segmen_geojson(request)
data = response.data

print(f"Total features: {len(data.get('features', []))}\n")

# Group by ruas jalan
by_ruas = {}
for feature in data.get('features', []):
    if feature.get('properties', {}).get('type') == 'line':
        props = feature.get('properties', {})
        ruas = props.get('ruas_nama')
        
        if ruas not in by_ruas:
            by_ruas[ruas] = []
        
        by_ruas[ruas].append({
            'segmen': props.get('nama_segmen'),
            'kategori': props.get('kategori'),
            'zscore': props.get('zscore'),
            'color': props.get('color'),
            'accidents': props.get('accident_count')
        })

# Display grouped by ruas
for ruas, segments in sorted(by_ruas.items()):
    print(f"🛣️ {ruas}")
    for seg in segments:
        print(f"   {seg['segmen']}: {seg['accidents']} accidents → Z={seg['zscore']:.3f} ({seg['kategori']}) {seg['color']}")
    print()

print("="*80)
