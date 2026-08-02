import winreg
import json
import os
import logging
import hashlib
from datetime import datetime
from typing import Optional


# ============================================================
# CONFIGURATION
# ============================================================

LOG_FILE = "registry_manager.log"
BACKUP_FILE = "registry_backup.json"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("RegistryManager")


# ============================================================
# REGISTRY ROOT MAPPING
# ============================================================

ROOT_KEYS = {

    "HKCU": winreg.HKEY_CURRENT_USER,

    "HKLM": winreg.HKEY_LOCAL_MACHINE,

    "HKCR": winreg.HKEY_CLASSES_ROOT,

    "HKU": winreg.HKEY_USERS,

    "HKCC": winreg.HKEY_CURRENT_CONFIG
}


# ============================================================
# REGISTRY TYPE MAPPING
# ============================================================

REGISTRY_TYPES = {

    "string": winreg.REG_SZ,

    "expand_string": winreg.REG_EXPAND_SZ,

    "integer": winreg.REG_DWORD,

    "binary": winreg.REG_BINARY,

    "multi_string": winreg.REG_MULTI_SZ
}


# ============================================================
# REGISTRY MANAGER
# ============================================================

class RegistryManager:

    def __init__(self):

        self.session_id = self.generate_session_id()

        logger.info(
            "Registry manager initialized: %s",
            self.session_id
        )


    # --------------------------------------------------------
    # SESSION ID
    # --------------------------------------------------------

    def generate_session_id(self):

        raw = (
            str(datetime.now())
            + os.getenv(
                "COMPUTERNAME",
                "UNKNOWN"
            )
        )

        return hashlib.sha256(
            raw.encode()
        ).hexdigest()[:16]


    # --------------------------------------------------------
    # PARSE REGISTRY PATH
    # --------------------------------------------------------

    def parse_path(self, path):

        path = path.strip()

        path = path.replace(
            "/",
            "\\"
        )

        parts = path.split(
            "\\",
            1
        )

        if len(parts) == 1:

            root_name = parts[0]

            subkey = ""

        else:

            root_name = parts[0]

            subkey = parts[1]

        root_name = root_name.upper()

        if root_name not in ROOT_KEYS:

            raise ValueError(
                f"Unsupported registry root: {root_name}"
            )

        return (
            ROOT_KEYS[root_name],
            root_name,
            subkey
        )


    # --------------------------------------------------------
    # OPEN KEY
    # --------------------------------------------------------

    def open_key(
        self,
        path,
        access=winreg.KEY_READ
    ):

        root, root_name, subkey = (
            self.parse_path(path)
        )

        logger.info(
            "Opening registry key: %s",
            path
        )

        return winreg.OpenKey(
            root,
            subkey,
            0,
            access
        )


    # --------------------------------------------------------
    # READ VALUE
    # --------------------------------------------------------

    def read_value(
        self,
        path,
        value_name
    ):

        try:

            with self.open_key(
                path
            ) as key:

                value, value_type = (
                    winreg.QueryValueEx(
                        key,
                        value_name
                    )
                )

            logger.info(
                "Read value: %s -> %s",
                value_name,
                path
            )

            return {
                "name": value_name,
                "value": value,
                "type": value_type,
                "path": path
            }

        except FileNotFoundError:

            logger.warning(
                "Registry value not found: %s",
                value_name
            )

            return None

        except PermissionError:

            logger.error(
                "Permission denied: %s",
                path
            )

            return None


    # --------------------------------------------------------
    # WRITE VALUE
    # --------------------------------------------------------

    def write_value(
        self,
        path,
        value_name,
        value,
        value_type="string"
    ):

        if value_type not in REGISTRY_TYPES:

            raise ValueError(
                "Unsupported registry type"
            )

        registry_type = (
            REGISTRY_TYPES[value_type]
        )

        try:

            root, root_name, subkey = (
                self.parse_path(path)
            )

            with winreg.CreateKeyEx(
                root,
                subkey,
                0,
                winreg.KEY_WRITE
            ) as key:

                winreg.SetValueEx(
                    key,
                    value_name,
                    0,
                    registry_type,
                    value
                )

            logger.info(
                "Registry value written: %s",
                path
            )

            return True

        except PermissionError:

            logger.error(
                "Write permission denied: %s",
                path
            )

            return False


    # --------------------------------------------------------
    # DELETE VALUE
    # --------------------------------------------------------

    def delete_value(
        self,
        path,
        value_name
    ):

        try:

            with self.open_key(
                path,
                winreg.KEY_SET_VALUE
            ) as key:

                winreg.DeleteValue(
                    key,
                    value_name
                )

            logger.info(
                "Deleted registry value: %s",
                value_name
            )

            return True

        except FileNotFoundError:

            return False

        except PermissionError:

            logger.error(
                "Delete permission denied"
            )

            return False


    # --------------------------------------------------------
    # LIST VALUES
    # --------------------------------------------------------

    def list_values(
        self,
        path
    ):

        results = []

        try:

            with self.open_key(
                path
            ) as key:

                index = 0

                while True:

                    try:

                        name, value, value_type = (
                            winreg.EnumValue(
                                key,
                                index
                            )
                        )

                        results.append({

                            "name": name,

                            "value": value,

                            "type": value_type

                        })

                        index += 1

                    except OSError:

                        break

        except Exception as error:

            logger.error(
                "Unable to list values: %s",
                error
            )

        return results


    # --------------------------------------------------------
    # LIST SUBKEYS
    # --------------------------------------------------------

    def list_subkeys(
        self,
        path
    ):

        results = []

        try:

            with self.open_key(
                path
            ) as key:

                index = 0

                while True:

                    try:

                        subkey = (
                            winreg.EnumKey(
                                key,
                                index
                            )
                        )

                        results.append(
                            subkey
                        )

                        index += 1

                    except OSError:

                        break

        except Exception as error:

            logger.error(
                "Unable to list subkeys: %s",
                error
            )

        return results


    # --------------------------------------------------------
    # SEARCH REGISTRY
    # --------------------------------------------------------

    def search(
        self,
        path,
        keyword,
        depth=2
    ):

        matches = []

        if depth < 0:

            return matches

        try:

            values = self.list_values(
                path
            )

            for item in values:

                name = str(
                    item["name"]
                ).lower()

                value = str(
                    item["value"]
                ).lower()

                if (
                    keyword.lower()
                    in name
                    or
                    keyword.lower()
                    in value
                ):

                    matches.append({

                        "path": path,

                        "name":
                            item["name"],

                        "value":
                            item["value"]

                    })


            subkeys = self.list_subkeys(
                path
            )

            for subkey in subkeys:

                if depth <= 0:

                    continue

                child_path = (
                    path
                    + "\\"
                    + subkey
                )

                matches.extend(
                    self.search(
                        child_path,
                        keyword,
                        depth - 1
                    )
                )

        except Exception as error:

            logger.debug(
                "Search error: %s",
                error
            )

        return matches


    # --------------------------------------------------------
    # EXPORT KEY
    # --------------------------------------------------------

    def export_key(
        self,
        path
    ):

        values = self.list_values(
            path
        )

        subkeys = self.list_subkeys(
            path
        )

        data = {

            "path": path,

            "values": values,

            "subkeys": subkeys,

            "exported_at":
                datetime.now().isoformat()

        }

        return data


    # --------------------------------------------------------
    # BACKUP
    # --------------------------------------------------------

    def backup(
        self,
        path,
        filename=BACKUP_FILE
    ):

        data = self.export_key(
            path
        )

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                default=str
            )

        logger.info(
            "Registry backup created: %s",
            filename
        )

        return filename


    # --------------------------------------------------------
    # DISPLAY KEY
    # --------------------------------------------------------

    def display(
        self,
        path
    ):

        print("\n" + "=" * 60)

        print(
            "REGISTRY:",
            path
        )

        print("=" * 60)

        values = self.list_values(
            path
        )

        if not values:

            print(
                "No values found."
            )

        for item in values:

            print(
                f"{item['name']} = "
                f"{item['value']}"
            )

        print("\nSubkeys:")

        for subkey in self.list_subkeys(
            path
        ):

            print(
                "  ",
                subkey
            )


