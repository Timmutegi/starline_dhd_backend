import resend
from typing import Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader
from app.core.config import settings
import os

resend.api_key = settings.RESEND_API_KEY

template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "emails", "templates")
env = Environment(loader=FileSystemLoader(template_dir))

class EmailService:
    @staticmethod
    def render_template(template_name: str, context: Dict[str, Any]) -> str:
        template = env.get_template(template_name)
        return template.render(**context)

    @staticmethod
    async def send_email(
        to: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        from_email: Optional[str] = None
    ) -> bool:
        try:
            html_content = EmailService.render_template(template_name, context)

            params = {
                "from": from_email or settings.FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "html": html_content
            }

            response = resend.Emails.send(params)
            return response.get("id") is not None

        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

    @staticmethod
    async def send_verification_email(
        email: str,
        otp: str,
        verification_link: str
    ) -> bool:
        context = {
            "otp": otp,
            "verification_link": verification_link,
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=email,
            subject="Verify Your Email - Starline",
            template_name="email_verification.html",
            context=context
        )

    @staticmethod
    async def send_password_reset_email(
        email: str,
        otp: str,
        reset_link: str,
        user_name: str
    ) -> bool:
        context = {
            "user_name": user_name,
            "otp": otp,
            "reset_link": reset_link,
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=email,
            subject="Reset Your Password - Starline",
            template_name="password_reset.html",
            context=context
        )

    @staticmethod
    async def send_welcome_email(
        email: str,
        user_name: str,
        organization_name: str
    ) -> bool:
        context = {
            "user_name": user_name,
            "organization_name": organization_name,
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=email,
            subject=f"Welcome to {organization_name} - Starline",
            template_name="welcome.html",
            context=context
        )

    @staticmethod
    async def send_account_locked_email(
        email: str,
        user_name: str,
        unlock_time: str
    ) -> bool:
        context = {
            "user_name": user_name,
            "unlock_time": unlock_time,
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=email,
            subject="Account Locked - Starline",
            template_name="account_locked.html",
            context=context
        )

    @staticmethod
    async def send_password_changed_email(
        email: str,
        user_name: str
    ) -> bool:
        context = {
            "user_name": user_name,
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=email,
            subject="Password Changed - Starline",
            template_name="password_changed.html",
            context=context
        )

    @staticmethod
    async def send_client_credentials(
        email: str,
        full_name: str,
        username: str,
        password: str,
        organization_name: str,
        support_email: Optional[str] = None,
        support_phone: Optional[str] = None
    ) -> bool:
        from datetime import datetime

        context = {
            "organization_name": organization_name,
            "full_name": full_name,
            "username": username,
            "email": email,
            "password": password,
            "login_url": settings.FRONTEND_URL,
            "frontend_url": settings.FRONTEND_URL,
            "support_email": support_email or settings.DEFAULT_ADMIN_EMAIL,
            "support_phone": support_phone or "Contact Administrator",
            "contact_email": settings.DEFAULT_ADMIN_EMAIL,
            "current_year": datetime.now().year
        }

        return await EmailService.send_email(
            to=email,
            subject=f"Your Account Has Been Created - {organization_name}",
            template_name="client_credentials.html",
            context=context
        )

    @staticmethod
    async def send_staff_credentials(
        email: str,
        full_name: str,
        username: str,
        password: str,
        employee_id: str,
        organization_name: str,
        role_name: str,
        department: Optional[str] = None,
        hire_date: Optional[str] = None,
        supervisor_name: Optional[str] = None,
        supervisor_email: Optional[str] = None,
        support_email: Optional[str] = None,
        support_phone: Optional[str] = None,
        hr_email: Optional[str] = None
    ) -> bool:
        from datetime import datetime

        context = {
            "organization_name": organization_name,
            "full_name": full_name,
            "username": username,
            "email": email,
            "password": password,
            "employee_id": employee_id,
            "role_name": role_name,
            "department": department or "Not Specified",
            "hire_date": hire_date or "Not Specified",
            "supervisor_name": supervisor_name or "Not Assigned",
            "supervisor_email": supervisor_email or settings.DEFAULT_ADMIN_EMAIL,
            "login_url": settings.FRONTEND_URL,
            "frontend_url": settings.FRONTEND_URL,
            "support_email": support_email or settings.DEFAULT_ADMIN_EMAIL,
            "support_phone": support_phone or "Contact Administrator",
            "hr_email": hr_email or settings.DEFAULT_ADMIN_EMAIL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL,
            "current_year": datetime.now().year
        }

        return await EmailService.send_email(
            to=email,
            subject=f"Welcome to {organization_name} - Your Staff Account Details",
            template_name="staff_credentials.html",
            context=context
        )

    # ==================== SHIFT EXCHANGE NOTIFICATIONS ====================

    @staticmethod
    async def send_shift_exchange_request_email(
        to_email: str,
        recipient_name: str,
        requester_name: str,
        requester_shift_date: str,
        requester_shift_time: str,
        target_shift_date: str,
        target_shift_time: str,
        requester_client: str = None,
        target_client: str = None,
        reason: str = None
    ) -> bool:
        """Send email to target staff when a shift exchange is requested."""
        context = {
            "recipient_name": recipient_name,
            "requester_name": requester_name,
            "requester_shift_date": requester_shift_date,
            "requester_shift_time": requester_shift_time,
            "target_shift_date": target_shift_date,
            "target_shift_time": target_shift_time,
            "requester_client": requester_client,
            "target_client": target_client,
            "reason": reason,
            "dashboard_url": f"{settings.FRONTEND_URL}/shift-exchanges",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="New Shift Exchange Request - DHD",
            template_name="shift_exchange_request.html",
            context=context
        )

    @staticmethod
    async def send_shift_exchange_accepted_email(
        to_email: str,
        recipient_name: str,
        accepter_name: str,
        requester_shift_date: str,
        requester_shift_time: str,
        target_shift_date: str,
        target_shift_time: str,
        requester_client: str = None,
        target_client: str = None
    ) -> bool:
        """Send email to requester when their shift exchange is accepted by peer."""
        context = {
            "recipient_name": recipient_name,
            "accepter_name": accepter_name,
            "requester_shift_date": requester_shift_date,
            "requester_shift_time": requester_shift_time,
            "target_shift_date": target_shift_date,
            "target_shift_time": target_shift_time,
            "requester_client": requester_client,
            "target_client": target_client,
            "dashboard_url": f"{settings.FRONTEND_URL}/shift-exchanges",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Shift Exchange Accepted - Pending Manager Approval - DHD",
            template_name="shift_exchange_accepted.html",
            context=context
        )

    @staticmethod
    async def send_shift_exchange_declined_email(
        to_email: str,
        recipient_name: str,
        decliner_name: str,
        requester_shift_date: str,
        requester_shift_time: str,
        target_shift_date: str,
        target_shift_time: str,
        requester_client: str = None,
        target_client: str = None,
        notes: str = None
    ) -> bool:
        """Send email to requester when their shift exchange is declined by peer."""
        context = {
            "recipient_name": recipient_name,
            "decliner_name": decliner_name,
            "requester_shift_date": requester_shift_date,
            "requester_shift_time": requester_shift_time,
            "target_shift_date": target_shift_date,
            "target_shift_time": target_shift_time,
            "requester_client": requester_client,
            "target_client": target_client,
            "notes": notes,
            "dashboard_url": f"{settings.FRONTEND_URL}/schedule",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Shift Exchange Declined - DHD",
            template_name="shift_exchange_declined.html",
            context=context
        )

    @staticmethod
    async def send_shift_exchange_pending_manager_email(
        to_email: str,
        manager_name: str,
        requester_name: str,
        target_name: str,
        requester_shift_date: str,
        requester_shift_time: str,
        target_shift_date: str,
        target_shift_time: str,
        requester_client: str = None,
        target_client: str = None,
        reason: str = None
    ) -> bool:
        """Send email to manager when a shift exchange needs approval."""
        context = {
            "manager_name": manager_name,
            "requester_name": requester_name,
            "target_name": target_name,
            "requester_shift_date": requester_shift_date,
            "requester_shift_time": requester_shift_time,
            "target_shift_date": target_shift_date,
            "target_shift_time": target_shift_time,
            "requester_client": requester_client,
            "target_client": target_client,
            "reason": reason,
            "dashboard_url": f"{settings.FRONTEND_URL}/manager/approvals",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Shift Exchange Pending Approval - DHD",
            template_name="shift_exchange_pending_manager.html",
            context=context
        )

    @staticmethod
    async def send_shift_exchange_approved_email(
        to_email: str,
        recipient_name: str,
        manager_name: str,
        new_shift_date: str,
        new_shift_time: str,
        new_client: str = None,
        manager_notes: str = None
    ) -> bool:
        """Send email to staff when their shift exchange is approved by manager."""
        context = {
            "recipient_name": recipient_name,
            "manager_name": manager_name,
            "new_shift_date": new_shift_date,
            "new_shift_time": new_shift_time,
            "new_client": new_client,
            "manager_notes": manager_notes,
            "dashboard_url": f"{settings.FRONTEND_URL}/schedule",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Shift Exchange Approved - DHD",
            template_name="shift_exchange_approved.html",
            context=context
        )

    @staticmethod
    async def send_shift_exchange_denied_by_manager_email(
        to_email: str,
        recipient_name: str,
        manager_name: str,
        your_shift_date: str,
        your_shift_time: str,
        your_client: str = None,
        manager_notes: str = None
    ) -> bool:
        """Send email to staff when their shift exchange is denied by manager."""
        context = {
            "recipient_name": recipient_name,
            "manager_name": manager_name,
            "your_shift_date": your_shift_date,
            "your_shift_time": your_shift_time,
            "your_client": your_client,
            "manager_notes": manager_notes,
            "dashboard_url": f"{settings.FRONTEND_URL}/schedule",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Shift Exchange Denied - DHD",
            template_name="shift_exchange_denied.html",
            context=context
        )

    # ==================== TIME-OFF REQUEST NOTIFICATIONS ====================

    @staticmethod
    async def send_time_off_request_email(
        to_email: str,
        manager_name: str,
        staff_name: str,
        request_type: str,
        start_date: str,
        end_date: str,
        total_hours: str,
        staff_role: str = None,
        reason: str = None
    ) -> bool:
        """Send email to manager when a new time-off request is submitted."""
        context = {
            "manager_name": manager_name,
            "staff_name": staff_name,
            "staff_role": staff_role,
            "request_type": request_type,
            "start_date": start_date,
            "end_date": end_date,
            "total_hours": total_hours,
            "reason": reason,
            "dashboard_url": f"{settings.FRONTEND_URL}/manager/approvals",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject=f"New Time-Off Request from {staff_name} - DHD",
            template_name="time_off_request.html",
            context=context
        )

    @staticmethod
    async def send_time_off_approved_email(
        to_email: str,
        staff_name: str,
        manager_name: str,
        request_type: str,
        start_date: str,
        end_date: str,
        total_hours: str,
        manager_notes: str = None
    ) -> bool:
        """Send email to staff when their time-off request is approved."""
        context = {
            "staff_name": staff_name,
            "manager_name": manager_name,
            "request_type": request_type,
            "start_date": start_date,
            "end_date": end_date,
            "total_hours": total_hours,
            "manager_notes": manager_notes,
            "dashboard_url": f"{settings.FRONTEND_URL}/time-off",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Time-Off Request Approved - DHD",
            template_name="time_off_approved.html",
            context=context
        )

    @staticmethod
    async def send_time_off_denied_email(
        to_email: str,
        staff_name: str,
        manager_name: str,
        request_type: str,
        start_date: str,
        end_date: str,
        total_hours: str,
        denial_reason: str = None
    ) -> bool:
        """Send email to staff when their time-off request is denied."""
        context = {
            "staff_name": staff_name,
            "manager_name": manager_name,
            "request_type": request_type,
            "start_date": start_date,
            "end_date": end_date,
            "total_hours": total_hours,
            "denial_reason": denial_reason,
            "dashboard_url": f"{settings.FRONTEND_URL}/time-off",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        return await EmailService.send_email(
            to=to_email,
            subject="Time-Off Request Denied - DHD",
            template_name="time_off_denied.html",
            context=context
        )

    # ==================== HELP REQUEST NOTIFICATIONS ====================

    @staticmethod
    async def send_help_request_notification(
        to_email: str,
        recipient_name: str,
        client_name: str,
        request_type: str,
        title: str,
        description: str,
        priority: str,
        preferred_time: str = None,
        submitted_at: str = None
    ) -> bool:
        """Send email notification when a client submits a help request."""
        # Format request type for display
        request_type_labels = {
            "shopping": "Shopping Assistance",
            "transportation": "Transportation",
            "medical": "Medical Assistance",
            "medication": "Medication Reminder",
            "meals": "Meal Assistance",
            "household": "Household Help",
            "communication": "Communication",
            "emergency": "Urgent/Emergency",
            "other": "Other"
        }
        formatted_request_type = request_type_labels.get(request_type, request_type.replace("_", " ").title())

        context = {
            "recipient_name": recipient_name,
            "client_name": client_name,
            "request_type": formatted_request_type,
            "title": title,
            "description": description,
            "priority": priority.lower(),
            "preferred_time": preferred_time,
            "submitted_at": submitted_at,
            "dashboard_url": f"{settings.FRONTEND_URL}/help-requests",
            "frontend_url": settings.FRONTEND_URL,
            "contact_email": settings.DEFAULT_ADMIN_EMAIL
        }

        # Customize subject based on priority
        if priority.lower() == "urgent":
            subject = f"🚨 URGENT Help Request from {client_name} - DHD"
        elif priority.lower() == "high":
            subject = f"⚡ High Priority Help Request from {client_name} - DHD"
        else:
            subject = f"New Help Request from {client_name} - DHD"

        return await EmailService.send_email(
            to=to_email,
            subject=subject,
            template_name="help_request_notification.html",
            context=context
        )