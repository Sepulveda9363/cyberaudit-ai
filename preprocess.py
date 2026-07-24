"""
CyberAudit AI — Pipeline de Ingesta de Normativas
Extrae, fragmenta y enriquece metadatos de todos los PDFs en data/raw/
"""

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Set

import fitz  # PyMuPDF

# ───────────────────────────────────────────────
# CONFIGURACIÓN
# ───────────────────────────────────────────────

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE = PROCESSED_DIR / "rag_chunks.json"

CHUNK_SIZE = 800        # Reducido para chunks más precisos (mejor retrieval)
CHUNK_OVERLAP = 150     # Solapamiento conservador
MAX_CHUNK_SIZE = 1200   # Límite duro de seguridad (evita prompts gigantes)

# Logging estructurado (formato JSON-friendly para observabilidad)
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────
# DETECCIÓN INTELIGENTE DE METADATOS
# ───────────────────────────────────────────────

def detectar_normativa(nombre_archivo: str) -> Dict[str, str]:
    """
    Clasifica el documento según su nombre para enriquecer los metadatos.
    Permite filtrar consultas RAG por tipo, organismo o país.
    """
    nombre = nombre_archivo.lower()
    
    # Mapeo de patrones → metadatos
    reglas = [
        (r"ley-?21663|ley marco", {"tipo": "Ley", "pais": "Chile", "tema": "Ciberseguridad", "organismo": "Ministerio del Interior"}),
        (r"ley-?21719", {"tipo": "Ley", "pais": "Chile", "tema": "Ciberseguridad", "organismo": "Congreso Nacional"}),
        (r"cis.?control", {"tipo": "Framework", "organismo": "CIS", "tema": "Controles de Seguridad", "pais": "Internacional"}),
        (r"owasp.*llm", {"tipo": "Guía", "organismo": "OWASP", "tema": "IA/LLM Security", "pais": "Internacional"}),
        (r"owasp.*top.?10", {"tipo": "Guía", "organismo": "OWASP", "tema": "AppSec", "pais": "Internacional"}),
        (r"iso.?27001", {"tipo": "ISO", "organismo": "ISO/IEC", "tema": "SGSI", "pais": "Internacional"}),
        (r"iso.?27002", {"tipo": "ISO", "organismo": "ISO/IEC", "tema": "Controles", "pais": "Internacional"}),
        (r"iso.?31000", {"tipo": "ISO", "organismo": "ISO", "tema": "Gestión de Riesgos", "pais": "Internacional"}),
        (r"nist", {"tipo": "Framework", "organismo": "NIST", "tema": "Ciberseguridad", "pais": "EE.UU."}),
        (r"pol[ií]tica.?nacional|ciberdefensa", {"tipo": "Política", "pais": "Chile", "tema": "Ciberdefensa", "organismo": "Gobierno de Chile"}),
        (r"informe.*bcn", {"tipo": "Informe", "pais": "Chile", "tema": "Ciberdefensa", "organismo": "Biblioteca del Congreso"}),
    ]
    
    for patron, meta in reglas:
        if re.search(patron, nombre):
            return meta
    
    return {"tipo": "Documento", "tema": "General", "pais": "Desconocido", "organismo": "Desconocido"}

# ───────────────────────────────────────────────
# EXTRACCIÓN DE TEXTO
# ───────────────────────────────────────────────

def extraer_paginas_pdf(pdf_path: Path) -> List[Dict]:
    """
    Extrae texto página por página usando PyMuPDF.
    Retorna lista de dicts con page_num y text.
    """
    paginas = []
    try:
        doc = fitz.open(str(pdf_path))
        
        for num_pag, pagina in enumerate(doc, start=1):
            texto = pagina.get_text("text")
            # Sanitización básica: eliminar espacios múltiples y caracteres de control
            texto_limpio = re.sub(r'\s+', ' ', texto)
            texto_limpio = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', texto_limpio)
            
            if texto_limpio.strip():
                paginas.append({
                    "page": num_pag,
                    "text": texto_limpio.strip()
                })
        
        doc.close()
        logger.info(f"✅ {pdf_path.name}: {len(paginas)} páginas extraídas")
        return paginas
        
    except Exception as e:
        logger.error(f"❌ Error leyendo {pdf_path.name}: {e}")
        return []

# ───────────────────────────────────────────────
# CHUNKING INTELIGENTE (corte en oraciones)
# ───────────────────────────────────────────────

