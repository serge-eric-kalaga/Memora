"""Validation, stockage et remplacement transactionnel des photos de profil."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4
import logging
import re

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from api.database import User
from api.services.storage import profile_storage
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)
_ALLOWED_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_FILENAME = re.compile(r"[0-9a-f]{32}\.webp\Z")


def photo_path(directory: Path, filename: str) -> Path:
    """Résoudre uniquement les noms générés par l’application, sans traversée de chemin."""
    if not _FILENAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return directory / filename


def _normalize(upload: UploadFile, config) -> bytes:
    """Valider une image fixe de taille limitée et la réencoder sans métadonnées."""
    if upload.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Formats acceptés : JPEG, PNG et WebP")
    content = upload.file.read(config.PROFILE_PHOTO_MAX_BYTES + 1)
    if len(content) > config.PROFILE_PHOTO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Photo trop volumineuse")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != _ALLOWED_TYPES[upload.content_type]:
                raise HTTPException(status_code=415, detail="Le contenu ne correspond pas au type d’image annoncé")
            if image.width * image.height > config.PROFILE_PHOTO_MAX_PIXELS:
                raise HTTPException(status_code=413, detail="Dimensions de la photo trop importantes")
            if getattr(image, "n_frames", 1) != 1:
                raise HTTPException(status_code=415, detail="Les images animées ne sont pas acceptées")
            image.verify()
        with Image.open(BytesIO(content)) as image:
            oriented = ImageOps.exif_transpose(image)
            oriented.thumbnail((1024, 1024))
            normalized = oriented.convert("RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB")
            # Copie des pixels uniquement : ni EXIF, ni ICC, ni commentaire utilisateur.
            clean = Image.new(normalized.mode, normalized.size)
            clean.paste(normalized)
            output = BytesIO()
            clean.save(output, format="WEBP", quality=85)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Fichier image invalide ou illisible") from None


def _remove(config, filename: str | None):
    """Supprimer une ancienne photo sans annuler une écriture SQL déjà validée."""
    if filename:
        try:
            photo_path(config.PROFILE_PHOTO_DIR, filename)
            profile_storage(config).delete(filename)
        except (OSError, HTTPException, BotoCoreError, ClientError, ValueError):
            logger.warning("Impossible de supprimer une ancienne photo de profil")


def update_profile_photo(
    db: Session, username: str, upload: UploadFile, config
) -> User:
    """Remplacer la photo du compte connecté et conserver l’ancienne en cas d’échec SQL."""
    content = _normalize(upload, config)
    user = db.query(User).filter_by(username=username).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    storage = profile_storage(config)
    filename = f"{uuid4().hex}.webp"
    previous = user.profile_photo
    try:
        storage.put(filename, content, "image/webp")
        user.profile_photo = filename
        db.commit()
    except Exception:
        db.rollback()
        _remove(config, filename)
        raise
    _remove(config, previous)
    db.refresh(user)
    return user


def read_profile_photo(db: Session, username: str, config) -> bytes:
    """Lire la photo enregistrée d’un utilisateur ou retourner HTTP 404."""
    user = User.get(username=username, db=db)
    if not user.profile_photo:
        raise HTTPException(status_code=404, detail="Aucune photo de profil")
    try:
        photo_path(config.PROFILE_PHOTO_DIR, user.profile_photo)
        return profile_storage(config).read(user.profile_photo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Photo introuvable") from None


def remove_profile_photo_file(user: User, config):
    """Nettoyer la photo d’un compte après la suppression de sa ligne en base."""
    _remove(config, user.profile_photo)
