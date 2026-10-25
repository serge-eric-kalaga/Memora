"""Stockage privé interchangeable ; les routes restent responsables des autorisations."""

from pathlib import Path
from botocore.config import Config
from botocore.exceptions import ClientError
import boto3


class LocalStorage:
    """Conserver les fichiers sous une racine locale, sans traversée de chemin."""

    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()

    def _path(self, key: str) -> Path:
        target = (self.directory / key).resolve()
        if (
            not key
            or target == self.directory
            or not target.is_relative_to(self.directory)
        ):
            raise ValueError("Clé de stockage invalide")
        return target

    def put(self, key: str, content: bytes, content_type: str):
        """Écrire un fichier ; le type MIME est utilisé par le stockage distant."""
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def read(self, key: str) -> bytes:
        """Lire le fichier ou lever FileNotFoundError."""
        return self._path(key).read_bytes()

    def delete(self, key: str):
        """Supprimer un fichier ; ignorer une absence déjà effective."""
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    """Utiliser un bucket existant privé AWS S3 ou compatible (par exemple MinIO)."""

    def __init__(self, config):
        if not config.S3_BUCKET:
            raise ValueError("S3_BUCKET est requis pour le stockage S3")
        if bool(config.S3_ACCESS_KEY_ID) != bool(config.S3_SECRET_ACCESS_KEY):
            raise ValueError(
                "Renseigner les deux identifiants S3 ou utiliser le rôle IAM"
            )
        self.bucket = config.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL or None,
            region_name=config.S3_REGION,
            aws_access_key_id=config.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=config.S3_SECRET_ACCESS_KEY or None,
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=10,
                retries={"mode": "standard", "total_max_attempts": 3},
                s3={"addressing_style": config.S3_ADDRESSING_STYLE},
            ),
        )

    def put(self, key: str, content: bytes, content_type: str):
        """Écrire un objet sans ACL publique."""
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=content, ContentType=content_type
        )

    def read(self, key: str) -> bytes:
        """Lire l’objet et libérer la connexion ; distinguer absence et panne."""
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except ClientError as error:
            if error.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                raise FileNotFoundError(key) from None
            raise

    def delete(self, key: str):
        """Supprimer l’objet ; S3 accepte aussi un objet déjà absent."""
        self.client.delete_object(Bucket=self.bucket, Key=key)


def profile_storage(config):
    """Choisir le stockage des photos sans changer les noms enregistrés en SQL."""
    return (
        S3Storage(config)
        if config.STORAGE_BACKEND == "s3"
        else LocalStorage(config.PROFILE_PHOTO_DIR)
    )
