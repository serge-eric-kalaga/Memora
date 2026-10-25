# Projet

Memora V1 : application locale de capture/import audio, transcription, analyse et chat sourcés, partage invité configurable. Référence : PDF fonctionnel V1 du 25/10/2026, 16 pages intégralement extraites et lues. Demande utilisateur complémentaire prioritaire.

Template initial : main 355e50a, FastAPI SQLAlchemy, MySQL, Celery/RabbitMQ, Redis ; Next 16.4.2 React 19.3, proxy serveur avec cookie HttpOnly. Dépendances : uv.lock / package-lock.json. Python du venv initial cassé (/usr/local/bin/python3 absent). Aucun code PHP ; phpMyAdmin est un outil Compose.

Références lues sans modification : DBChat controllers/ollama.py et AI_Agora services/providers.py. Patterns API locale, contrôle de destination. Aucune copie de code faute de licence explicite repérée. ServicePublic README et services/chat.py consultés en lecture seule : isolation conversation/session, références persistées et contexte limité. Sa recherche Chroma/reranking répond à un corpus documentaire global ; Memora conserve le périmètre strict de la réunion et n’en copie pas le code.

Machine : Apple M5,16 GiB RAM,15 GiB disque libres observés vers02h ; GMT = Africa/Ouagadougou. Début 00:22, objectif de découverte 10h sans garantie de délai. Ollama fonctionne hors restrictions réseau sandbox, modèles existants conservés. qwen3.5:4b répond en JSON (3.39s chargement compris). Ollama non exposé publiquement.