# ============================================================
# COMMAND ROUTER
# ============================================================

class RegistryCommandRouter:

    def __init__(self):

        self.manager = RegistryManager()


    # --------------------------------------------------------
    # ROUTE COMMAND
    # --------------------------------------------------------

    def route(
        self,
        command,
        **kwargs
    ):

        routes = {

            "read":
                self.read_handler,

            "write":
                self.write_handler,

            "delete":
                self.delete_handler,

            "list":
                self.list_handler,

            "search":
                self.search_handler,

            "backup":
                self.backup_handler,

            "display":
                self.display_handler
        }

        handler = routes.get(
            command.lower()
        )

        if handler is None:

            raise ValueError(
                "Unknown registry command"
            )

        return handler(
            **kwargs
        )


    # --------------------------------------------------------
    # HANDLERS
    # --------------------------------------------------------

    def read_handler(
        self,
        path,
        value_name
    ):

        return self.manager.read_value(
            path,
            value_name
        )


    def write_handler(
        self,
        path,
        value_name,
        value,
        value_type="string"
    ):

        return self.manager.write_value(
            path,
            value_name,
            value,
            value_type
        )


    def delete_handler(
        self,
        path,
        value_name
    ):

        return self.manager.delete_value(
            path,
            value_name
        )


    def list_handler(
        self,
        path
    ):

        return {

            "values":
                self.manager.list_values(
                    path
                ),

            "subkeys":
                self.manager.list_subkeys(
                    path
                )
        }


    def search_handler(
        self,
        path,
        keyword,
        depth=2
    ):

        return self.manager.search(
            path,
            keyword,
            depth
        )


    def backup_handler(
        self,
        path,
        filename=BACKUP_FILE
    ):

        return self.manager.backup(
            path,
            filename
        )


    def display_handler(
        self,
        path
    ):

        return self.manager.display(
            path
        )


