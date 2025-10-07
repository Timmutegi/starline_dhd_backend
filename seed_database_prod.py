#!/usr/bin/env python3
"""
Database Seeding Script for Starline Backend
Creates sample clients, staff, and assignments using API endpoints
"""

import os
import sys
import requests
import json
from datetime import date, timedelta
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEV").upper()
# Force localhost for seeding since we're running against local Docker containers
BASE_URL = "http://localhost/api/v1"

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


def login() -> Optional[str]:
    """Login and get access token"""
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
            return data["access_token"]
        else:
            print_error(f"Login failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return None


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

        if response.status_code == 201:
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

        if response.status_code == 201:
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
            f"{BASE_URL}/locations",
            json=location_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 201:
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

        if response.status_code == 201:
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
            f"{BASE_URL}/notifications",
            json=notification_data,
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


def create_shift_assignment(token: str, shift_id: str, client_id: str) -> Optional[Dict]:
    """Create a shift assignment (linking a shift to a client)"""
    try:
        assignment_data = {
            "shift_id": shift_id,
            "client_id": client_id,
            "assignment_type": "primary",
            "notes": "Auto-assigned during seeding"
        }

        response = requests.post(
            f"{BASE_URL}/scheduling/shift-assignments",
            json=assignment_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            # Not a critical error, shifts can exist without assignments
            return None

    except Exception as e:
        return None


def main():
    """Main seeding function"""
    print_header("STARLINE DATABASE SEEDING SCRIPT")

    print_info(f"Environment: {ENVIRONMENT}")
    print_info(f"Base URL: {BASE_URL}")
    print()

    # Login
    token = login()
    if not token:
        print_error("Failed to login. Exiting...")
        sys.exit(1)

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
        {
            "first_name": "David",
            "last_name": "Mateo",
            "email": "mateo@kaziflex.com",
            "phone": "+1-555-0102",
            "employee_id": "SP002",
            "hire_date": str(date.today() - timedelta(days=545)),
            "department": "Direct Care",
            "job_title": "Care Provider",
            "pay_type": "hourly",
            "hourly_rate": "20.00",
            "role_id": support_staff_role_id,
            "use_custom_permissions": False
        },
        {
            "first_name": "Mat",
            "last_name": "Anderson",
            "email": "mat@kaziflex.com",
            "phone": "+1-555-0103",
            "employee_id": "SP003",
            "hire_date": str(date.today() - timedelta(days=365)),
            "department": "Direct Care",
            "job_title": "Care Provider",
            "pay_type": "hourly",
            "hourly_rate": "19.50",
            "role_id": support_staff_role_id,
            "use_custom_permissions": False
        },
        {
            "first_name": "Alfred",
            "last_name": "Taylor",
            "email": "alfred@kaziflex.com",
            "phone": "+1-555-0104",
            "employee_id": "SP004",
            "hire_date": str(date.today() - timedelta(days=180)),
            "department": "Direct Care",
            "job_title": "Care Provider",
            "preferred_name": "Rob",
            "pay_type": "hourly",
            "hourly_rate": "18.00",
            "role_id": support_staff_role_id,
            "use_custom_permissions": False
        },
        {
            "first_name": "Otto",
            "last_name": "Brown",
            "email": "otto@kaziflex.com",
            "phone": "+1-555-0105",
            "employee_id": "SP005",
            "hire_date": str(date.today() - timedelta(days=90)),
            "department": "Direct Care",
            "job_title": "Care Provider",
            "preferred_name": "Jen",
            "pay_type": "hourly",
            "hourly_rate": "17.50",
            "role_id": support_staff_role_id,
            "use_custom_permissions": False
        }
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

    # Assign first staff member to first client
    print_header("CREATING STAFF ASSIGNMENTS")

    if len(staff_members) > 0 and len(clients) > 0:
        assignment_data = {
            "client_id": clients[0]["id"],
            "assignment_type": "primary",
            "start_date": str(date.today()),
            "notes": "Primary care provider for client"
        }

        print_info(f"Assigning {staff_members[0]['full_name']} to {clients[0]['full_name']}...")
        assignment = assign_staff_to_client(
            token,
            staff_members[0]["id"],
            clients[0]["id"],
            assignment_data
        )

        if assignment:
            print_success("\nAssignment created successfully!")
        else:
            print_error("\nFailed to create assignment")

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

    # Note: Location creation endpoint not available in current API
    # Locations should be created via admin interface or separate management endpoint
    print_info("\nℹ Note: Locations should be created via admin interface")

    locations = []
    client_location_assignments = []

    # Create Schedules and Shifts for tim@kaziflex.com (first staff member)
    print_header("CREATING SCHEDULES AND SHIFTS")

    schedules = []
    shifts = []
    if len(staff_members) > 0 and len(clients) > 0:
        tim_staff = staff_members[0]  # tim@kaziflex.com
        org_id = staff_members[0]["organization_id"]

        # Create a schedule for the week
        schedule_data = {
            "schedule_name": f"Weekly Schedule - Week of {date.today().strftime('%Y-%m-%d')}",
            "start_date": str(date.today() - timedelta(days=7)),
            "end_date": str(date.today() + timedelta(days=7)),
            "schedule_type": "weekly",
            "notes": f"Primary schedule for {tim_staff['full_name']}"
        }
        schedule = create_schedule(token, schedule_data, org_id)

        if schedule:
            schedules.append(schedule)
            print_success(f"Created schedule for {tim_staff['full_name']}")

            # Today's shift (active)
            today_shift_data = {
                "schedule_id": schedule["id"],
                "staff_id": tim_staff["id"],
                "shift_date": str(date.today()),
                "start_time": "08:00:00",
                "end_time": "16:00:00",
                "shift_type": "regular",
                "notes": f"Assigned to {clients[0]['full_name']}"
            }
            today_shift = create_shift(token, today_shift_data)
            if today_shift:
                shifts.append(today_shift)
                print_success(f"Created today's shift for {tim_staff['full_name']}")

                # Try to create shift assignment
                shift_assignment = create_shift_assignment(token, today_shift["id"], clients[0]["id"])
                if shift_assignment:
                    print_success(f"  → Assigned shift to client {clients[0]['full_name']}")

                # Clock in to today's shift
                clock_in_result = clock_in(token, today_shift["id"])
                if clock_in_result:
                    print_success(f"  → Clocked in {tim_staff['full_name']} for today's shift")

            # Create shifts for the week (Mon-Fri)
            for day_offset in range(-3, 5):  # Past 3 days + future 4 days
                if day_offset == 0:  # Skip today, already created
                    continue

                shift_date = date.today() + timedelta(days=day_offset)
                # Skip weekends
                if shift_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                    continue

                client_index = abs(day_offset) % len(clients)
                shift_data = {
                    "schedule_id": schedule["id"],
                    "staff_id": tim_staff["id"],
                    "shift_date": str(shift_date),
                    "start_time": "08:00:00",
                    "end_time": "16:00:00",
                    "shift_type": "regular",
                    "notes": f"Assigned to {clients[client_index]['full_name']}"
                }
                shift = create_shift(token, shift_data)
                if shift:
                    shifts.append(shift)
                    # Try to create shift assignment
                    create_shift_assignment(token, shift["id"], clients[client_index]["id"])

    print_success(f"\nCreated {len(schedules)} schedules and {len(shifts)} shifts")

    # Create Appointments
    print_header("CREATING APPOINTMENTS")

    appointments = []
    if len(clients) > 0 and len(staff_members) > 0:
        # Get organization_id from staff member
        org_id = staff_members[0]["organization_id"]

        appointments_data = [
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
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Vitals Entry Due",
                "message": f"Scheduled vitals for {clients[0]['full_name']} at 2:00 PM.",
                "category": "reminder",
                "priority": "medium"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Meal Log Missing",
                "message": f"No lunch intake recorded for {clients[1]['full_name'] if len(clients) > 1 else clients[0]['full_name']}.",
                "category": "reminder",
                "priority": "medium"
            },
            {
                "user_id": staff_members[0]["user"]["id"],
                "title": "Incident Form Pending",
                "message": "Shift incident needs submission.",
                "category": "critical",
                "priority": "high"
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
    print_success(f"✓ Created 1 staff assignment")
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