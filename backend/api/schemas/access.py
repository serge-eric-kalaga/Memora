"""Contrats Pydantic de l’administration des rôles et permissions."""

from pydantic import BaseModel, ConfigDict, Field
from api.schemas.user import CreateUserModel


class AccessName(BaseModel):
    """Code stable utilisé dans les dépendances, par exemple editor ou reports.read."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{0,99}$", examples=["reports.read"])


class AccessUpdate(BaseModel):
    """Métadonnées modifiables ; le code reste stable pour les dépendances métier."""

    model_config = ConfigDict(extra="forbid")
    description: str = Field(
        max_length=500, description="Description du droit ou du rôle"
    )
    is_active: bool = Field(
        description="Désactiver suspend les droits sans effacer les attributions"
    )


class AccessItem(AccessName):
    """Identifiant et nom d’un rôle ou d’une permission."""

    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Identifiant SQL du rôle ou de la permission")
    description: str = ""
    is_active: bool = True


class RoleDetail(AccessItem):
    """Permissions explicitement associées au rôle."""

    permissions: list[AccessItem] = Field(description="Permissions accordées au rôle")


class UserAccess(BaseModel):
    """Droits SQL de l’utilisateur, en distinguant droits directs et effectifs."""

    is_superuser: bool = Field(
        default=False,
        description="Statut super administrateur attribué uniquement côté serveur",
    )
    username: str = Field(description="Nom du compte concerné")
    roles: list[str] = Field(description="Rôles directement attribués au compte")
    direct_permissions: list[str] = Field(
        description="Permissions accordées directement au compte"
    )
    permissions: list[str] = Field(
        description="Union des permissions directes et héritées des rôles"
    )


class AdminCreateUser(CreateUserModel):
    """Créer un compte normal, sans accepter de rôle ou statut privilégié dans le corps."""

    model_config = ConfigDict(extra="forbid")


class AdminUser(BaseModel):
    """Projection limitée du compte pour les listes d’administration."""

    model_config = ConfigDict(from_attributes=True)
    username: str
    email: str | None
    is_superuser: bool
