#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# Login as Admin first to check trainings
print("Logging in as Admin...")
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": "support@starline.com", "password": "Admin123!!"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()["access_token"]
print(f"✓ Logged in successfully")

# Get training courses
print("\nFetching training courses...")
courses_response = requests.get(
    f"{BASE_URL}/training/courses",
    headers={"Authorization": f"Bearer {token}"}
)

if courses_response.status_code == 200:
    data = courses_response.json()
    print(f"✓ Found {len(data['courses'])} courses\n")

    for item in data['courses']:
        course = item['course']
        progress = item.get('progress')

        print(f"Course: {course['title']}")
        print(f"  Status: {progress['status'] if progress else 'not_started'}")
        if progress:
            print(f"  Completed: {progress['completed_at']}")
            print(f"  Acknowledged: {progress['acknowledged_at']}")
            print(f"  Cert Expires: {progress['certification_expires_at']}")
            print(f"  Progress ID: {progress['id']}")
        print()
else:
    print(f"Failed to get courses: {courses_response.status_code}")
    print(courses_response.text)
