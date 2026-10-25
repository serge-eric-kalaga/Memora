FROM python:3.14-bookworm

# Garder les dépendances hors du dossier /app monté depuis l’hôte en développement.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml uv.lock ./

# Installer uniquement les dépendances sans construire le projet
RUN uv sync --frozen --no-install-project

# Copier le code source
COPY . .

# Installer le projet maintenant que api/ existe
RUN uv sync --frozen

EXPOSE 80

# Les dépendances sont installées au build ; surveiller le code, pas les environnements locaux.
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "80", "--reload", "--reload-dir", "/app/api"]
