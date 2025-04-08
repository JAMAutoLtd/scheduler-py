import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Determine Database URL based on TESTING environment variable
if os.environ.get("TESTING"):
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    # SQLite specific configuration for testing
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Import settings only when not testing to avoid circular dependencies potentially
    from scheduler.api.deps import get_settings
    settings = get_settings()
    SQLALCHEMY_DATABASE_URL = settings["database_url"]
    # Create the SQLAlchemy engine for the actual database
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a SessionLocal class
# Each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class 
# All SQLAlchemy models will inherit from this class
Base = declarative_base()

# Function to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 