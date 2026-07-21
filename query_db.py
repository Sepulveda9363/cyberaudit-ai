import chromadb
from chromadb.utils import embedding_functions

def buscar_en_db(consulta, numero_resultados=3):
    # 1. Conectar a la base de datos persistente
    client = chromadb.PersistentClient(path="data/vector_db")
    
    # 2. Cargar el mismo modelo de embeddings que usamos para guardar
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # 3. Obtener la colección
    collection = client.get_collection(name="cybersecurity_norms", embedding_function=emb_fn)
    
    # 4. Realizar la consulta
    print(f"\n🔍 Buscando: '{consulta}'...")
    resultados = collection.query(
        query_texts=[consulta],
        n_results=numero_resultados
    )
    
    # 5. Mostrar los resultados de forma ordenada
    print("\n================ RESULTADOS ENCONTRADOS ================")
    for i in range(len(resultados["documents"][0])):
        documento = resultados["documents"][0][i]
        meta = resultados["metadatas"][0][i]
        distancia = resultados["distances"][0][i] # Menor distancia = Mayor similitud
        
        # Calcular un porcentaje aproximado de similitud basado en la distancia coseno
        similitud = (1 - distancia) * 100
        
        print(f"\n📌 [Resultado #{i+1}] - Similitud: {similitud:.2f}%")
        print(f"📄 Origen: {meta['source']} | Pág(s): {meta['pages']}")
        print(f"--------------------------------------------------------")
        print(documento)
        print(f"--------------------------------------------------------")

if __name__ == "__main__":
    # Aquí puedes cambiar la pregunta para probar distintos temas de ciberseguridad
    pregunta_prueba = "plazo para reportar incidentes criticos"
    buscar_en_db(pregunta_prueba, numero_resultados=3)