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