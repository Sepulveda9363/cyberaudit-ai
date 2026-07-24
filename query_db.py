"""
CyberAudit AI — Script de Consulta y Diagnóstico RAG
Permite buscar en ChromaDB directamente, con filtros por tipo de normativa.
Útil para debuggear calidad de retrieval antes de integrar con la API.
"""

import os
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ───────────────────────────────────────────────
# CONFIGURACIÓN
# ───────────────────────────────────────────────
DB_DIR = Path("data/vector_db")
COLLECTION_NAME = "cybersecurity_norms"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# ───────────────────────────────────────────────
# CONEXIÓN A CHROMADB
# ───────────────────────────────────────────────

def conectar_db():
    """Inicializa cliente ChromaDB y retorna la colección."""
    if not DB_DIR.exists():
        raise FileNotFoundError(f"No existe la base de datos en {DB_DIR}. Ejecutá primero store_vectors.py")
    
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False)
    )
    
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    
    try:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=emb_fn
        )
        return collection
    except Exception as e:
        raise RuntimeError(f"Error conectando a colección '{COLLECTION_NAME}': {e}")

# ───────────────────────────────────────────────
# BÚSQUEDA CON FILTROS
# ───────────────────────────────────────────────

def buscar(
    consulta: str,
    n_resultados: int = 5,
    filtro_tipo: Optional[str] = None,
    filtro_pais: Optional[str] = None,
    filtro_organismo: Optional[str] = None
) -> Dict[str, Any]:
    """
    Busca en ChromaDB con filtros opcionales por metadatos.
    """
    collection = conectar_db()
    
    # Construir filtro ChromaDB
    filtros = []
    if filtro_tipo:
        filtros.append({"tipo": {"$eq": filtro_tipo}})
    if filtro_pais:
        filtros.append({"pais": {"$eq": filtro_pais}})
    if filtro_organismo:
        filtros.append({"organismo": {"$eq": filtro_organismo}})
    
    where_clause = None
    if len(filtros) == 1:
        where_clause = filtros[0]
    elif len(filtros) > 1:
        where_clause = {"$and": filtros}
    
    # Ejecutar query
    query_params = {
        "query_texts": [consulta],
        "n_results": n_resultados,
        "include": ["documents", "metadatas", "distances"]
    }
    if where_clause:
        query_params["where"] = where_clause
    
    return collection.query(**query_params)

# ───────────────────────────────────────────────
# FORMATEO DE RESULTADOS
# ───────────────────────────────────────────────

def mostrar_resultados(resultados: Dict[str, Any], mostrar_texto_completo: bool = False):
    """Muestra resultados formateados en terminal."""
    docs = resultados.get("documents", [[]])[0]
    metas = resultados.get("metadatas", [[]])[0]
    dists = resultados.get("distances", [[]])[0]
    
    if not docs:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ No se encontraron resultados.{Colors.END}")
        return
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}================ RESULTADOS ({len(docs)} encontrados) ================{Colors.END}\n")
    
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
        similitud = (1 - float(dist)) * 100 if dist else 0.0
        
        # Parsear metadatos que vienen como strings JSON
        paginas_raw = meta.get("pages", "[]")
        try:
            paginas = json.loads(paginas_raw) if isinstance(paginas_raw, str) else paginas_raw
        except:
            paginas = [paginas_raw]
        
        tipo = meta.get("tipo", "Desconocido")
        organismo = meta.get("organismo", "")
        pais = meta.get("pais", "")
        tema = meta.get("tema", "")
        fuente = meta.get("source", "Desconocida")
        
        # Badge de color según tipo
        color_tipo = Colors.CYAN if tipo == "Ley" else Colors.YELLOW if tipo == "ISO" else Colors.BLUE
        
        print(f"{Colors.BOLD}{Colors.HEADER}📌 [Resultado #{i+1}]{Colors.END} {color_tipo}[{tipo}]{Colors.END} | Similitud: {Colors.GREEN}{similitud:.2f}%{Colors.END}")
        print(f"   📄 Fuente: {Colors.BOLD}{fuente}{Colors.END}")
        print(f"   🏛️  Organismo: {organismo or 'N/A'} | 🌍 País: {pais or 'N/A'} | 📚 Tema: {tema or 'N/A'}")
        print(f"   📑 Página(s): {paginas}")
        print(f"   {Colors.YELLOW}{'─' * 60}{Colors.END}")
        
        texto = doc if mostrar_texto_completo else doc[:500] + ("..." if len(doc) > 500 else "")
        print(texto)
        print(f"   {Colors.YELLOW}{'─' * 60}{Colors.END}\n")

