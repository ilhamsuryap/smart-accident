#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartAccident.settings')
django.setup()

from django.test import RequestFactory
from coreapp.views import api_segmen_geojson
import json

print("\n" + "="*80)
print("TESTING ACTUAL API ENDPOINT")
print("="*80)

# Create a fake request
factory = RequestFactory()
request = factory.get('/api/segmen/geojson/?tahun=2026')

# Call the view
response = api_segmen_geojson(request)
data = response.data

print(f"\nTotal features: {len(data.get('features', []))}")

# Check first few features
for i, feature in enumerate(data.get('features', [])[:6]):
    print(f"\n--- Feature {i+1} ---")
    props = feature.get('properties', {})
    geom = feature.get('geometry', {})
    
    print(f"Type: {props.get('type')}")
    print(f"ID: {props.get('segmen_id')}")
    print(f"Geometry type: {geom.get('type')}")
    
    if geom.get('type') == 'LineString':
        print(f"✓ LineString with {len(geom.get('coordinates', []))} points")
    elif geom.get('type') == 'Point':
        print(f"✓ Point at {geom.get('coordinates')}")
    else:
        print(f"Coordinates: {geom.get('coordinates')}")

print("\n" + "="*80)
print("API TEST COMPLETE")
print("="*80 + "\n")
