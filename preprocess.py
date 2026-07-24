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

from pypdf import PdfReader

# ───────────────────────────────────────────────
# CONFIGURACIÓN
# ───────────────────────────────────────────────

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE = PROCESSED_DIR / "rag_chunks.json"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MAX_CHUNK_SIZE = 1200

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
    nombre = nombre_archivo.lower()
    
    reglas = [
        (r"ley-?21663|ley marco", {"tipo": "Ley", "pais": "Chile", "tema": "Ciberseguridad", "organismo": "Ministerio del Interior"}),
        (r"ley-?21719", {"tipo": "Ley", "pais": "Chile", "tema": "Ciberseguridad", "organismo": "Congreso Nacional"}),
        # ← NUEVAS LEYES AQUÍ
        (r"ley-?21459|delitos?.informaticos", {"tipo": "Ley", "pais": "Chile", "tema": "Delitos Informáticos", "organismo": "Congreso Nacional"}),
        (r"ley-?19628|proteccion.*datos|datos.personales", {"tipo": "Ley", "pais": "Chile", "tema": "Protección de Datos Personales", "organismo": "Congreso Nacional"}),
        (r"ley-?19799|firma.electronica|documento.electronico", {"tipo": "Ley", "pais": "Chile", "tema": "Firma Digital", "organismo": "Congreso Nacional"}),
        # ← FIN NUEVAS LEYES
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
# EXTRACCIÓN DE TEXTO CON PYPDF
# ───────────────────────────────────────────────

def extraer_paginas_pdf(pdf_path: Path) -> List[Dict]:
    paginas = []
    try:
        reader = PdfReader(str(pdf_path))
        doc_name = pdf_path.stem
        
        for i, page in enumerate(reader.pages, start=1):
            texto = page.extract_text()
            texto_limpio = re.sub(r'\s+', ' ', texto) if texto else ""
            texto_limpio = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', texto_limpio)
            
            if texto_limpio.strip():
                paginas.append({
                    "page": i,
                    "text": texto_limpio.strip()
                })
        
        logger.info(f"✅ {pdf_path.name}: {len(paginas)} páginas extraídas")
        return paginas
        
    except Exception as e:
        logger.error(f"❌ Error leyendo {pdf_path.name}: {e}")
        return []

# ───────────────────────────────────────────────
# CHUNKING INTELIGENTE
# ───────────────────────────────────────────────

def crear_chunks(paginas: List[Dict], source_name: str) -> List[Dict]:
    if not paginas:
        return []
    
    meta_normativa = detectar_normativa(source_name)
    
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
        
        if fin_chunk < len(texto_completo):
            ventana = texto_completo[fin_chunk:min(fin_chunk + 200, len(texto_completo))]
            ultimo_punto = ventana.rfind('. ')
            if ultimo_punto != -1:
                fin_chunk += ultimo_punto + 1
            else:
                sub = texto_completo[i:fin_chunk]
                ultimo_espacio = sub.rfind(' ')
                if ultimo_espacio > CHUNK_SIZE * 0.5:
                    fin_chunk = i + ultimo_espacio
        
        fin_chunk = min(fin_chunk, i + MAX_CHUNK_SIZE)
        fragmento = texto_completo[i:fin_chunk].strip()
        
        if not fragmento:
            i += (CHUNK_SIZE - CHUNK_OVERLAP)
            continue
        
        paginas_asociadas: Set[int] = set()
        for mapeo in mapa_paginas:
            if not (fin_chunk <= mapeo["inicio"] or i >= mapeo["fin"]):
                paginas_asociadas.add(mapeo["page"])
        
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
                **meta_normativa
            }
        })
        
        chunk_counter += 1
        
        if fin_chunk >= len(texto_completo):
            break
        i += (fin_chunk - i - CHUNK_OVERLAP)
        if i <= 0:
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
            logger.warning(f"   ⚠️ Sin contenido extraído")
            continue
        
        chunks = crear_chunks(paginas, archivo.name)
        todos_los_chunks.extend(chunks)
        logger.info(f"   📄 {len(chunks)} chunks generados")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(todos_los_chunks, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n🎉 Ingesta completa: {len(todos_los_chunks)} chunks guardados")
    
    resumen = {}
    for c in todos_los_chunks:
        tipo = c["metadata"].get("tipo", "Desconocido")
        resumen[tipo] = resumen.get(tipo, 0) + 1
    logger.info(f"📊 Resumen por tipo: {resumen}")

if __name__ == "__main__":
    main()