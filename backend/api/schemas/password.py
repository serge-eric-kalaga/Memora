"""Contrats privés de gestion des identifiants et de récupération de compte."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class CredentialsInput(BaseModel):
    """Interdire les champs supplémentaires pour les opérations sensibles."""

    model_config = ConfigDict(extra="forbid")


class ChangePassword(CredentialsInput):
    """Vérifier le mot de passe actuel avant de révoquer toutes les sessions."""

    current_password: SecretStr = Field(
        min_length=1, max_length=128, description="Mot de passe actuel du compte."
    )
    new_password: SecretStr = Field(
        min_length=8,
        max_length=128,
        description="Nouveau mot de passe (8 à 128 caractères).",
    )


class ChangeEmail(CredentialsInput):
    """Associer une adresse de récupération après réauthentification."""

    email: EmailStr = Field(
        max_length=254, description="Adresse e-mail unique de récupération."
    )
    current_password: SecretStr = Field(
        min_length=1,
        max_length=128,
        description="Mot de passe actuel, requis pour changer l’adresse.",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value):
        """Utiliser la même forme canonique pour l’unicité et la récupération."""
        return str(value).lower()


class ForgotPassword(CredentialsInput):
    """Demande publique ; sa réponse ne révèle pas l’existence du compte."""

    email: EmailStr = Field(
        max_length=254, description="Adresse associée au compte à récupérer."
    )
    language: Literal["fr", "en"] = Field(
        default="fr", description="Langue du message envoyé."
    )


class ResetPassword(CredentialsInput):
    """Jeton opaque reçu par e-mail et nouveau mot de passe."""

    token: SecretStr = Field(
        min_length=43,
        max_length=128,
        description="Jeton temporaire à usage unique du lien reçu par e-mail.",
    )
    new_password: SecretStr = Field(
        min_length=8,
        max_length=128,
        description="Nouveau mot de passe (8 à 128 caractères).",
    )
