from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Date, JSON, Integer, DECIMAL, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit_mixins import PHIAuditMixin
from datetime import datetime, timezone
import uuid

# Enum values as constants for validation
CLIENT_STATUS_VALUES = ("active", "inactive", "discharged", "deceased", "on_hold")
GENDER_VALUES = ("male", "female", "other", "prefer_not_to_say")
CONTACT_TYPE_VALUES = ("emergency", "primary", "guardian", "power_of_attorney", "physician", "case_manager")
LOCATION_TYPE_VALUES = ("residential", "day_program", "workshop", "community")
PLAN_TYPE_VALUES = ("ISP", "behavior", "medical", "dietary", "therapy")
PLAN_STATUS_VALUES = ("draft", "active", "under_review", "expired", "archived")
NOTE_TYPE_VALUES = ("general", "medical", "behavioral", "incident", "progress")
INSURANCE_TYPE_VALUES = ("primary", "secondary", "tertiary")

class Client(PHIAuditMixin, Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    preferred_name = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=False)
    ssn_encrypted = Column(String(255), nullable=True)
    photo_url = Column(Text, nullable=True)
    status = Column(String(20), default="active", nullable=False)
    admission_date = Column(Date, nullable=False)
    discharge_date = Column(Date, nullable=True)
    primary_diagnosis = Column(Text, nullable=True)
    secondary_diagnoses = Column(JSON, nullable=True)
    allergies = Column(JSON, nullable=True)
    dietary_restrictions = Column(JSON, nullable=True)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint(f"gender IN {GENDER_VALUES}", name="check_client_gender"),
        CheckConstraint(f"status IN {CLIENT_STATUS_VALUES}", name="check_client_status"),
    )

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id])
    user = relationship("User", foreign_keys=[user_id], backref="client_profile")
    creator = relationship("User", foreign_keys=[created_by])
    contacts = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")
    assignments = relationship("ClientAssignment", back_populates="client", cascade="all, delete-orphan")
    programs = relationship("ClientProgram", back_populates="client", cascade="all, delete-orphan")
    care_plans = relationship("CarePlan", back_populates="client", cascade="all, delete-orphan")
    documents = relationship("ClientDocument", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")
    medications = relationship("ClientMedication", back_populates="client", cascade="all, delete-orphan")
    insurance_policies = relationship("ClientInsurance", back_populates="client", cascade="all, delete-orphan")
    vitals_logs = relationship("VitalsLog", back_populates="client", cascade="all, delete-orphan")
    incident_reports = relationship("IncidentReport", back_populates="client", cascade="all, delete-orphan")
    shift_notes = relationship("ShiftNote", back_populates="client", cascade="all, delete-orphan")
    bowel_movement_logs = relationship("BowelMovementLog", back_populates="client", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="client", cascade="all, delete-orphan")
    staff_assignments = relationship("StaffAssignment", foreign_keys="[StaffAssignment.client_id]", cascade="all, delete-orphan", overlaps="client")
    # meal_logs and activity_logs relationships are accessed via queries, not ORM relationships
    # to avoid circular import issues

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    # Audit configuration
    __audit_resource_type__ = "client"
    __audit_phi_fields__ = [
        "first_name", "last_name", "date_of_birth", "ssn", "phone_number",
        "email", "address", "emergency_contact", "medical_information",
        "dietary_restrictions", "notes", "medication_allergies"
    ]
    __audit_exclude_fields__ = ["created_at", "updated_at", "password_hash"]

class ClientContact(Base):
    __tablename__ = "client_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    contact_type = Column(String(20), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    relationship_type = Column(String(100), nullable=True)
    phone_primary = Column(String(20), nullable=False)
    phone_secondary = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    is_primary = Column(Boolean, default=False)
    can_make_decisions = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="contacts")

    __table_args__ = (
        CheckConstraint(f"contact_type IN {CONTACT_TYPE_VALUES}", name="check_contact_type"),
    )

class ClientLocation(Base):
    __tablename__ = "client_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=True)
    type = Column(String(20), nullable=False)
    capacity = Column(Integer, nullable=True)
    current_occupancy = Column(Integer, default=0)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    organization = relationship("Organization", foreign_keys=[organization_id])
    manager = relationship("User", foreign_keys=[manager_id])
    assignments = relationship("ClientAssignment", back_populates="location", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(f"type IN {LOCATION_TYPE_VALUES}", name="check_location_type"),
    )

class ClientAssignment(Base):
    __tablename__ = "client_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("client_locations.id", ondelete="CASCADE"), nullable=False)
    room_number = Column(String(50), nullable=True)
    bed_number = Column(String(50), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="assignments")
    location = relationship("ClientLocation", back_populates="assignments")

class ClientProgram(Base):
    __tablename__ = "client_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    program_id = Column(UUID(as_uuid=True), nullable=False)  # Will link to programs table later
    enrollment_date = Column(Date, nullable=False)
    discharge_date = Column(Date, nullable=True)
    status = Column(String(50), default="enrolled")
    goals = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="programs")

class CarePlan(Base):
    __tablename__ = "care_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    plan_type = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    review_date = Column(Date, nullable=True)
    status = Column(String(20), default="draft", nullable=False)
    goals = Column(JSON, nullable=True)
    interventions = Column(JSON, nullable=True)
    responsible_staff = Column(JSON, nullable=True)  # Array of UUID strings
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    document_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="care_plans")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        CheckConstraint(f"plan_type IN {PLAN_TYPE_VALUES}", name="check_plan_type"),
        CheckConstraint(f"status IN {PLAN_STATUS_VALUES}", name="check_plan_status"),
    )

class ClientDocument(Base):
    __tablename__ = "client_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_url = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    is_confidential = Column(Boolean, default=False)
    expiry_date = Column(Date, nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])

class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    note_type = Column(String(20), nullable=False)
    subject = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_confidential = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="notes")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint(f"note_type IN {NOTE_TYPE_VALUES}", name="check_note_type"),
    )

class ClientMedication(Base):
    __tablename__ = "client_medications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    medication_name = Column(String(255), nullable=False)
    generic_name = Column(String(255), nullable=True)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    route = Column(String(50), nullable=False)
    prescriber_name = Column(String(255), nullable=True)
    prescriber_phone = Column(String(20), nullable=True)
    pharmacy_name = Column(String(255), nullable=True)
    pharmacy_phone = Column(String(20), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    is_prn = Column(Boolean, default=False)
    prn_instructions = Column(Text, nullable=True)
    side_effects = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="medications")

class ClientInsurance(Base):
    __tablename__ = "client_insurance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    insurance_type = Column(String(20), nullable=False)
    company_name = Column(String(255), nullable=False)
    policy_number = Column(String(100), nullable=False)
    group_number = Column(String(100), nullable=True)
    subscriber_name = Column(String(255), nullable=False)
    subscriber_dob = Column(Date, nullable=True)
    subscriber_relationship = Column(String(50), nullable=True)
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=True)
    copay_amount = Column(DECIMAL(10, 2), nullable=True)
    deductible = Column(DECIMAL(10, 2), nullable=True)
    out_of_pocket_max = Column(DECIMAL(10, 2), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    client = relationship("Client", back_populates="insurance_policies")

    __table_args__ = (
        CheckConstraint(f"insurance_type IN {INSURANCE_TYPE_VALUES}", name="check_insurance_type"),
    )