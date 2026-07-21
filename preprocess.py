import os
import json
import fitz  # PyMuPDF

# Configuración de rutas
RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "rag_chunks.json")

# Parámetros de fragmentación (Chunking)
CHUNK_SIZE = 1000       # Tamaño aproximado de cada fragmento (en caracteres)
CHUNK_OVERLAP = 200     # Solapamiento para no perder contexto entre fragmentos

def extraer_paginas_pdf(pdf_path):
    """Extrae el texto de un PDF manteniendo el número de página."""
    documento = fitz.open(pdf_path)
    paginas_extraidas = []
    
    for num_pag, pagina in enumerate(documento):
        texto = pagina.get_text("text")
        # Limpieza básica de espacios en blanco redundantes
        texto_limpio = " ".join(texto.split())
        if texto_limpio.strip():
            paginas_extraidas.append({
                "page": num_pag + 1,
                "text": texto_limpio
            })
    return paginas_extraidas

def crear_chunks(paginas, source_name):
    """Divide el texto de las páginas en fragmentos con solapamiento y metadatos."""
    chunks = []
    
    # Consolidamos todo el texto pero recordando de qué páginas viene
    texto_completo = ""
    mapa_paginas = [] # Para rastrear qué índice de caracter pertenece a qué página
    
    for p in paginas:
        inicio = len(texto_completo)
        texto_completo += p["text"] + " "
        fin = len(texto_completo)
        mapa_paginas.append({"inicio": inicio, "fin": fin, "page": p["page"]})
    
    # Deslizamos la ventana para crear los chunks
    i = 0
    while i < len(texto_completo):
        fin_chunk = min(i + CHUNK_SIZE, len(texto_completo))
        fragmento = texto_completo[i:fin_chunk].strip()
        
        # Determinar de qué página(s) proviene este fragmento
        paginas_asociadas = set()
        for mapeo in mapa_paginas:
            # Si hay intersección entre el fragmento [i, fin_chunk] y el rango de la página
            if not (fin_chunk <= mapeo["inicio"] or i >= mapeo["fin"]):
                paginas_asociadas.add(mapeo["page"])
        
        chunks.append({
            "content": fragmento,
            "metadata": {
                "source": source_name,
                "pages": sorted(list(paginas_asociadas)),
                "char_start": i,
                "char_end": fin_chunk
            }
        })
        
        # Si llegamos al final, rompemos el ciclo
        if fin_chunk == len(texto_completo):
            break
            
        i += (CHUNK_SIZE - CHUNK_OVERLAP)
        
    return chunks

def main():
    # Asegurar que la carpeta procesada exista
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    todos_los_chunks = []
    
    # Escanear la carpeta raw
    archivos = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.pdf')]
    
    if not archivos:
        print(f"⚠️ No se encontraron archivos PDF en '{RAW_DIR}'. ¡Asegúrate de haberlos copiado ahí!")
        return
        
    print(f"🔍 Procesando {len(archivos)} archivo(s)...")
    
    for archivo in archivos:
        ruta_completa = os.path.join(RAW_DIR, archivo)
        print(f"-> Procesando: {archivo}")
        
        # 1. Extraer
        paginas = extraer_paginas_pdf(ruta_completa)
        
        # 2. Fragmentar
        chunks_archivo = crear_chunks(paginas, archivo)
        todos_los_chunks.extend(chunks_archivo)
        
        print(f"   Generados {len(chunks_archivo)} fragmentos.")

    # 3. Guardar el resultado estructurado
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(todos_los_chunks, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 ¡Listo! Se han guardado {len(todos_los_chunks)} fragmentos en '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()