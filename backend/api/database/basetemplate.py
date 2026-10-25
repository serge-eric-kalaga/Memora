from typing import Self
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session, Query


class BaseTemplate:
    """Méthodes CRUD communes aux modèles SQLAlchemy utilisant une session fournie.

    Les méthodes de lecture ne valident pas de transaction. Les méthodes suffixées
    WithCommit valident toute la transaction en cours de la session.
    """
    @classmethod
    def query(cls, db: Session) -> Query:
        """Construire une requête SQLAlchemy sur le modèle sans l’exécuter."""
        return db.query(cls)

    @classmethod
    def get(cls, db: Session, error_msg: str = "model not found", **kwargs) -> Self:
        """Retourner le premier objet correspondant aux filtres ou lever HTTP 404."""
        result = db.query(cls).filter_by(**kwargs).first()
        if result is None:
            raise HTTPException(status_code=404, detail=error_msg)
        return result

    @classmethod
    def getOrNone(cls, db: Session, **kwargs) -> Self:
        """Retourner le premier objet correspondant aux filtres, ou None s’il est absent."""
        result = db.query(cls).filter_by(**kwargs).first()
        return result

    @classmethod
    def getAll(cls, db: Session) -> list[Self]:
        """Retourner tous les objets du modèle dans une liste."""
        return db.query(cls).all()

    @classmethod
    def getAllFilterBy(cls, db: Session, **kwargs) -> list[Self]:
        """Retourner les objets correspondant aux égalités transmises dans kwargs."""
        return db.query(cls).filter_by(**kwargs).all()

    # def commit(self, db:Session) -> Self:
    #     db.commit()
    #     return self

    # def save(self, db:Session) -> Self:
    #     db.add(self)
    #     # db.refresh(self)
    #     return self

    def saveWithCommit(self, db: Session) -> Self:
        """Ajouter l’objet, valider la transaction et rafraîchir ses valeurs depuis la base."""
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    # def delete(self, db:Session) -> Self:
    #     db.delete(self)
    #     return self

    def deleteWithCommit(self, db: Session) -> Self:
        """Supprimer l’objet, valider la transaction et retourner l’instance supprimée."""
        db.delete(self)
        db.commit()
        return self
