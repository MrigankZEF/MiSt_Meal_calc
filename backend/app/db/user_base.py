from sqlalchemy.orm import DeclarativeBase


class UserBase(DeclarativeBase):
    """Declarative base for user-DB models (Postgres).

    Kept separate from the reference-DB Base so SQLAlchemy never confuses
    the two engines.  All models in app/models/user.py inherit from this.
    """
