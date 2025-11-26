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

    shift_data = {
        "schedule_id": schedule_id,
        "staff_id": staff_id,
        "client_id": client_id,
        "shift_date": datetime.date.today().isoformat(),
        "start_time": "08:00:00",
        "end_time": "23:00:00",
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

def create_sleep_log(token, client_id):
    print("Creating sleep log...")
    data = {
        "client_id": client_id,
        "shift_date": datetime.date.today().isoformat(),
        "sleep_periods": [
            {"start_time": "22:00", "end_time": "23:30"},
            {"start_time": "01:00", "end_time": "05:00"}
        ],
        "notes": "Client slept well with brief awakening",
        "recorded_at": datetime.datetime.now().isoformat()
    }
    response = requests.post(
        f"{BASE_URL}/documentation/sleep-logs",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code != 200:
        print(f"Failed to create sleep log: {response.text}")
        exit(1)
    print("Sleep log created successfully")
    log = response.json()
    print(f"  Total sleep: {log['total_sleep_minutes']} minutes")
    print(f"  Sleep periods: {log['sleep_periods']}")
    return log

def get_sleep_logs(token, client_id):
    print("Fetching sleep logs...")
    response = requests.get(
        f"{BASE_URL}/documentation/sleep-logs?client_id={client_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(f"Failed to get sleep logs: {response.text}")
        exit(1)
    data = response.json()
    print(f"Found {len(data['data'])} logs")
    for log in data['data']:
        print(f"  {log['shift_date']}: {log['total_sleep_minutes']} minutes")
        print(f"    Periods: {log['sleep_periods']}")

def main():
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    client = create_client(admin_token)
    print(f"Created client: {client['id']}")
    
    staff_result = create_staff(admin_token)
    staff = staff_result["staff"]
    temp_password = staff_result["temporary_password"]
    print(f"Created staff: {staff['id']} with password {temp_password}")
    
    assign_staff(admin_token, staff["id"], client["id"])
    
    shift = create_schedule_and_shift(admin_token, staff["id"], client["id"], staff["organization_id"])
    print(f"Created shift: {shift['id']}")
    
    staff_token = login(staff["user"]["email"], temp_password)
    
    clock_in(staff_token, shift["id"])
    
    create_sleep_log(staff_token, client["id"])
    get_sleep_logs(staff_token, client["id"])
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()
