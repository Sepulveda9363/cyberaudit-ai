"""
CyberAudit AI — Indexador Vectorial en ChromaDB
Lee los chunks de rag_chunks.json y los indexa en ChromaDB local.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ───────────────────────────────────────────────
# CONFIGURACIÓN
# ───────────────────────────────────────────────

PROCESSED_DIR = Path("data/processed")
INPUT_FILE = PROCESSED_DIR / "rag_chunks.json"
DB_DIR = Path("data/vector_db")
COLLECTION_NAME = "cybersecurity_norms"

# Logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────
# SANITIZACIÓN DE METADATOS
# ───────────────────────────────────────────────

def sanitizar_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB solo acepta metadatos con tipos primitivos:
    str, int, float, bool. Listas y dicts deben convertirse.
    """
    meta_limpia = {}
    
    for key, value in meta.items():
        if value is None:
            meta_limpia[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            meta_limpia[key] = value
        elif isinstance(value, list):
            # Convertir listas a string JSON
            meta_limpia[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, dict):
            meta_limpia[key] = json.dumps(value, ensure_ascii=False)
        else:
            meta_limpia[key] = str(value)
    
    return meta_limpia

# ───────────────────────────────────────────────
# PIPELINE DE INDEXACIÓN
# ───────────────────────────────────────────────

def main():
    # 1. Verificar archivo de entrada
    if not INPUT_FILE.exists():
        logger.error(f"No se encontró '{INPUT_FILE}'. Ejecutá primero 'preprocesar.py'.")
        return

    logger.info("📖 Cargando fragmentos procesados...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    logger.info(f"   Se cargaron {len(chunks)} fragmentos.")

    # 2. Inicializar ChromaDB (persistente, sin telemetría)
    logger.info("📦 Inicializando base de datos vectorial local...")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False)
    )

    # 3. Configurar modelo de embeddings local
    logger.info("🧠 Cargando modelo de embeddings: all-MiniLM-L6-v2")
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # 4. Crear o recuperar colección
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine", "description": "Normativas de ciberseguridad"}
    )

    # 5. Preparar datos para inserción
    logger.info("🚀 Indexando fragmentos en ChromaDB...")
    
    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        # Usar el ID determinístico generado en preprocesar.py
        chunk_id = chunk.get("id")
        if not chunk_id:
            # Fallback por si el JSON viejo no tiene id
            chunk_id = f"chunk_{hash(chunk['content']) % 10**16}"
        
        ids.append(chunk_id)
        documents.append(chunk["content"])
        
        # Sanitizar metadatos para ChromaDB
        meta_raw = chunk.get("metadata", {})
        meta_procesada = sanitizar_metadata(meta_raw)
        metadatas.append(meta_procesada)

    # 6. Insertar por lotes (batch) para no saturar memoria
    batch_size = 500
    total_insertados = 0
    
    for i in range(0, len(documents), batch_size):
        end_idx = min(i + batch_size, len(documents))
        batch_ids = ids[i:end_idx]
        batch_docs = documents[i:end_idx]
        batch_metas = metadatas[i:end_idx]
        
        try:
            collection.add(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metas
            )
            total_insertados += len(batch_ids)
            logger.info(f"   ✅ Lote {i}-{end_idx}: {len(batch_ids)} registros indexados")
        except Exception as e:
            logger.error(f"   ❌ Error en lote {i}-{end_idx}: {e}")
            continue

    # 7. Verificación final
    count_final = collection.count()
    logger.info(f"\n🎉 Indexación completa: {count_final} registros en ChromaDB.")
    
    # Resumen por tipo de normativa (usando metadatos enriquecidos)
    if count_final > 0:
        logger.info("📊 Resumen de documentos indexados por tipo:")
        # ChromaDB no tiene GROUP BY, pero podemos hacer un resumen desde el JSON
        resumen = {}
        for m in metadatas:
            tipo = m.get("tipo", "Desconocido")
            resumen[tipo] = resumen.get(tipo, 0) + 1
        for tipo, cantidad in sorted(resumen.items()):
            logger.info(f"   • {tipo}: {cantidad} chunks")

if __name__ == "__main__":
    main()