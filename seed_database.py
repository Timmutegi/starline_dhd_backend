#!/usr/bin/env python3
"""
Database Seeding Script for Starline Backend
Creates sample clients, staff, and assignments using API endpoints
"""

import os
import sys
import requests
import json
from datetime import date, timedelta, datetime, timezone
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEV").upper()
BASE_URL = "http://localhost:8000/api/v1" if ENVIRONMENT in ["DEV", "DEVELOPMENT"] else "http://localhost/api/v1"

# Admin credentials from .env
ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "support@starline.com")
ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!!")

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(message: str):
    """Print a header message"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.OKCYAN}ℹ {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def login() -> tuple[Optional[str], Optional[Dict]]:
    """Login and get access token and user data"""
    print_info(f"Logging in as {ADMIN_EMAIL}...")

    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "remember_me": False
            },
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            user = data['user']
            full_name = f"{user['first_name']} {user['last_name']}"
            print_success(f"Logged in successfully as {full_name}")
            return data["access_token"], user
        else:
            print_error(f"Login failed: {response.status_code} - {response.text}")
            return None, None

    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return None, None


def create_client(token: str, client_data: Dict) -> Optional[Dict]:
    """Create a client using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/clients/",
            json=client_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code in [200, 201]:
            result = response.json()
            client = result["client"]
            temp_password = result["temporary_password"]
            username = result["username"]

            print_success(f"Created client: {client['full_name']} (ID: {client['client_id']})")
            print_info(f"  → Username: {username}")
            print_info(f"  → Temporary password: {temp_password}")

            # Add password info to client dict for later use
            client['temporary_password'] = temp_password
            client['username'] = username

            return client
        else:
            print_error(f"Failed to create client {client_data['first_name']}: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating client {client_data['first_name']}: {str(e)}")
        return None


def create_staff(token: str, staff_data: Dict) -> Optional[Dict]:
    """Create a staff member using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/staff/",
            json=staff_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code == 200:
            result = response.json()
            staff = result["staff"]
            temp_password = result["temporary_password"]

            print_success(f"Created staff: {staff['full_name']} (Employee ID: {staff['employee_id']})")
            print_info(f"  → Username: {staff['user']['username']}")
            print_info(f"  → Temporary password: {temp_password}")

            # Add password info to staff dict for later use
            staff['temporary_password'] = temp_password

            return staff
        else:
            print_error(f"Failed to create staff {staff_data['first_name']}: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating staff {staff_data['first_name']}: {str(e)}")
        return None


def assign_staff_to_client(token: str, staff_id: str, client_id: str, assignment_data: Dict) -> Optional[Dict]:
    """Assign a staff member to a client"""
    try:
        response = requests.post(
            f"{BASE_URL}/staff/{staff_id}/assignments",
            json=assignment_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code in [200, 201]:
            assignment = response.json()
            print_success(f"Assigned staff to client (Assignment ID: {assignment['id']})")
            return assignment
        else:
            print_error(f"Failed to assign staff to client: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error assigning staff to client: {str(e)}")
        return None


def get_roles(token: str) -> Optional[list]:
    """Get available roles"""
    try:
        response = requests.get(
            f"{BASE_URL}/roles/",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_warning(f"Could not fetch roles: {response.status_code}")
            return None

    except Exception as e:
        print_warning(f"Error fetching roles: {str(e)}")
        return None


def create_manager(token: str, manager_data: Dict) -> Optional[Dict]:
    """Create a manager user using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/users/",
            json=manager_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code in [200, 201]:
            result = response.json()
            manager = result.get("user", result)
            temp_password = result.get("temporary_password", "Admin123!!")

            print_success(f"Created manager: {manager['first_name']} {manager['last_name']}")
            print_info(f"  → Username: {manager.get('username', manager.get('email'))}")
            print_info(f"  → Email: {manager['email']}")
            print_info(f"  → Temporary password: {temp_password}")

            # Add password info to manager dict for later use
            manager['temporary_password'] = temp_password

            return manager
        else:
            print_error(f"Failed to create manager {manager_data['first_name']}: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating manager {manager_data['first_name']}: {str(e)}")
        return None


def create_task(token: str, task_data: Dict) -> Optional[Dict]:
    """Create a task using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/tasks/",
            json=task_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_vitals_log(token: str, vitals_data: Dict) -> Optional[Dict]:
    """Create a vitals log using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/documentation/vitals",
            json=vitals_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_shift_note(token: str, note_data: Dict) -> Optional[Dict]:
    """Create a shift note using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/documentation/shift-notes",
            json=note_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_meal_log(token: str, meal_data: Dict) -> Optional[Dict]:
    """Create a meal log using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/documentation/meals",
            json=meal_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_incident_report(token: str, incident_data: Dict) -> Optional[Dict]:
    """Create an incident report using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/documentation/incidents",
            data=incident_data,
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_location(token: str, location_data: Dict) -> Optional[Dict]:
    """Create a location using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/clients/locations",
            json=location_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to create location: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating location: {str(e)}")
        return None


