from setuptools import setup, find_packages

setup(
    name="scheduler-py",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "pytest>=8.3.5",
        "pydantic>=2.0.0",
        "fastapi>=0.100.0",
        "sqlalchemy>=2.0.0",
        "datetime",
        "typing",
        "ortools>=9.0",
        "requests",
        "python-dotenv",
    ],
    entry_points={
        'console_scripts': [
            # Define any command-line scripts here
        ],
    },
) 