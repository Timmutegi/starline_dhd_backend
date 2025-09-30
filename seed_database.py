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
BASE_URL = "http://localhost:8000/api/v1" if ENVIRONMENT == "DEV" else "https://dla74pfa6wcvm.cloudfront.net/api/v1"

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

    # Summary
    print_header("SEEDING COMPLETE")

    print_success(f"✓ Created {len(clients)} clients")
    print_success(f"✓ Created {len(staff_members)} staff members")
    print_success(f"✓ Created 1 staff assignment")

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