def assign_client_to_location(token: str, client_id: str, assignment_data: Dict) -> Optional[Dict]:
    """Assign a client to a location"""
    try:
        response = requests.post(
            f"{BASE_URL}/clients/{client_id}/assignments",
            json=assignment_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to assign client to location: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error assigning client to location: {str(e)}")
        return None


def create_schedule(token: str, schedule_data: Dict, org_id: str) -> Optional[Dict]:
    """Create a schedule using the API"""
    try:
        # Add organization_id to schedule data
        schedule_data["organization_id"] = org_id

        response = requests.post(
            f"{BASE_URL}/scheduling/schedules",
            json=schedule_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to create schedule: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating schedule: {str(e)}")
        return None


def create_shift(token: str, shift_data: Dict) -> Optional[Dict]:
    """Create a shift using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/scheduling/shifts",
            json=shift_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to create shift: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating shift: {str(e)}")
        return None


def clock_in(token: str, shift_id: str) -> Optional[Dict]:
    """Clock in for a shift"""
    try:
        response = requests.post(
            f"{BASE_URL}/scheduling/time-clock/clock-in",
            json={"shift_id": shift_id},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            return None

    except Exception as e:
        return None


def create_notification(token: str, notification_data: Dict) -> Optional[Dict]:
    """Create a notification using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/notifications/create",
            json=notification_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to create notification: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating notification: {str(e)}")
        return None


def create_appointment(token: str, appointment_data: Dict) -> Optional[Dict]:
    """Create an appointment using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/scheduling/appointments",
            json=appointment_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print_error(f"Failed to create appointment: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Error creating appointment: {str(e)}")
        return None


def seed_training_courses(token: str, org_id: str, admin_user_id: str, tim_user_id: str):
    """Seed training courses and progress for tim@kaziflex.com"""
    print_header("SEEDING TRAINING COURSES")

    courses_data = [
        {
            "title": "HIPAA Compliance Training",
            "description": "Comprehensive training on HIPAA regulations and patient privacy",
            "course_type": "video",
            "duration_minutes": 45,
            "is_required": True,
            "passing_score": 80,
            "provides_certification": True,
            "certification_valid_days": 365,
            "status": "active"
        },
        {
            "title": "Emergency Response Procedures",
            "description": "Learn how to respond to medical emergencies and safety protocols",
            "course_type": "interactive",
            "duration_minutes": 30,
            "is_required": True,
            "passing_score": 85,
            "provides_certification": True,
            "certification_valid_days": 180,
            "status": "active"
        },
        {
            "title": "Medication Administration Safety",
            "description": "Safe medication administration practices and documentation",
            "course_type": "document",
            "duration_minutes": 20,
            "is_required": True,
            "passing_score": 90,
            "provides_certification": True,
            "certification_valid_days": 180,
            "status": "active"
        },
        {
            "title": "Client Communication Best Practices",
            "description": "Effective communication strategies for working with clients",
            "course_type": "video",
            "duration_minutes": 35,
            "is_required": False,
            "passing_score": 75,
            "provides_certification": True,
            "certification_valid_days": 365,
            "status": "active"
        }
    ]

    created_courses = []

    try:
        for course_data in courses_data:
            response = requests.post(
                f"{BASE_URL}/training/courses",
                headers={"Authorization": f"Bearer {token}"},
                json=course_data
            )

            if response.status_code in [200, 201]:
                course = response.json()
                created_courses.append(course)
                print_success(f"Created course: {course_data['title']}")
            else:
                print_error(f"Failed to create course {course_data['title']}: {response.status_code}")

        # Now create progress for Tim
        if created_courses:
            print_info(f"\nCreating training progress for Tim...")

            # Course 1: HIPAA - Completed AND Acknowledged (VALID state)
            if len(created_courses) > 0:
                course_id = created_courses[0]['id']
                requests.post(
                    f"{BASE_URL}/training/courses/{course_id}/start",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response = requests.post(
                    f"{BASE_URL}/training/courses/{course_id}/complete",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"quiz_score": 95}
                )
                if response.status_code == 200:
                    # Get the progress ID and acknowledge it
                    progress_response = requests.get(
                        f"{BASE_URL}/training/progress",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if progress_response.status_code == 200:
                        progress_records = progress_response.json()
                        for prog in progress_records:
                            if prog['course_id'] == course_id:
                                ack_response = requests.post(
                                    f"{BASE_URL}/training/progress/{prog['id']}/acknowledge",
                                    headers={"Authorization": f"Bearer {token}"}
                                )
                                if ack_response.status_code == 200:
                                    print_success(f"  ✓ Valid: HIPAA Compliance Training (95%, Acknowledged)")
                                break

            # Course 2: Emergency Response - In Progress (65%) - NOT TAKEN state
            if len(created_courses) > 1:
                course_id = created_courses[1]['id']
                requests.post(
                    f"{BASE_URL}/training/courses/{course_id}/start",
                    headers={"Authorization": f"Bearer {token}"}
                )
                # Update progress to 65%
                progress_response = requests.get(
                    f"{BASE_URL}/training/progress",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if progress_response.status_code == 200:
                    progress_records = progress_response.json()
                    for prog in progress_records:
                        if prog['course_id'] == course_id:
                            requests.put(
                                f"{BASE_URL}/training/progress/{prog['id']}",
                                headers={"Authorization": f"Bearer {token}"},
                                json={"progress_percentage": 65, "status": "in_progress"}
                            )
                            print_success(f"  ⏳ Not Taken: Emergency Response Procedures (65% In Progress)")
                            break

            # Course 3: Medication Safety - Not Started - NOT TAKEN state
            if len(created_courses) > 2:
                print_success(f"  📝 Not Taken: Medication Administration Safety (Not Started)")

            # Course 4: Communication - Completed but NOT Acknowledged - PENDING ACKNOWLEDGMENT state
            if len(created_courses) > 3:
                course_id = created_courses[3]['id']
                requests.post(
                    f"{BASE_URL}/training/courses/{course_id}/start",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response = requests.post(
                    f"{BASE_URL}/training/courses/{course_id}/complete",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"quiz_score": 88}
                )
                if response.status_code == 200:
                    print_success(f"  ⚠️  Pending Acknowledgment: Client Communication Best Practices (88%, Not Acknowledged)")

        return created_courses

    except Exception as e:
        print_error(f"Error seeding training courses: {str(e)}")
        return []


def seed_notices(token: str, org_id: str, admin_user_id: str):
    """Seed notices/announcements"""
    print_header("SEEDING NOTICES")

    notices_data = [
        {
            "title": "Updated Safety Protocols",
            "content": "Please review the updated safety protocols in the training portal. All staff must acknowledge receipt by end of week.",
            "summary": "New safety protocols require review and acknowledgment",
            "priority": "high",
            "category": "safety",
            "is_active": True,
            "publish_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "requires_acknowledgment": True
        },
        {
            "title": "New Client Assignment System",
            "content": "We have implemented a new client assignment system. Please familiarize yourself with the updated dashboard and assignment workflow.",
            "summary": "Updated client assignment system launched",
            "priority": "medium",
            "category": "system",
            "is_active": True,
            "publish_date": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            "requires_acknowledgment": False
        },
        {
            "title": "Staff Meeting Reminder",
            "content": "Monthly staff meeting scheduled for Friday at 2 PM in Conference Room A. Agenda includes policy updates and training requirements.",
            "summary": "Monthly staff meeting - Friday 2 PM",
            "priority": "low",
            "category": "general",
            "is_active": True,
            "publish_date": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "requires_acknowledgment": False
        },
        {
            "title": "Emergency Preparedness Training",
            "content": "Mandatory emergency preparedness training session next week. Please complete the online module before attending.",
            "summary": "Mandatory emergency training next week",
            "priority": "high",
            "category": "training",
            "is_active": True,
            "publish_date": datetime.now(timezone.utc).isoformat(),
            "requires_acknowledgment": True
        },
        {
            "title": "Updated Documentation Requirements",
            "content": "New documentation requirements are now in effect. All activity logs must include detailed observations and client responses.",
            "summary": "Enhanced documentation requirements",
            "priority": "medium",
            "category": "policy",
            "is_active": True,
            "publish_date": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "requires_acknowledgment": True
        }
    ]

    created_notices = []

    try:
        for notice_data in notices_data:
            response = requests.post(
                f"{BASE_URL}/notices",
                headers={"Authorization": f"Bearer {token}"},
                json=notice_data
            )

            if response.status_code in [200, 201]:
                notice = response.json()
                created_notices.append(notice)
                priority_emoji = "🔴" if notice_data['priority'] == 'high' else "🟡" if notice_data['priority'] == 'medium' else "🟢"
                print_success(f"Created notice: {priority_emoji} {notice_data['title']}")
            else:
                print_error(f"Failed to create notice {notice_data['title']}: {response.status_code}")

        # Mark some notices as read for Tim (simulate history)
        if len(created_notices) >= 2:
            print_info(f"\nMarking some notices as read for Tim...")
            # Mark notice 2 and 3 as read
            for i in [1, 2]:
                if i < len(created_notices):
                    notice_id = created_notices[i]['id']
                    requests.post(
                        f"{BASE_URL}/notices/{notice_id}/read",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    print_success(f"  ✓ Marked as read: {created_notices[i]['title']}")

        return created_notices

    except Exception as e:
        print_error(f"Error seeding notices: {str(e)}")
        return []


def seed_activities(token: str, clients: list, staff_member: dict):
    """Seed activity logs for clients"""
    print_header("SEEDING ACTIVITIES")

    if not clients or not staff_member:
        print_warning("No clients or staff member found. Skipping activities.")
        return []

    activities_data = []

    # Activity for each client
    activity_templates = [
        {
            "activity_type": "therapeutic",
            "activity_name": "Physical Therapy Session",
            "activity_description": "Upper body strength exercises and mobility training",
            "location": "Therapy Room",
            "location_type": "facility",
            "participation_level": "full",
            "independence_level": "supervised",
            "mood_during": "content",
            "activity_completed": True,
            "completion_percentage": 100,
            "start_time": "09:00 AM",
            "end_time": "10:00 AM",
            "duration_minutes": 60
        },
        {
            "activity_type": "therapeutic",
            "activity_name": "Occupational Therapy",
            "activity_description": "Fine motor skills practice and daily living activities",
            "location": "OT Room",
            "location_type": "facility",
            "participation_level": "full",
            "independence_level": "assisted",
            "mood_during": "happy",
            "activity_completed": True,
            "completion_percentage": 100,
            "start_time": "10:30 AM",
            "end_time": "11:30 AM",
            "duration_minutes": 60
        },
        {
            "activity_type": "exercise",
            "activity_name": "Group Exercise Class",
            "activity_description": "Low-impact aerobics and stretching exercises",
            "location": "Activity Center",
            "location_type": "facility",
            "participation_level": "partial",
            "independence_level": "supervised",
            "mood_during": "content",
            "activity_completed": False,
            "completion_percentage": 60,
            "start_time": "02:00 PM",
            "end_time": "03:00 PM",
            "duration_minutes": 60
        },
        {
            "activity_type": "social",
            "activity_name": "Music Therapy",
            "activity_description": "Group music session with singing and instrument playing",
            "location": "Community Room",
            "location_type": "facility",
            "participation_level": "full",
            "independence_level": "independent",
            "mood_during": "happy",
            "activity_completed": True,
            "completion_percentage": 100,
            "start_time": "03:30 PM",
            "end_time": "04:30 PM",
            "duration_minutes": 60
        }
    ]

    created_activities = []

    try:
        today = datetime.now(timezone.utc)

        # Create activities for each client
        for i, client in enumerate(clients[:4]):  # First 4 clients
            if i < len(activity_templates):
                activity_data = activity_templates[i].copy()
                activity_data['client_id'] = client['id']
                activity_data['activity_date'] = today.isoformat()

                response = requests.post(
                    f"{BASE_URL}/documentation/activities",
                    headers={"Authorization": f"Bearer {token}"},
                    json=activity_data
                )

                if response.status_code in [200, 201]:
                    activity = response.json()
                    created_activities.append(activity)
                    status = "✓" if activity_data['activity_completed'] else "⏳"
                    print_success(f"{status} Created: {activity_data['activity_name']} for {client['first_name']} {client['last_name']}")
                else:
                    print_error(f"Failed to create activity: {response.status_code}")

        # Create some past activities for history
        print_info(f"\nCreating historical activities...")
        for client in clients[:2]:
            past_activity = {
                "client_id": client['id'],
                "activity_type": "recreational",
                "activity_name": "Arts and Crafts",
                "activity_description": "Painting and drawing session",
                "activity_date": (today - timedelta(days=1)).isoformat(),
                "start_time": "02:00 PM",
                "end_time": "03:30 PM",
                "duration_minutes": 90,
                "location": "Art Studio",
                "location_type": "facility",
                "participation_level": "full",
                "independence_level": "supervised",
                "mood_during": "happy",
                "activity_completed": True,
                "completion_percentage": 100
            }

            response = requests.post(
                f"{BASE_URL}/documentation/activities",
                headers={"Authorization": f"Bearer {token}"},
                json=past_activity
            )

            if response.status_code == 201:
                print_success(f"  ✓ Historical: Arts and Crafts for {client['first_name']}")

        return created_activities

    except Exception as e:
        print_error(f"Error seeding activities: {str(e)}")
        return []


def main():
    """Main seeding function"""
    print_header("STARLINE DATABASE SEEDING SCRIPT")

    print_info(f"Environment: {ENVIRONMENT}")
    print_info(f"Base URL: {BASE_URL}")
    print()

    # Login
    token, admin_user = login()
    if not token or not admin_user:
        print_error("Failed to login. Exiting...")
        sys.exit(1)

    # Get admin user info from login response
    admin_user_id = admin_user.get('id')
    org_id = admin_user.get('organization_id')

    if not admin_user_id or not org_id:
        print_error("Failed to get admin user info from login response. Exiting...")
        sys.exit(1)

    print_success(f"Admin User ID: {admin_user_id}")
    print_success(f"Organization ID: {org_id}")

    # Get roles
    print_info("\nFetching available roles...")
    roles = get_roles(token)

    # Find Support Staff role for clients and staff
    support_staff_role_id = None
    if roles:
        for role in roles:
            if role["name"] == "Support Staff":
                support_staff_role_id = role["id"]
                print_success(f"Found 'Support Staff' role: {support_staff_role_id}")
                break

    if not support_staff_role_id:
        print_warning("Could not find 'Support Staff' role. Using default behavior...")

    # Find Manager role
    manager_role_id = None
    if roles:
        for role in roles:
            if role["name"].lower() == "manager":
                manager_role_id = role["id"]
                print_success(f"Found 'Manager' role: {manager_role_id}")
                break

    if not manager_role_id:
        print_warning("Could not find 'Manager' role. Skipping manager creation...")

    # Create manager users
    print_header("CREATING MANAGER USERS")

    managers = []
    if manager_role_id:
        managers_data = [
            {
                "email": "manager1@kaziflex.com",
                "username": "manager1",
                "first_name": "Sarah",
                "last_name": "Thompson",
                "phone": "+1-555-0201",
                "role_id": manager_role_id,
                "password": "Manager123!!",
                "must_change_password": False
            },
            {
                "email": "manager2@kaziflex.com",
                "username": "manager2",
                "first_name": "Michael",
                "last_name": "Rodriguez",
                "phone": "+1-555-0202",
                "role_id": manager_role_id,
                "password": "Manager123!!",
                "must_change_password": False
            }
        ]

        for manager_data in managers_data:
            manager = create_manager(token, manager_data)
            if manager:
                managers.append(manager)

        if managers:
            print_success(f"\nCreated {len(managers)} manager users successfully!")
        else:
            print_warning("No managers were created")
    else:
        print_info("Skipping manager creation - role not found")

    # Create 4 clients
    print_header("CREATING CLIENTS")

    clients_data = [
        {
            "first_name": "Cynthia",
            "last_name": "Wanza",
            "email": "wanza@kaziflex.com",
            "date_of_birth": "1985-03-15",
            "gender": "male",
            "primary_diagnosis": "Autism Spectrum Disorder",
            "allergies": ["Peanuts", "Penicillin"],
            "dietary_restrictions": ["Gluten-free"],
            "admission_date": str(date.today() - timedelta(days=365)),
            "send_credentials": False
        },
        {
            "first_name": "Sharon",
            "last_name": "Smith",
            "email": "sharon@kaziflex.com",
            "date_of_birth": "1990-07-22",
            "gender": "female",
            "primary_diagnosis": "Down Syndrome",
            "allergies": ["Latex"],
            "admission_date": str(date.today() - timedelta(days=180)),
            "send_credentials": False
        },
        {
            "first_name": "David",
            "last_name": "Johnson",
            "email": "davy@kaziflex.com",
            "date_of_birth": "1988-11-08",
            "gender": "male",
            "primary_diagnosis": "Cerebral Palsy",
            "secondary_diagnoses": ["Epilepsy"],
            "dietary_restrictions": ["Low sodium"],
            "admission_date": str(date.today() - timedelta(days=90)),
            "send_credentials": False
        },
        {
            "first_name": "Shirleen",
            "last_name": "Davis",
            "email": "shirleen@kaziflex.com",
            "date_of_birth": "1995-05-30",
            "gender": "female",
            "preferred_name": "Em",
            "primary_diagnosis": "Intellectual Disability",
            "allergies": ["Shellfish"],
            "admission_date": str(date.today() - timedelta(days=30)),
            "send_credentials": False
        }
    ]

    clients = []
    for client_data in clients_data:
        client = create_client(token, client_data)
        if client:
            clients.append(client)

    if not clients:
        print_error("No clients were created. Exiting...")
        sys.exit(1)

    print_success(f"\nCreated {len(clients)} clients successfully!")

    # Create 5 staff members
    print_header("CREATING STAFF MEMBERS")

    staff_data_list = [
        {
            "first_name": "Timothy",
            "last_name": "Williams",
            "email": "tim@kaziflex.com",
            "phone": "+1-555-0101",
            "employee_id": "SP001",
            "hire_date": str(date.today() - timedelta(days=730)),
            "department": "Direct Care",
            "job_title": "Senior Care Provider",
            "pay_type": "hourly",
            "hourly_rate": "22.50",
            "role_id": support_staff_role_id,
            "use_custom_permissions": False
        },
    ]

    staff_members = []
    for staff_data in staff_data_list:
        staff = create_staff(token, staff_data)
        if staff:
            staff_members.append(staff)

    if not staff_members:
        print_error("No staff members were created. Exiting...")
        sys.exit(1)

    print_success(f"\nCreated {len(staff_members)} staff members successfully!")

    # Assign first staff member (tim@kaziflex.com) to ALL clients
    print_header("CREATING STAFF ASSIGNMENTS")

    assignments = []
    if len(staff_members) > 0 and len(clients) > 0:
        tim_staff = staff_members[0]  # tim@kaziflex.com

        # Assign tim to all 4 clients
        for i, client in enumerate(clients):
            assignment_type = "primary" if i == 0 else "secondary"
            assignment_data = {
                "client_id": client["id"],
                "assignment_type": assignment_type,
                "start_date": str(date.today() - timedelta(days=30 * i)),  # Stagger start dates
                "notes": f"{'Primary' if i == 0 else 'Secondary'} care provider for {client['full_name']}"
            }

            print_info(f"Assigning {tim_staff['full_name']} to {client['full_name']}...")
            assignment = assign_staff_to_client(
                token,
                tim_staff["id"],
                client["id"],
                assignment_data
            )

            if assignment:
                assignments.append(assignment)
                print_success(f"  ✓ Assigned to {client['full_name']}")
            else:
                print_error(f"  ✗ Failed to assign to {client['full_name']}")

    print_success(f"\nCreated {len(assignments)} staff assignments")

    # Create Tasks
    print_header("CREATING TASKS")

    tasks = []
    if len(clients) > 0 and len(staff_members) > 0:
        tasks_data = [
            {
                "client_id": clients[0]["id"],
                "title": "Complete medication administration training",
                "description": "Review medication protocols and complete certification",
                "priority": "high",
                "due_date": str(date.today() + timedelta(days=7))
            },
            {
                "client_id": clients[0]["id"],
                "title": "Update care plan documentation",
                "description": "Review and update quarterly care plan",
                "priority": "medium",
                "due_date": str(date.today() + timedelta(days=14))
            },
            {
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "title": "Schedule dental appointment",
                "description": "Coordinate with dental office for routine checkup",
                "priority": "medium",
                "due_date": str(date.today() + timedelta(days=10))
            }
        ]

        for task_data in tasks_data:
            task = create_task(token, task_data)
            if task:
                tasks.append(task)
                print_success(f"Created task: {task_data['title']}")

    print_success(f"\nCreated {len(tasks)} tasks")

    # Create Vitals Logs
    print_header("CREATING VITALS LOGS")

    vitals_logs = []
    if len(clients) > 0:
        vitals_data_list = [
            {
                "client_id": clients[0]["id"],
                "temperature": 98.6,
                "blood_pressure_systolic": 120,
                "blood_pressure_diastolic": 80,
                "blood_sugar": 95.0,
                "weight": 165.5,
                "heart_rate": 72,
                "oxygen_saturation": 98.0,
                "notes": "All vitals within normal range"
            },
            {
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "temperature": 97.8,
                "blood_pressure_systolic": 118,
                "blood_pressure_diastolic": 76,
                "heart_rate": 68,
                "oxygen_saturation": 99.0,
                "notes": "Client resting comfortably"
            }
        ]

        for vitals_data in vitals_data_list:
            vitals = create_vitals_log(token, vitals_data)
            if vitals:
                vitals_logs.append(vitals)
                print_success(f"Created vitals log for client")

    print_success(f"\nCreated {len(vitals_logs)} vitals logs")

    # Create Shift Notes
    print_header("CREATING SHIFT NOTES")

    shift_notes = []
    if len(clients) > 0:
        shift_notes_data = [
            {
                "client_id": clients[0]["id"],
                "shift_date": str(date.today()),
                "shift_time": "8:00 AM - 4:00 PM",
                "narrative": "Client was cooperative throughout the shift. Participated in all scheduled activities. Maintained good hygiene and followed daily routine.",
                "challenges_faced": "Minor difficulty with medication compliance at lunch time",
                "support_required": "Continued reminders for medication schedule",
                "observations": "Overall positive mood and good engagement with peers"
            },
            {
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "shift_date": str(date.today() - timedelta(days=1)),
                "shift_time": "8:00 AM - 4:00 PM",
                "narrative": "Client had a productive day with full participation in activities. Enjoyed outdoor recreation time.",
                "observations": "Demonstrated improved social interaction skills"
            }
        ]

        for note_data in shift_notes_data:
            note = create_shift_note(token, note_data)
            if note:
                shift_notes.append(note)
                print_success(f"Created shift note for {note_data['shift_date']}")

    print_success(f"\nCreated {len(shift_notes)} shift notes")

    # Create Meal Logs
    print_header("CREATING MEAL LOGS")

    meal_logs = []
    if len(clients) > 0:
        meal_logs_data = [
            {
                "client_id": clients[0]["id"],
                "meal_type": "breakfast",
                "meal_time": "08:00 AM",
                "food_items": ["Oatmeal", "Orange juice", "Toast", "Scrambled eggs"],
                "intake_amount": "most",
                "percentage_consumed": 85,
                "calories": 450.0,
                "water_intake_ml": 240,
                "appetite_level": "good",
                "dietary_preferences_followed": True,
                "dietary_restrictions_followed": True,
                "assistance_required": False,
                "notes": "Client enjoyed breakfast and ate well"
            },
            {
                "client_id": clients[0]["id"],
                "meal_type": "lunch",
                "meal_time": "12:30 PM",
                "food_items": ["Grilled chicken", "Steamed vegetables", "Rice", "Apple"],
                "intake_amount": "all",
                "percentage_consumed": 100,
                "calories": 520.0,
                "water_intake_ml": 300,
                "appetite_level": "good",
                "dietary_preferences_followed": True,
                "dietary_restrictions_followed": True,
                "assistance_required": False,
                "notes": "Excellent appetite, finished entire meal"
            },
            {
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "meal_type": "breakfast",
                "meal_time": "08:15 AM",
                "food_items": ["Cereal", "Milk", "Banana"],
                "intake_amount": "partial",
                "percentage_consumed": 60,
                "water_intake_ml": 180,
                "appetite_level": "fair",
                "notes": "Client ate slowly, needed encouragement"
            }
        ]

        for meal_data in meal_logs_data:
            meal = create_meal_log(token, meal_data)
            if meal:
                meal_logs.append(meal)
                print_success(f"Created meal log: {meal_data['meal_type']}")

    print_success(f"\nCreated {len(meal_logs)} meal logs")

    # Create Incident Reports
    print_header("CREATING INCIDENT REPORTS")

    incidents = []
    if len(clients) > 0:
        incidents_data = [
            {
                "client_id": clients[0]["id"],
                "incident_type": "behavioral",
                "description": "Client became agitated during group activity. Staff intervened with de-escalation techniques.",
                "action_taken": "Removed client to quiet area, provided calming activities, monitored closely",
                "severity": "low",
                "incident_date": str(date.today() - timedelta(days=2)),
                "incident_time": "14:30",
                "location": "Recreation room",
                "follow_up_required": False
            }
        ]

        for incident_data in incidents_data:
            incident = create_incident_report(token, incident_data)
            if incident:
                incidents.append(incident)
                print_success(f"Created incident report: {incident_data['incident_type']}")

    print_success(f"\nCreated {len(incidents)} incident reports")

    # Create Locations
    print_header("CREATING LOCATIONS")

    locations_data = [
        {
            "name": "Main Residence - Maple Street",
            "address": "123 Maple Street",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62701",
            "phone": "+1-555-1000",
            "type": "residential",
            "capacity": 6
        },
        {
            "name": "Community Living Center",
            "address": "456 Oak Avenue",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62702",
            "phone": "+1-555-1001",
            "type": "residential",
            "capacity": 8
        },
        {
            "name": "Independence Day Program",
            "address": "789 Pine Road",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62703",
            "phone": "+1-555-1002",
            "type": "day_program",
            "capacity": 15
        },
        {
            "name": "Community Integration Center",
            "address": "321 Elm Street",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62704",
            "phone": "+1-555-1003",
            "type": "community",
            "capacity": 20
        }
    ]

    locations = []
    for location_data in locations_data:
        location = create_location(token, location_data)
        if location:
            locations.append(location)
            print_success(f"Created location: {location_data['name']}")

    print_success(f"\nCreated {len(locations)} locations")

    # Assign Clients to Locations
    print_header("ASSIGNING CLIENTS TO LOCATIONS")

    client_location_assignments = []
    if len(clients) > 0 and len(locations) > 0:
        # Assign each client to a location
        for i, client in enumerate(clients):
            location_index = i % len(locations)  # Distribute clients across locations
            assignment_data = {
                "location_id": locations[location_index]["id"],
                "start_date": str(date.today() - timedelta(days=30)),
                "room_number": f"Room {100 + i}",
                "bed_number": f"Bed {i + 1}"
            }

            assignment = assign_client_to_location(token, client["id"], assignment_data)
            if assignment:
                client_location_assignments.append(assignment)
                print_success(f"Assigned {client['first_name']} {client['last_name']} to {locations[location_index]['name']}")

    print_success(f"\nCreated {len(client_location_assignments)} client-location assignments")

    # Create Schedules and Shifts for tim@kaziflex.com (first staff member)
    print_header("CREATING SCHEDULES AND SHIFTS")

    schedules = []
    shifts = []
    if len(staff_members) > 0 and len(clients) > 0:
        tim_staff = staff_members[0]  # tim@kaziflex.com
        org_id = staff_members[0]["organization_id"]

        # Create a schedule for the week
        schedule_data = {
            "schedule_name": f"Weekly Schedule - {tim_staff['full_name']}",
            "staff_id": tim_staff["id"],
            "start_date": str(date.today() - timedelta(days=7)),
            "end_date": str(date.today() + timedelta(days=7)),
            "schedule_type": "weekly",
            "is_active": True
        }
        schedule = create_schedule(token, schedule_data, org_id)

        if schedule:
            schedules.append(schedule)
            print_success(f"Created schedule for {tim_staff['full_name']}")

            # Define shift time slots throughout the day
            from datetime import datetime as dt
            current_time = dt.now().time()
            current_hour = current_time.hour

            # Time slots for shifts (allows testing at any time of day)
            shift_slots = [
                {"name": "Early Morning", "start": "06:00:00", "end": "10:00:00"},
                {"name": "Late Morning", "start": "10:00:00", "end": "14:00:00"},
                {"name": "Afternoon", "start": "14:00:00", "end": "18:00:00"},
                {"name": "Evening", "start": "18:00:00", "end": "22:00:00"}
            ]

            # Create multiple shifts for today covering different time periods
            print_success(f"Creating shifts for today ({date.today()}):")
            active_shift_id = None

            for idx, slot in enumerate(shift_slots):
                # Determine which client for this slot (rotate through clients)
                client_idx = idx % len(clients)
                client = clients[client_idx]

                # Parse start and end times
                start_hour = int(slot["start"].split(":")[0])
                end_hour = int(slot["end"].split(":")[0])

                # Check if current time falls within this shift
                is_active = start_hour <= current_hour < end_hour

                today_shift_data = {
                    "schedule_id": schedule["id"],
                    "staff_id": tim_staff["id"],
                    "client_id": client["id"],
                    "shift_date": str(date.today()),
                    "start_time": slot["start"],
                    "end_time": slot["end"],
                    "shift_type": "regular",
                    "status": "scheduled",
                    "required_documentation": ["vitals_log", "shift_note", "meal_log"]
                }

                shift = create_shift(token, today_shift_data)
                if shift:
                    shifts.append(shift)
                    status_icon = "🟢 ACTIVE" if is_active else "⚪"
                    print_success(f"  {status_icon} {slot['name']} ({slot['start']}-{slot['end']}): {client['first_name']} {client['last_name']}")

                    # Track active shift for clock-in
                    if is_active:
                        active_shift_id = shift["id"]

            # Clock in to the active shift if one exists
            if active_shift_id:
                clock_in_result = clock_in(token, active_shift_id)
                if clock_in_result:
                    print_success(f"✓ Clocked in {tim_staff['full_name']} to active shift")
            else:
                print_warning(f"⚠️  No active shift at current time ({current_hour}:00). DSP will need to wait for shift start.")

            # Create shifts for the week (Mon-Fri) with multiple daily shifts
            print_success(f"\nCreating shifts for the rest of the week:")
            for day_offset in range(-3, 8):  # Past 3 days + future 7 days
                if day_offset == 0:  # Skip today, already created
                    continue

                shift_date = date.today() + timedelta(days=day_offset)
                # Skip weekends
                if shift_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                    continue

                day_name = shift_date.strftime("%a %m/%d")
                day_status = "completed" if day_offset < 0 else "scheduled"
                status_emoji = "✓" if day_offset < 0 else "📅"

                # Create 2 shifts per day (morning and afternoon)
                daily_slots = [
                    {"name": "Morning", "start": "08:00:00", "end": "13:00:00"},
                    {"name": "Afternoon", "start": "13:00:00", "end": "18:00:00"}
                ]

                for slot_idx, slot in enumerate(daily_slots):
                    # Rotate through clients
                    client_idx = (abs(day_offset) + slot_idx) % len(clients)
                    client = clients[client_idx]

                    shift_data = {
                        "schedule_id": schedule["id"],
                        "staff_id": tim_staff["id"],
                        "client_id": client["id"],
                        "shift_date": str(shift_date),
                        "start_time": slot["start"],
                        "end_time": slot["end"],
                        "shift_type": "regular",
                        "status": day_status,
                        "required_documentation": ["vitals_log", "shift_note", "meal_log"]
                    }

                    shift = create_shift(token, shift_data)
                    if shift:
                        shifts.append(shift)
                        print_success(f"  {status_emoji} {day_name} {slot['name']}: {client['first_name']} {client['last_name']}")

    print_success(f"\nCreated {len(schedules)} schedules and {len(shifts)} shifts")

    # Create Appointments
    print_header("CREATING APPOINTMENTS")

    appointments = []
    if len(clients) > 0 and len(staff_members) > 0:
        # Get organization_id from staff member
        org_id = staff_members[0]["organization_id"]

        appointments_data = [
            # Today's appointments
            {
                "organization_id": org_id,
                "client_id": clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Annual Physical Examination",
                "appointment_type": "medical",
                "start_datetime": f"{date.today()}T14:00:00",
                "end_datetime": f"{date.today()}T15:00:00",
                "location": "Springfield Medical Center",
                "notes": "Annual physical examination",
                "status": "scheduled"
            },
            {
                "organization_id": org_id,
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Physical Therapy Session",
                "appointment_type": "therapy",
                "start_datetime": f"{date.today()}T15:30:00",
                "end_datetime": f"{date.today()}T16:30:00",
                "location": "Wellness Center",
                "notes": "Physical therapy session",
                "status": "scheduled"
            },
            # Tomorrow's appointments
            {
                "organization_id": org_id,
                "client_id": clients[2]["id"] if len(clients) > 2 else clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Dental Checkup",
                "appointment_type": "medical",
                "start_datetime": f"{date.today() + timedelta(days=1)}T10:00:00",
                "end_datetime": f"{date.today() + timedelta(days=1)}T11:00:00",
                "location": "Family Dental Care",
                "notes": "Routine dental examination and cleaning",
                "status": "scheduled"
            },
            {
                "organization_id": org_id,
                "client_id": clients[3]["id"] if len(clients) > 3 else clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Occupational Therapy",
                "appointment_type": "therapy",
                "start_datetime": f"{date.today() + timedelta(days=1)}T13:00:00",
                "end_datetime": f"{date.today() + timedelta(days=1)}T14:00:00",
                "location": "Rehabilitation Center",
                "notes": "Fine motor skills development",
                "status": "scheduled"
            },
            # This week's appointments
            {
                "organization_id": org_id,
                "client_id": clients[1]["id"] if len(clients) > 1 else clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Community Outing",
                "appointment_type": "outing",
                "start_datetime": f"{date.today() + timedelta(days=3)}T10:00:00",
                "end_datetime": f"{date.today() + timedelta(days=3)}T12:00:00",
                "location": "City Park",
                "notes": "Social skills development activity",
                "status": "scheduled"
            },
            {
                "organization_id": org_id,
                "client_id": clients[0]["id"],
                "staff_id": staff_members[0]["id"],
                "title": "Psychiatrist Appointment",
                "appointment_type": "medical",
                "start_datetime": f"{date.today() + timedelta(days=5)}T11:00:00",
                "end_datetime": f"{date.today() + timedelta(days=5)}T12:00:00",
                "location": "Mental Health Clinic",
                "notes": "Medication review and therapy session",
                "status": "scheduled"
            }
        ]

        for appointment_data in appointments_data:
            appointment = create_appointment(token, appointment_data)
            if appointment:
                appointments.append(appointment)
                print_success(f"Created appointment: {appointment_data['title']}")

    print_success(f"\nCreated {len(appointments)} appointments")

    # Create Notifications
    print_header("CREATING NOTIFICATIONS")

    notifications_created = []
    if len(clients) > 0 and len(staff_members) > 0:
        notifications_data = [
            # Critical notifications
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Missed Medication",
                "message": f"{clients[0]['full_name']}'s 8:00 AM dose not logged.",
                "type": "critical",
                "category": "medication"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Incident Form Pending",
                "message": f"Shift incident for {clients[2]['full_name'] if len(clients) > 2 else clients[0]['full_name']} needs submission.",
                "type": "critical",
                "category": "incident"
            },
            # Reminder notifications
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Meal Log Missing",
                "message": f"No lunch intake recorded for {clients[1]['full_name'] if len(clients) > 1 else clients[0]['full_name']}.",
                "type": "reminder",
                "category": "general"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Vitals Entry Due",
                "message": f"Scheduled vitals for {clients[0]['full_name']} at 2:00 PM.",
                "type": "reminder",
                "category": "task"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Appointment Reminder",
                "message": f"{clients[3]['full_name'] if len(clients) > 3 else clients[0]['full_name']} has a doctor's appointment at 3:00 PM.",
                "type": "reminder",
                "category": "appointment"
            },
            # Info notifications
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "New Form Added",
                "message": '"Daily Risk Tracking" form now available in Documentation.',
                "type": "info",
                "category": "system"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Shift Schedule Updated",
                "message": "Your schedule for next week has been updated.",
                "type": "info",
                "category": "schedule"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Training Reminder",
                "message": "CPR certification renewal due in 30 days.",
                "type": "reminder",
                "category": "general"
            }
        ]

        for notification_data in notifications_data:
            notification = create_notification(token, notification_data)
            if notification:
                notifications_created.append(notification)
                print_success(f"Created notification: {notification_data['title']}")

    print_success(f"\nCreated {len(notifications_created)} notifications")

    # Summary
    print_header("SEEDING COMPLETE")

    print_success(f"✓ Created {len(clients)} clients")
    print_success(f"✓ Created {len(staff_members)} staff members")
    print_success(f"✓ Created {len(assignments)} staff assignments")
    print_success(f"✓ Created {len(locations)} locations")
    print_success(f"✓ Created {len(client_location_assignments)} client-location assignments")
    print_success(f"✓ Created {len(schedules)} schedules")
    print_success(f"✓ Created {len(shifts)} shifts")
    print_success(f"✓ Created {len(appointments)} appointments")
    print_success(f"✓ Created {len(notifications_created)} notifications")
    print_success(f"✓ Created {len(tasks)} tasks")
    print_success(f"✓ Created {len(vitals_logs)} vitals logs")
    print_success(f"✓ Created {len(shift_notes)} shift notes")
    print_success(f"✓ Created {len(meal_logs)} meal logs")
    print_success(f"✓ Created {len(incidents)} incident reports")

    # Seed Training Courses and Activities (login as Tim)
    tim_staff = staff_members[0] if staff_members else None
    tim_user_id = tim_staff['user']['id'] if tim_staff else None
    tim_password = tim_staff.get('temporary_password') if tim_staff else None
    tim_token = None  # Initialize tim_token

    if tim_user_id and admin_user_id and org_id and tim_password:
        # Login as Tim to create his training progress and activities
        tim_token_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "tim@kaziflex.com", "password": tim_password}
        )
        if tim_token_response.status_code == 200:
            tim_token = tim_token_response.json()["access_token"]
            training_courses = seed_training_courses(tim_token, org_id, admin_user_id, tim_user_id)
            print_success(f"✓ Created {len(training_courses)} training courses")
        else:
            print_warning(f"Could not login as Tim. Status: {tim_token_response.status_code}")
            print_warning(f"Response: {tim_token_response.text}")
            training_courses = []
    else:
        print_warning("Missing required data for training courses seeding")
        training_courses = []

    # Seed Notices (as admin)
    if admin_user_id and org_id:
        notices = seed_notices(token, org_id, admin_user_id)
        print_success(f"✓ Created {len(notices)} notices")
    else:
        print_warning("Missing required data for notices seeding")
        notices = []

    # Activities will be added manually through the UI
    print_info("\n📝 Activities can be added manually through the UI")

    # Display credentials table for clients
    if clients:
        print_header("CLIENT CREDENTIALS")
        print(f"{Colors.BOLD}{'Name':<20} {'Client ID':<11} {'Email':<30} {'Username':<20} {'Password':<15}{Colors.ENDC}")
        print("-" * 96)
        for client in clients:
            name = client['full_name'][:19]
            client_id = client['client_id']
            email = client['email'][:29]
            username = client.get('username', 'N/A')[:19]
            password = client.get('temporary_password', 'N/A')[:14]
            print(f"{name:<20} {client_id:<11} {email:<30} {username:<20} {password:<15}")

    # Display credentials table for staff
    if staff_members:
        print_header("STAFF CREDENTIALS")
        print(f"{Colors.BOLD}{'Name':<20} {'Emp ID':<8} {'Email':<30} {'Username':<20} {'Password':<15}{Colors.ENDC}")
        print("-" * 93)
        for staff in staff_members:
            name = staff['full_name'][:19]
            emp_id = staff['employee_id']
            email = staff['user']['email'][:29]
            username = staff['user']['username'][:19]
            password = staff.get('temporary_password', 'N/A')[:14]
            print(f"{name:<20} {emp_id:<8} {email:<30} {username:<20} {password:<15}")

    print_info("\n📋 Summary:")
    print_info(f"  • Clients: {', '.join([c['full_name'] for c in clients])}")
    print_info(f"  • Staff: {', '.join([s['full_name'] for s in staff_members])}")
    if len(staff_members) > 0 and len(clients) > 0:
        print_info(f"  • Assignment: {staff_members[0]['full_name']} → {clients[0]['full_name']}")

    print_info(f"\n🌐 Access the API at: {BASE_URL}")
    print_info(f"📚 API Documentation: {BASE_URL.replace('/api/v1', '')}/api/v1/docs")

    print(f"\n{Colors.OKGREEN}{Colors.BOLD}Database seeding completed successfully!{Colors.ENDC}\n")
    print_warning("⚠️  IMPORTANT: Save these credentials securely. They will not be displayed again!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nSeeding interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {str(e)}")
        sys.exit(1)