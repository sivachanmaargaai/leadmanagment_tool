from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


@contextmanager
def database_operation(db):
    try:
        yield
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="These changes conflict with existing database records") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database operation unavailable. Please retry") from None
