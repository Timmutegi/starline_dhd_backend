import requests
import json
import datetime
import time

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "support@starline.com"
ADMIN_PASSWORD = "Admin123!!"

def login(email, password):
    print(f"Logging in as {email}...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        exit(1)
    return response.json()["access_token"]

def create_client(token):
    print("Creating client...")
    data = {
        "first_name": "Test",
        "last_name": f"Client_{int(time.time())}",
        "email": f"client_{int(time.time())}@example.com",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "admission_date": datetime.date.today().isoformat(),
        "status": "active"
    }
    response = requests.post(
        f"{BASE_URL}/clients/",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to create client: {response.text}")
        exit(1)
    return response.json()["client"]

def create_staff(token):
    print("Creating staff...")
    data = {
        "first_name": "Test",
        "last_name": f"Staff_{int(time.time())}",
        "email": f"staff_{int(time.time())}@example.com",
        "phone": "+15550000000",
        "employee_id": f"EMP_{int(time.time())}",
        "hire_date": datetime.date.today().isoformat(),
        "role_id": get_support_role_id(token),
        "pay_type": "hourly",
        "hourly_rate": 20.0
    }
    response = requests.post(
        f"{BASE_URL}/staff/",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to create staff: {response.text}")
        exit(1)
    return response.json()

def get_support_role_id(token):
    response = requests.get(
        f"{BASE_URL}/roles/",
        headers={"Authorization": f"Bearer {token}"}
    )
    roles = response.json()
    for role in roles:
        if role["name"] == "Support Staff":
            return role["id"]
    # Fallback to first role if not found
    return roles[0]["id"]

def assign_staff(token, staff_id, client_id):
    print("Assigning staff to client...")
    data = {
        "client_id": client_id,
        "assignment_type": "primary",
        "start_date": datetime.date.today().isoformat()
    }
    response = requests.post(
        f"{BASE_URL}/staff/{staff_id}/assignments",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to assign staff: {response.text}")
        exit(1)

def create_schedule_and_shift(token, staff_id, client_id, org_id):
    print("Creating schedule and shift...")
    # Create Schedule
    schedule_data = {
        "schedule_name": "Test Schedule",
        "staff_id": staff_id,
        "organization_id": org_id,
        "start_date": datetime.date.today().isoformat(),
        "end_date": datetime.date.today().isoformat(),
        "schedule_type": "weekly",
        "is_active": True
    }
    response = requests.post(
        f"{BASE_URL}/scheduling/schedules",
        headers={"Authorization": f"Bearer {token}"},
        json=schedule_data
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to create schedule: {response.text}")
        exit(1)
    schedule_id = response.json()["id"]

    # Create Shift
    # Set shift from 08:00 to 23:00 to cover most current times without crossing midnight
    start_time = "08:00:00"
    end_time = "23:00:00"
    
    shift_data = {
        "schedule_id": schedule_id,
        "staff_id": staff_id,
        "client_id": client_id,
        "shift_date": datetime.date.today().isoformat(),
        "start_time": start_time,
        "end_time": end_time,
        "shift_type": "regular",
        "status": "scheduled",
        "required_documentation": ["vitals_log"]
    }
    response = requests.post(
        f"{BASE_URL}/scheduling/shifts",
        headers={"Authorization": f"Bearer {token}"},
        json=shift_data
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to create shift: {response.text}")
        exit(1)
    return response.json()

def clock_in(token, shift_id):
    print("Clocking in...")
    response = requests.post(
        f"{BASE_URL}/scheduling/time-clock/clock-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"shift_id": shift_id}
    )
    if response.status_code not in [200, 201]:
        print(f"Failed to clock in: {response.text}")
        exit(1)

def get_stool_types(token):
    print("Fetching stool types...")
    response = requests.get(
        f"{BASE_URL}/documentation/bowel-movements/types",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(f"Failed to get stool types: {response.text}")
        exit(1)
    types = response.json()
    print(f"Found {len(types)} stool types")
    for t in types:
        print(f"  {t['type']}: {t['description']}")

def create_bowel_movement(token, client_id):
    print("Creating bowel movement log...")
    data = {
        "client_id": client_id,
        "stool_type": "Type 4",
        "stool_color": "Brown",
        "additional_information": "Normal",
        "recorded_at": datetime.datetime.now().isoformat()
    }
    response = requests.post(
        f"{BASE_URL}/documentation/bowel-movements",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code != 200:
        print(f"Failed to create log: {response.text}")
        exit(1)
    print("Log created successfully")
    return response.json()

def get_bowel_movements(token, client_id):
    print("Fetching bowel movement logs...")
    response = requests.get(
        f"{BASE_URL}/documentation/bowel-movements?client_id={client_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(f"Failed to get logs: {response.text}")
        exit(1)
    data = response.json()
    print(f"Found {len(data['data'])} logs")
    for log in data['data']:
        print(f"  {log['recorded_at']}: {log['stool_type']} - {log['stool_color']}")

def main():
    # 1. Login as Admin
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    # 2. Create Client
    client = create_client(admin_token)
    print(f"Created client: {client['id']}")
    
    # 3. Create Staff
    staff_result = create_staff(admin_token)
    staff = staff_result["staff"]
    temp_password = staff_result["temporary_password"]
    print(f"Created staff: {staff['id']} with password {temp_password}")
    
    # 4. Assign Staff to Client
    assign_staff(admin_token, staff["id"], client["id"])
    
    # 5. Create Schedule and Shift
    shift = create_schedule_and_shift(admin_token, staff["id"], client["id"], staff["organization_id"])
    print(f"Created shift: {shift['id']}")
    
    # 6. Login as Staff
    staff_token = login(staff["user"]["email"], temp_password)
    
    # 7. Clock In
    clock_in(staff_token, shift["id"])
    
    # 8. Test Bowel Movement Endpoints
    get_stool_types(staff_token)
    create_bowel_movement(staff_token, client["id"])
    get_bowel_movements(staff_token, client["id"])

if __name__ == "__main__":
    main()
