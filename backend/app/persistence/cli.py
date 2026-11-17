"""Command-line entry point for database initialization."""

from app.persistence.database import DatabaseManager
from app.persistence.seed import seed_default_case


def main() -> None:
    manager = DatabaseManager()
    results = manager.initialize()
    default_case = seed_default_case(manager)

    print("TheraSim databases initialized successfully.")
    print(f"Data directory: {manager.data_dir}")
    print(f"Operational database: {manager.path_for('operational')}")
    print(f"Restricted database: {manager.path_for('restricted')}")

    for database, migrations in results.items():
        print(f"{database}: {', '.join(migrations)}")

    print(
        "Default case seeded: "
        f"{default_case['case_code']} ({default_case['case_id']})"
    )


if __name__ == "__main__":
    main()