# ============================================================
# AI COMMAND INTERFACE
# ============================================================

class RegistryAIInterface:

    def __init__(self):

        self.router = (
            RegistryCommandRouter()
        )


    # --------------------------------------------------------
    # INTERPRET NATURAL LANGUAGE
    # --------------------------------------------------------

    def interpret(
        self,
        command
    ):

        command = command.lower()

        if "read" in command:

            return "read"

        if "search" in command:

            return "search"

        if "backup" in command:

            return "backup"

        if "delete" in command:

            return "delete"

        if "write" in command:

            return "write"

        if "list" in command:

            return "list"

        return "display"


# ============================================================
# SECURITY VALIDATOR
# ============================================================

class RegistrySecurity:

    ALLOWED_ROOTS = {

        "HKCU",

        "HKLM",

        "HKCR",

        "HKU",

        "HKCC"
    }


    def validate_path(
        self,
        path
    ):

        root = path.split(
            "\\",
            1
        )[0].upper()

        if root not in self.ALLOWED_ROOTS:

            raise PermissionError(
                "Invalid registry root"
            )

        return True


    def validate_operation(
        self,
        operation
    ):

        allowed = {

            "read",
            "write",
            "delete",
            "list",
            "search",
            "backup",
            "display"
        }

        if operation not in allowed:

            raise PermissionError(
                "Operation not permitted"
            )

        return True


# ============================================================
# EXAMPLE USAGE
# ============================================================

def main():

    registry = RegistryManager()

    security = RegistrySecurity()

    router = RegistryCommandRouter()


    # --------------------------------------------------------
    # Example registry path
    # --------------------------------------------------------

    path = (
        r"HKCU\Software\MyDesktopAgent"
    )


    # --------------------------------------------------------
    # Validate path
    # --------------------------------------------------------

    security.validate_path(
        path
    )


    # --------------------------------------------------------
    # Create application setting
    # --------------------------------------------------------

    router.route(

        "write",

        path=path,

        value_name="AgentEnabled",

        value="true",

        value_type="string"
    )


    # --------------------------------------------------------
    # Write numeric configuration
    # --------------------------------------------------------

    router.route(

        "write",

        path=path,

        value_name="MaxTokens",

        value=2048,

        value_type="integer"
    )


    # --------------------------------------------------------
    # Read value
    # --------------------------------------------------------

    result = router.route(

        "read",

        path=path,

        value_name="AgentEnabled"
    )


    print(
        "\nRead result:"
    )

    print(
        result
    )


    # --------------------------------------------------------
    # List registry values
    # --------------------------------------------------------

    result = router.route(

        "list",

        path=path
    )


    print(
        "\nRegistry contents:"
    )

    print(
        json.dumps(
            result,
            indent=4,
            default=str
        )
    )


    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    results = router.route(

        "search",

        path=r"HKCU\Software",

        keyword="agent",

        depth=2
    )


    print(
        "\nSearch results:"
    )

    for item in results:

        print(
            item
        )


    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    backup_file = router.route(

        "backup",

        path=path,

        filename="agent_registry_backup.json"
    )


    print(
        "\nBackup:",
        backup_file
    )


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except PermissionError as error:

        print(
            "Permission error:",
            error
        )

        logger.error(
            "Permission error: %s",
            error
        )

    except Exception as error:

        print(
            "Unexpected error:",
            error
        )

        logger.exception(
            "Unexpected error"
        )