# ───────────────────────────────────────────────
# DIAGNÓSTICO DE LA BASE DE DATOS
# ───────────────────────────────────────────────

def diagnostico_db():
    """Muestra estadísticas de la base de datos vectorial."""
    collection = conectar_db()
    count = collection.count()
    
    print(f"\n{Colors.BOLD}{Colors.HEADER}📊 DIAGNÓSTICO DE CHROMADB{Colors.END}\n")
    print(f"   📁 Ruta: {DB_DIR}")
    print(f"   📦 Colección: {COLLECTION_NAME}")
    print(f"   📊 Total documentos indexados: {Colors.GREEN}{Colors.BOLD}{count}{Colors.END}")
    
    if count == 0:
        print(f"   {Colors.RED}⚠️  La base está vacía. Ejecutá preprocesar.py + store_vectors.py.{Colors.END}")
        return
    
    # Obtener una muestra para ver tipos de documentos
    muestra = collection.get(limit=min(count, 100), include=["metadatas"])
    metas = muestra.get("metadatas", [])
    
    # Contar por tipo
    tipos = {}
    organismos = {}
    for m in metas:
        t = m.get("tipo", "Desconocido")
        o = m.get("organismo", "Desconocido")
        tipos[t] = tipos.get(t, 0) + 1
        organismos[o] = organismos.get(o, 0) + 1
    
    print(f"\n   {Colors.CYAN}📋 Distribución por tipo de normativa:{Colors.END}")
    for tipo, cantidad in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"      • {tipo}: {cantidad} chunks")
    
    print(f"\n   {Colors.CYAN}🏛️  Distribución por organismo:{Colors.END}")
    for org, cantidad in sorted(organismos.items(), key=lambda x: -x[1])[:5]:
        print(f"      • {org or 'N/A'}: {cantidad} chunks")

# ───────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CyberAudit AI — Consulta y diagnóstico de base vectorial",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python consulta_db.py "plazo para reportar incidentes" --tipo Ley --pais Chile
  python consulta_db.py "controles de acceso" --tipo Framework --n 5
  python consulta_db.py --diagnostico
  python consulta_db.py "ISO 27001" --full-text
        """
    )
    
    parser.add_argument("consulta", nargs="?", help="Pregunta o término de búsqueda")
    parser.add_argument("-n", "--numero", type=int, default=5, help="Número de resultados (default: 5)")
    parser.add_argument("--tipo", choices=["Ley", "ISO", "Framework", "Guía", "Política", "Informe"], 
                       help="Filtrar por tipo de normativa")
    parser.add_argument("--pais", help="Filtrar por país (ej: Chile, Internacional, EE.UU.)")
    parser.add_argument("--organismo", help="Filtrar por organismo (ej: CIS, OWASP, NIST)")
    parser.add_argument("--full-text", action="store_true", help="Mostrar texto completo de cada chunk")
    parser.add_argument("--diagnostico", action="store_true", help="Mostrar estadísticas de la DB y salir")
    
    args = parser.parse_args()
    
    # Modo diagnóstico
    if args.diagnostico:
        diagnostico_db()
        return
    
    # Validar consulta
    if not args.consulta:
        parser.print_help()
        return
    
    print(f"\n{Colors.BOLD}{Colors.HEADER}🔍 CyberAudit AI — Búsqueda RAG{Colors.END}")
    print(f"   Consulta: '{Colors.CYAN}{args.consulta}{Colors.END}'")
    if args.tipo:
        print(f"   Filtro tipo: {Colors.YELLOW}{args.tipo}{Colors.END}")
    if args.pais:
        print(f"   Filtro país: {Colors.YELLOW}{args.pais}{Colors.END}")
    
    try:
        resultados = buscar(
            consulta=args.consulta,
            n_resultados=args.numero,
            filtro_tipo=args.tipo,
            filtro_pais=args.pais,
            filtro_organismo=args.organismo
        )
        mostrar_resultados(resultados, mostrar_texto_completo=args.full_text)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.END}")

if __name__ == "__main__":
    main()