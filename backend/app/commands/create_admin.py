"""Run locally: python -m app.commands.create_admin. Passwords are never command arguments."""
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import passwords
from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.auth import LoginRequest


def main():
    print("Create an ENGEN CRM administrator. No default login accounts are installed.")
    try:
        email = input("Email: ")
        name = input("Display name: ").strip()
        password = getpass("Password (8-128 characters): ")
        confirm = getpass("Confirm password: ")
        if not name or len(name) > 120 or not 8 <= len(password) <= 128 or password != confirm:
            raise SystemExit("Name/password validation failed; no account created.")
        details = LoginRequest(email=email, password=password)
        with SessionLocal.begin() as db:
            if db.scalar(select(User.id).where(User.is_owner.is_(True))) is not None:
                raise SystemExit("The Owner account already exists. Use Settings > Users & access to manage login accounts.")
            if db.scalar(select(User.id).where(User.email == details.email)) is not None:
                raise SystemExit("An account with that email already exists; it was not changed.")
            db.add(User(email=details.email, name=name, password_hash=passwords.hash(password), role="Admin", is_owner=True, admin_slot=1))
        print("Administrator created. Sign in using the email and password you entered.")
    except ValidationError:
        raise SystemExit("Enter a valid email address; no account created.") from None
    except SQLAlchemyError:
        raise SystemExit("Account creation failed. Check the database connection and apply migrations first.") from None
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Cancelled; no account created.") from None


if __name__ == "__main__":
    main()
