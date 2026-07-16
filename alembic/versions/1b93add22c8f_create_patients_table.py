"""create patients table

Revision ID: 1b93add22c8f
Revises:
Create Date: 2026-07-16 10:29:48.913714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1b93add22c8f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the patients table with constraints + indexes."""
    op.create_table(
        'patients',
        sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('sex', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('phone_number', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('address_line_1', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column('address_line_2', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column('city', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('state', sqlmodel.sql.sqltypes.AutoString(length=2), nullable=False),
        sa.Column('zip_code', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column('insurance_provider', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('insurance_member_id', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=True),
        sa.Column('preferred_language', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False,
                  server_default='English'),
        sa.Column('emergency_contact_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('emergency_contact_phone', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('patient_id'),
        # --- DB-level CHECK constraints (defense in depth alongside Pydantic) ---
        sa.CheckConstraint("sex in ('Male','Female','Other','Decline to Answer')", name='ck_patients_sex'),
        sa.CheckConstraint("phone_number ~ '^\\d{10}$'", name='ck_patients_phone'),
        sa.CheckConstraint("state in ('AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY')", name='ck_patients_state'),
        sa.CheckConstraint("zip_code ~ '^\\d{5}(-\\d{4})?$'", name='ck_patients_zip'),
        sa.CheckConstraint("date_of_birth < current_date", name='ck_patients_dob_not_future'),
        sa.CheckConstraint("emergency_contact_phone is null or emergency_contact_phone ~ '^\\d{10}$'", name='ck_patients_ec_phone'),
    )

    # Indexes for API filter params + duplicate detection
    op.create_index('idx_patients_last_name', 'patients', [sa.text('lower(last_name)')])
    op.create_index('idx_patients_phone', 'patients', ['phone_number'])
    op.create_index('idx_patients_dob', 'patients', ['date_of_birth'])
    op.create_index('idx_patients_deleted_at', 'patients', ['deleted_at'])

    # Auto-update updated_at on row change
    op.execute("""
        create or replace function touch_updated_at()
        returns trigger language plpgsql as $$
        begin
            new.updated_at = now();
            return new;
        end;
        $$;
    """)
    op.execute("""
        create trigger trg_patients_touch
            before update on patients
            for each row execute function touch_updated_at();
    """)

    # Seed data (2 demo patients)
    op.execute("""
        insert into patients (first_name, last_name, date_of_birth, sex, phone_number, email,
                              address_line_1, city, state, zip_code, insurance_provider, insurance_member_id)
        values
            ('Jane', 'Doe', '1985-04-12', 'Female', '5551234567', 'jane.doe@example.com',
             '123 Maple Street', 'Springfield', 'IL', '62704', 'Blue Cross Blue Shield', 'BCBS123456789'),
            ('John', 'Smith', '1979-11-30', 'Male', '5559876543', null,
             '456 Oak Avenue', 'Madison', 'WI', '53703', null, null);
    """)


def downgrade() -> None:
    """Drop the patients table."""
    op.execute("drop trigger if exists trg_patients_touch on patients")
    op.execute("drop function if exists touch_updated_at()")
    op.drop_table('patients')
