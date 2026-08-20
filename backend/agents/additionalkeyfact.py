import os
import json
import base64
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

KEY_DIRECTORY = "keys"
KEY_DATABASE = os.path.join(
    KEY_DIRECTORY,
    "key_registry.json"
)

KEY_SIZE = 32
KEY_ROTATION_DAYS = 30


# ============================================================
# KEY FACTORY
# ============================================================

class KeyFactory:

    def __init__(self):

        self.create_key_directory()

        self.registry = self.load_registry()


    # --------------------------------------------------------
    # CREATE KEY DIRECTORY
    # --------------------------------------------------------

    def create_key_directory(self):

        if not os.path.exists(
            KEY_DIRECTORY
        ):

            os.makedirs(
                KEY_DIRECTORY
            )


    # --------------------------------------------------------
    # LOAD KEY REGISTRY
    # --------------------------------------------------------

    def load_registry(self):

        if not os.path.exists(
            KEY_DATABASE
        ):

            return {
                "keys": []
            }

        try:

            with open(
                KEY_DATABASE,
                "r"
            ) as file:

                return json.load(file)

        except Exception:

            return {
                "keys": []
            }


    # --------------------------------------------------------
    # SAVE REGISTRY
    # --------------------------------------------------------

    def save_registry(self):

        with open(
            KEY_DATABASE,
            "w"
        ) as file:

            json.dump(
                self.registry,
                file,
                indent=4
            )


    # --------------------------------------------------------
    # GENERATE RANDOM KEY
    # --------------------------------------------------------

    def generate_secret(self):

        return secrets.token_bytes(
            KEY_SIZE
        )


    # --------------------------------------------------------
    # ENCODE KEY
    # --------------------------------------------------------

    def encode_key(
        self,
        key
    ):

        return base64.urlsafe_b64encode(
            key
        ).decode()


    # --------------------------------------------------------
    # GENERATE KEY ID
    # --------------------------------------------------------

    def generate_key_id(
        self,
        key
    ):

        fingerprint = hashlib.sha256(
            key
        ).hexdigest()

        return fingerprint[:16]


    # --------------------------------------------------------
    # CREATE NEW KEY
    # --------------------------------------------------------

    def create_key(
        self,
        purpose="authentication"
    ):

        raw_key = self.generate_secret()

        encoded_key = self.encode_key(
            raw_key
        )

        key_id = self.generate_key_id(
            raw_key
        )

        created = datetime.utcnow()

        expires = (
            created
            + timedelta(
                days=KEY_ROTATION_DAYS
            )
        )

        key_record = {

            "key_id":
                key_id,

            "purpose":
                purpose,

            "algorithm":
                "HMAC-SHA256",

            "created_at":
                created.isoformat(),

            "expires_at":
                expires.isoformat(),

            "status":
                "active",

            "key":
                encoded_key
        }

        self.registry[
            "keys"
        ].append(
            key_record
        )

        self.save_registry()

        return key_record


    # --------------------------------------------------------
    # FIND ACTIVE KEY
    # --------------------------------------------------------

    def get_active_key(
        self,
        purpose="authentication"
    ):

        current_time = datetime.utcnow()

        candidates = []

        for key in self.registry["keys"]:

            if key["purpose"] != purpose:
                continue

            if key["status"] != "active":
                continue

            expiration = datetime.fromisoformat(
                key["expires_at"]
            )

            if expiration > current_time:

                candidates.append(
                    key
                )


        if not candidates:

            return self.create_key(
                purpose
            )


        candidates.sort(
            key=lambda x: x["created_at"],
            reverse=True
        )

        return candidates[0]


    # --------------------------------------------------------
    # DECODE KEY
    # --------------------------------------------------------

    def decode_key(
        self,
        key_record
    ):

        return base64.urlsafe_b64decode(
            key_record["key"]
        )


    # --------------------------------------------------------
    # ROTATE KEYS
    # --------------------------------------------------------

    def rotate_key(
        self,
        purpose="authentication"
    ):

        for key in self.registry["keys"]:

            if key["purpose"] == purpose:

                key["status"] = "retired"


        new_key = self.create_key(
            purpose
        )

        return new_key


    # --------------------------------------------------------
    # REVOKE KEY
    # --------------------------------------------------------

    def revoke_key(
        self,
        key_id
    ):

        for key in self.registry["keys"]:

            if key["key_id"] == key_id:

                key["status"] = "revoked"

                self.save_registry()

                return True

        return False


    # --------------------------------------------------------
    # LIST KEYS
    # --------------------------------------------------------

    def list_keys(self):

        results = []

        for key in self.registry["keys"]:

            results.append({

                "key_id":
                    key["key_id"],

                "purpose":
                    key["purpose"],

                "algorithm":
                    key["algorithm"],

                "created_at":
                    key["created_at"],

                "expires_at":
                    key["expires_at"],

                "status":
                    key["status"]

            })

        return results


