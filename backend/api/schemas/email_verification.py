"""Contrats publics du parcours de confirmation d’adresse."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class ResendConfirmation(BaseModel):
    """Demande publique, sans indication sur l’existence d’un compte."""

    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(
        max_length=254, description="Adresse du compte à confirmer."
    )
    language: Literal["fr", "en"] = Field(
        default="fr", description="Langue du message envoyé."
    )


class ConfirmEmail(BaseModel):
    """Secret reçu par e-mail, jamais retourné par l’API."""

    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(
        min_length=43,
        max_length=43,
        description="Jeton de confirmation temporaire à usage unique.",
    )


class AuthConfiguration(BaseModel):
    """Options publiques que le frontend utilise pour adapter l’inscription."""

    email_verification_enabled: bool = Field(
        description="Exiger une confirmation de l’adresse avant la connexion des nouveaux comptes."
    )
