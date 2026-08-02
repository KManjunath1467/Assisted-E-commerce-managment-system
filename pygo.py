import os
import json
import shutil
import datetime
import random
import string

DATA_FILE = "file_database.json"
BACKUP_FOLDER = "backup"


def load_database():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except Exception:
        return []


def save_database(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def generate_id():
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choice(characters) for _ in range(8))


def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_file(database):
    print("\n--- Add File ---")

    name = input("Enter file name: ")
    category = input("Enter category: ")
    description = input("Enter description: ")

    file_record = {
        "id": generate_id(),
        "name": name,
        "category": category,
        "description": description,
        "created_at": get_current_time(),
        "size": random.randint(10, 5000),
        "status": "active"
    }

    database.append(file_record)
    save_database(database)

    print("\nFile added successfully.")
    print("Generated ID:", file_record["id"])


def display_file(file_record):
    print("-" * 50)
    print("ID          :", file_record["id"])
    print("Name        :", file_record["name"])
    print("Category    :", file_record["category"])
    print("Description :", file_record["description"])
    print("Created     :", file_record["created_at"])
    print("Size        :", file_record["size"], "KB")
    print("Status      :", file_record["status"])
    print("-" * 50)


def list_files(database):
    print("\n--- All Files ---")

    if not database:
        print("No files available.")
        return

    for file_record in database:
        display_file(file_record)


def search_file(database):
    print("\n--- Search File ---")

    keyword = input("Enter file name or category: ").lower()

    found = False

    for file_record in database:
        if (keyword in file_record["name"].lower()
                or keyword in file_record["category"].lower()):

            display_file(file_record)
            found = True

    if not found:
        print("No matching files found.")


def find_by_id(database):
    file_id = input("Enter file ID: ").upper()

    for file_record in database:
        if file_record["id"] == file_id:
            return file_record

    return None


def update_file(database):
    print("\n--- Update File ---")

    file_record = find_by_id(database)

    if file_record is None:
        print("File not found.")
        return

    print("Leave a field empty to keep the old value.")

    name = input("New name: ")
    category = input("New category: ")
    description = input("New description: ")

    if name:
        file_record["name"] = name

    if category:
        file_record["category"] = category

    if description:
        file_record["description"] = description

    save_database(database)

    print("File updated successfully.")


def delete_file(database):
    print("\n--- Delete File ---")

    file_record = find_by_id(database)

    if file_record is None:
        print("File not found.")
        return

    print("\nFile selected:")
    display_file(file_record)

    confirmation = input("Delete this file? (yes/no): ")

    if confirmation.lower() == "yes":
        database.remove(file_record)
        save_database(database)
        print("File deleted successfully.")
    else:
        print("Delete operation cancelled.")


def change_status(database):
    print("\n--- Change File Status ---")

    file_record = find_by_id(database)

    if file_record is None:
        print("File not found.")
        return

    print("Current status:", file_record["status"])

    print("\n1. Active")
    print("2. Archived")
    print("3. Hidden")

    choice = input("Choose status: ")

    if choice == "1":
        file_record["status"] = "active"
    elif choice == "2":
        file_record["status"] = "archived"
    elif choice == "3":
        file_record["status"] = "hidden"
    else:
        print("Invalid choice.")
        return

    save_database(database)

    print("Status updated.")


def create_backup():
    print("\n--- Creating Backup ---")

    if not os.path.exists(DATA_FILE):
        print("Database does not exist.")
        return

    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_name = f"database_backup_{timestamp}.json"

    destination = os.path.join(
        BACKUP_FOLDER,
        backup_name
    )

    shutil.copy(DATA_FILE, destination)

    print("Backup created:")
    print(destination)


def statistics(database):
    print("\n--- File Statistics ---")

    total = len(database)

    active = 0
    archived = 0
    hidden = 0
    total_size = 0

    for file_record in database:

        status = file_record["status"]

        if status == "active":
            active += 1

        elif status == "archived":
            archived += 1

        elif status == "hidden":
            hidden += 1

        total_size += file_record["size"]

    print("Total files     :", total)
    print("Active files    :", active)
    print("Archived files  :", archived)
    print("Hidden files    :", hidden)
    print("Total size      :", total_size, "KB")


def generate_sample_data(database):
    print("\n--- Generating Sample Data ---")

    categories = [
        "Documents",
        "Images",
        "Projects",
        "Reports",
        "Assignments"
    ]

    names = [
        "resume.pdf",
        "project.docx",
        "photo.jpg",
        "report.pdf",
        "assignment.txt",
        "notes.docx",
        "presentation.pptx",
        "data.csv"
    ]

    for i in range(5):

        record = {
            "id": generate_id(),
            "name": random.choice(names),
            "category": random.choice(categories),
            "description": "Sample generated file",
            "created_at": get_current_time(),
            "size": random.randint(100, 5000),
            "status": random.choice(
                ["active", "active", "archived"]
            )
        }

        database.append(record)

    save_database(database)

    print("Sample data generated.")


def menu():
    print("\n")
    print("=" * 50)
    print("        FILE MANAGEMENT SYSTEM")
    print("=" * 50)
    print("1. Add File")
    print("2. List Files")
    print("3. Search File")
    print("4. Update File")
    print("5. Delete File")
    print("6. Change File Status")
    print("7. Create Backup")
    print("8. View Statistics")
    print("9. Generate Sample Data")
    print("0. Exit")
    print("=" * 50)


def main():
    database = load_database()

    while True:

        menu()

        choice = input("Enter your choice: ")

        if choice == "1":
            add_file(database)

        elif choice == "2":
            list_files(database)

        elif choice == "3":
            search_file(database)

        elif choice == "4":
            update_file(database)

        elif choice == "5":
            delete_file(database)

        elif choice == "6":
            change_status(database)

        elif choice == "7":
            create_backup()

        elif choice == "8":
            statistics(database)

        elif choice == "9":
            generate_sample_data(database)

        elif choice == "0":
            print("\nExiting program...")
            break

        else:
            print("\nInvalid choice. Please try again.")


if __name__ == "__main__":
    main()
