import requests
import json

try:
    response = requests.get('http://127.0.0.1:5001/api/projects')
    if response.status_code == 200:
        data = response.json()
        print("Success:", data['success'])
        if data['success']:
            projects = data['projects']
            print(f"Found {len(projects)} projects")
            if projects:
                p = projects[0]
                print(f"Project: {p['name']}")
                datasets = p.get('datasets', {})
                print("Datasets keys:", datasets.keys())
                print(f"Trainable count: {len(datasets.get('trainable', []))}")
                print(f"Annotatable count: {len(datasets.get('annotatable', []))}")
    else:
        print(f"Failed with status {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