def crear_chunks(paginas: List[Dict], source_name: str) -> List[Dict]:
    """
    Divide el texto en chunks respetando límites de oración cuando es posible.
    Cada chunk incluye metadatos enriquecidos y un ID determinístico.
    """
    if not paginas:
        return []
    
    # Detectar metadatos de la normativa desde el nombre del archivo
    meta_normativa = detectar_normativa(source_name)
    
    # Consolidar texto completo con mapa de páginas
    texto_completo = ""
    mapa_paginas = []
    
    for p in paginas:
        inicio = len(texto_completo)
        texto_completo += p["text"] + " "
        fin = len(texto_completo)
        mapa_paginas.append({"inicio": inicio, "fin": fin, "page": p["page"]})
    
    chunks = []
    i = 0
    chunk_counter = 0
    
    while i < len(texto_completo):
        fin_chunk = min(i + CHUNK_SIZE, len(texto_completo))
        
        # Estrategia de corte inteligente: buscar fin de oración/párrafo
        if fin_chunk < len(texto_completo):
            # Buscar el último punto seguido de espacio en los próximos 200 caracteres
            ventana_busqueda = texto_completo[fin_chunk:min(fin_chunk + 200, len(texto_completo))]
            ultimo_punto = ventana_busqueda.rfind('. ')
            
            if ultimo_punto != -1:
                fin_chunk += ultimo_punto + 1  # +1 para incluir el punto
            else:
                # Fallback: buscar último espacio
                sub_texto = texto_completo[i:fin_chunk]
                ultimo_espacio = sub_texto.rfind(' ')
                if ultimo_espacio > CHUNK_SIZE * 0.5:  # Solo si no recortamos demasiado
                    fin_chunk = i + ultimo_espacio
        
        # Aplicar límite duro de seguridad
        fin_chunk = min(fin_chunk, i + MAX_CHUNK_SIZE)
        
        fragmento = texto_completo[i:fin_chunk].strip()
        if not fragmento:
            i += (CHUNK_SIZE - CHUNK_OVERLAP)
            continue
        
        # Determinar páginas asociadas
        paginas_asociadas: Set[int] = set()
        for mapeo in mapa_paginas:
            if not (fin_chunk <= mapeo["inicio"] or i >= mapeo["fin"]):
                paginas_asociadas.add(mapeo["page"])
        
        # Generar ID determinístico (evita duplicados en re-ingestas)
        id_hash = hashlib.sha256(
            f"{source_name}:{sorted(paginas_asociadas)}:{fragmento[:100]}".encode()
        ).hexdigest()[:16]
        
        chunks.append({
            "id": id_hash,
            "content": fragmento,
            "metadata": {
                "source": source_name,
                "pages": sorted(list(paginas_asociadas)),
                "char_start": i,
                "char_end": fin_chunk,
                "chunk_index": chunk_counter,
                **meta_normativa  # Unpack de tipo, pais, tema, organismo
            }
        })
        
        chunk_counter += 1
        
        if fin_chunk >= len(texto_completo):
            break
            
        i += (fin_chunk - i - CHUNK_OVERLAP)
        if i <= 0:  # Seguridad anti-loop infinito
            i = fin_chunk
    
    return chunks

# ───────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ───────────────────────────────────────────────

def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    archivos = sorted(RAW_DIR.glob("*.pdf"))
    if not archivos:
        logger.warning(f"No se encontraron PDFs en '{RAW_DIR}'")
        return
    
    logger.info(f"📚 Iniciando ingesta de {len(archivos)} documento(s)...")
    
    todos_los_chunks = []
    
    for archivo in archivos:
        logger.info(f"-> {archivo.name}")
        
        paginas = extraer_paginas_pdf(archivo)
        if not paginas:
            logger.warning(f"   ⚠️ Sin contenido extraído (¿PDF escaneado/imagen?)")
            continue
        
        chunks = crear_chunks(paginas, archivo.name)
        todos_los_chunks.extend(chunks)
        logger.info(f"   📄 {len(chunks)} chunks generados")
    
    # Guardar JSON intermedio
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(todos_los_chunks, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n🎉 Ingesta completa: {len(todos_los_chunks)} chunks guardados en {OUTPUT_FILE}")
    
    # Resumen por tipo de normativa
    resumen = {}
    for c in todos_los_chunks:
        tipo = c["metadata"].get("tipo", "Desconocido")
        resumen[tipo] = resumen.get(tipo, 0) + 1
    logger.info(f"📊 Resumen por tipo: {resumen}")

if __name__ == "__main__":
    main()