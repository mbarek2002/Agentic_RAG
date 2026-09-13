# Agentic RAG — arXiv Paper Curator

Système RAG (Retrieval-Augmented Generation) agentique construit pas à pas : une API FastAPI qui ingère, indexe et interroge des papiers de recherche arXiv, orchestrée avec PostgreSQL, OpenSearch, Apache Airflow et Ollama.

> Statut : **Semaine 1 — Infrastructure**. L'API, la base de données et l'orchestration Docker sont en place. La logique RAG (ingestion, embeddings, recherche hybride, génération LLM) sera ajoutée dans les semaines suivantes.

## Prérequis

- **Docker Desktop** (avec Docker Compose)
- **Python 3.12**
- **[UV](https://docs.astral.sh/uv/getting-started/installation/)** comme gestionnaire de paquets/projet
- 8 Go de RAM et 20 Go d'espace disque libres (recommandé)

## Démarrage rapide

```bash
# 1. Installer les dépendances Python
uv sync

# 2. Copier le fichier d'environnement et l'ajuster si besoin
cp .env.example .env

# 3. Démarrer tous les services
docker compose up --build -d

# 4. Vérifier que l'API répond
curl http://localhost:8000/api/v1/health
```

## Services

| Service | URL | Rôle |
|---|---|---|
| **API** | http://localhost:8000/docs | Documentation interactive FastAPI |
| **PostgreSQL** | `localhost:5432` | Stockage des métadonnées des papiers |
| **OpenSearch** | http://localhost:9200 | Moteur de recherche (hybride, à venir) |
| **OpenSearch Dashboards** | http://localhost:5601 | Interface d'administration OpenSearch |
| **Airflow** | http://localhost:8080 | Orchestration des pipelines (identifiants : `admin` / `admin`) |
| **Ollama** | http://localhost:11434 | Serveur LLM local |

## Structure du projet

```
.
├── src/
│   ├── main.py               # Point d'entrée FastAPI (app + lifespan + routers)
│   ├── config.py              # Configuration (Pydantic Settings)
│   ├── dependencies.py        # Injection de dépendances FastAPI
│   ├── exceptions.py          # Exceptions applicatives
│   ├── middlewares.py         # Logging des requêtes
│   ├── database.py             # Accès à l'instance de base de données
│   ├── db/                    # Interfaces DB (base abstraite + implémentation PostgreSQL)
│   ├── models/                # Modèles ORM SQLAlchemy (Paper)
│   ├── repositories/           # Couche d'accès aux données
│   ├── schemas/                # Schémas de validation Pydantic
│   ├── routers/                # Endpoints API (ping, papers, ask)
│   └── services/                # Logique métier (client Ollama)
├── tests/                      # Suite de tests (pytest)
├── airflow/                    # Image et DAGs Airflow
├── compose.yml                 # Orchestration des services
├── Dockerfile                  # Image de l'API
└── Makefile                    # Commandes de développement
```

## Commandes utiles

```bash
make start       # Démarrer tous les services
make stop        # Arrêter tous les services
make restart     # Redémarrer tous les services
make status      # Statut des conteneurs
make logs        # Suivre les logs
make health      # Vérifier la santé de tous les services
make setup       # uv sync
make format      # Formater le code (ruff)
make lint        # Linter + vérification de types (ruff + mypy)
make test        # Lancer les tests (pytest)
make test-cov    # Lancer les tests avec couverture
make clean       # Arrêter et nettoyer volumes/images Docker
```

`make help` liste toutes les commandes disponibles.

## Configuration

Toutes les variables d'environnement sont documentées dans [.env.example](.env.example) (application, PostgreSQL, OpenSearch, Ollama, Airflow). Copiez ce fichier vers `.env` et ajustez les valeurs pour votre environnement local. Le fichier `.env` ne doit jamais être commité.

## Tests

```bash
uv run pytest
```

## Dépannage

- **Les services ne démarrent pas ?** Attendez 2-3 minutes puis consultez `docker compose logs`.
- **Conflit de ports ?** Vérifiez que rien d'autre n'utilise les ports 8000, 8080, 5432, 9200, 9600, 5601, 11434.
- **Réinitialisation complète :**
  ```bash
  docker compose down --volumes
  docker compose up --build -d
  ```

## Feuille de route

- **Semaine 1** — Infrastructure : API, PostgreSQL, OpenSearch, Airflow, Ollama ✅
- **Semaine 2** — Ingestion arXiv + parsing PDF (Docling)
- **Semaine 3** — Recherche hybride OpenSearch (BM25 + vecteurs sémantiques)
- **Semaine 4** — Chunking contextuel et évaluation de la recherche (nDCG)
- **Semaine 5** — Pipeline RAG complet avec intégration LLM
- **Semaine 6** — Observabilité (Langfuse), A/B testing, mise en production

## Licence

MIT — voir [LICENSE](LICENSE).
