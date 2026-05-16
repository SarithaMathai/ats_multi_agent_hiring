# ChromaDB Service

ChromaDB runs as a Docker service using the official `chromadb/chroma` image.
No custom Dockerfile is needed — all configuration is passed via environment variables
in `docker-compose.yml`.

## Collections used by the ATS system

| Collection name          | Purpose                                    |
|--------------------------|--------------------------------------------|
| `ats_candidates`         | Candidate profile embeddings               |
| `ats_resumes`            | Resume text chunks for RAG retrieval       |
| `ats_feedback`           | Interview feedback & manager notes         |
| `ats_interventions`      | Historical MCP intervention case studies   |

Collections are created programmatically by `vector_store/chroma/` at startup.
