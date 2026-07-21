import os
import json
import chromadb
from chromadb.utils import embedding_functions

# Configuración de rutas
PROCESSED_DIR = "data/processed"
INPUT_FILE = os.path.join(PROCESSED_DIR, "rag_chunks.json")
DB_DIR = "data/vector_db"  # Aquí se guardará la base de datos local

def main():
    # 1. Verificar si existe el archivo de fragmentos
    if not os.path.exists(INPUT_FILE):
        print(f"⚠️ No se encontró el archivo '{INPUT_FILE}'. Ejecuta primero 'preprocess.py'.")
        return

    print("📖 Cargando fragmentos procesados...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    print(f"   Se cargaron {len(chunks)} fragmentos.")

    # 2. Inicializar el cliente de ChromaDB (Persistente en disco)
    print("\n📦 Inicializando base de datos vectorial local...")
    client = chromadb.PersistentClient(path=DB_DIR)

    # 3. Configurar el modelo de embeddings local (all-MiniLM-L6-v2)
    # Este modelo es ligero, rápido y corre 100% en tu máquina
    print("🧠 Descargando/Inicializando modelo de embeddings semánticos...")
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # 4. Crear o recuperar la colección en la base de datos
    # Usamos distancia coseno para medir qué tan similares son las preguntas del usuario y los textos
    collection = client.get_or_create_collection(
        name="cybersecurity_norms",
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"}
    )

    # 5. Preparar los datos para la inserción en ChromaDB
    print("\n🚀 Indexando fragmentos en la base de datos (esto puede tardar un poco)...")
    
    ids = []
    documents = []
    metadatas = []

    for idx, chunk in enumerate(chunks):
        ids.append(f"id_{idx}")
        documents.append(chunk["content"])
        
        # ChromaDB requiere que los metadatos tengan tipos simples (strings, ints, floats, bools)
        # Como 'pages' es una lista de enteros en nuestro JSON, la convertimos a string para evitar errores
        meta = chunk["metadata"]
        meta_procesada = {
            "source": meta["source"],
            "pages": str(meta["pages"]),  # Ej: "[12, 13]"
            "char_start": meta["char_start"],
            "char_end": meta["char_end"]
        }
        metadatas.append(meta_procesada)

    # ChromaDB permite insertar por lotes para no saturar la memoria
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        end_idx = min(i + batch_size, len(documents))
        print(f"   -> Insertando lote {i} al {end_idx}...")
        
        collection.add(
            ids=ids[i:end_idx],
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )

    print(f"\n🎉 ¡Éxito! Base de datos vectorial creada con {collection.count()} registros en '{DB_DIR}'")

if __name__ == "__main__":
    main()