# ============================================================
# TOKEN SERVICE
# ============================================================

class TokenService:

    def __init__(
        self,
        key_factory
    ):

        self.key_factory = (
            key_factory
        )


    # --------------------------------------------------------
    # CREATE SIGNATURE
    # --------------------------------------------------------

    def sign(
        self,
        payload
    ):

        key_record = (
            self.key_factory
            .get_active_key(
                "authentication"
            )
        )

        secret = (
            self.key_factory
            .decode_key(
                key_record
            )
        )

        message = json.dumps(
            payload,
            sort_keys=True
        ).encode()

        signature = hmac.new(
            secret,
            message,
            hashlib.sha256
        ).digest()

        return {

            "key_id":
                key_record["key_id"],

            "payload":
                payload,

            "signature":
                base64.urlsafe_b64encode(
                    signature
                ).decode()

        }


    # --------------------------------------------------------
    # VERIFY SIGNATURE
    # --------------------------------------------------------

    def verify(
        self,
        token
    ):

        key_id = token[
            "key_id"
        ]

        selected_key = None

        for key in (
            self.key_factory.registry[
                "keys"
            ]
        ):

            if key["key_id"] == key_id:

                selected_key = key

                break


        if selected_key is None:

            return False


        if selected_key["status"] == "revoked":

            return False


        secret = (
            self.key_factory
            .decode_key(
                selected_key
            )
        )

        message = json.dumps(
            token["payload"],
            sort_keys=True
        ).encode()

        expected = hmac.new(
            secret,
            message,
            hashlib.sha256
        ).digest()

        received = (
            base64.urlsafe_b64decode(
                token["signature"]
            )
        )

        return hmac.compare_digest(
            expected,
            received
        )


# ============================================================
# AUTHENTICATION SERVICE
# ============================================================

class AuthenticationService:

    def __init__(self):

        self.key_factory = (
            KeyFactory()
        )

        self.token_service = (
            TokenService(
                self.key_factory
            )
        )


    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    def login(
        self,
        username,
        password
    ):

        # Example credentials.
        # A real application should use a
        # persistent user database.

        valid_users = {

            "admin":
                "admin123",

            "user":
                "user123"

        }

        if username not in valid_users:

            return None


        if not hmac.compare_digest(
            password,
            valid_users[username]
        ):

            return None


        payload = {

            "username":
                username,

            "role":
                "admin"
                if username == "admin"
                else "user",

            "issued_at":
                datetime.utcnow().isoformat()

        }


        token = (
            self.token_service
            .sign(
                payload
            )
        )

        return token


    # --------------------------------------------------------
    # VERIFY LOGIN
    # --------------------------------------------------------

    def verify_session(
        self,
        token
    ):

        return (
            self.token_service
            .verify(
                token
            )
        )


# ============================================================
# APPLICATION
# ============================================================

def main():

    print(
        "=" * 60
    )

    print(
        "        OFFLINE KEY FACTORY"
    )

    print(
        "=" * 60
    )


    # --------------------------------------------------------
    # Initialize factory
    # --------------------------------------------------------

    factory = KeyFactory()


    # --------------------------------------------------------
    # Generate authentication key
    # --------------------------------------------------------

    key = factory.get_active_key(
        "authentication"
    )

    print(
        "\nActive Key ID:",
        key["key_id"]
    )

    print(
        "Algorithm:",
        key["algorithm"]
    )

    print(
        "Expires:",
        key["expires_at"]
    )


    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    auth = AuthenticationService()


    token = auth.login(
        "admin",
        "admin123"
    )


    if token:

        print(
            "\nLogin successful."
        )

        print(
            "Key ID:",
            token["key_id"]
        )


        # ----------------------------------------------------
        # Verify token
        # ----------------------------------------------------

        valid = auth.verify_session(
            token
        )


        print(
            "Token valid:",
            valid
        )


    else:

        print(
            "\nLogin failed."
        )


    # --------------------------------------------------------
    # Display registered keys
    # --------------------------------------------------------

    print(
        "\nRegistered Keys:"
    )

    for item in factory.list_keys():

        print(
            item
        )


    # --------------------------------------------------------
    # Example key rotation
    # --------------------------------------------------------

    print(
        "\nRotating authentication key..."
    )

    new_key = factory.rotate_key(
        "authentication"
    )

    print(
        "New Key ID:",
        new_key["key_id"]
    )


# ============================================================
# PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":

    main()
