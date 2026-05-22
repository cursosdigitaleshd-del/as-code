import re
from typing import List, Dict
from sqlalchemy.orm import Session
from api.memory_models import MemoryObservation
from api.rag_models import RAGDocument

KEYWORD_MAPS: Dict[str, List[str]] = {
    "marketing": [
        "marketing", "ventas", "vender", "instagram", "flyer", "anuncio", "campaña", "campaign",
        "leads", "ad", "target", "audience", "redes", "social media", "publicidad", "hooks",
        "hook", "branding", "copys", "audiencia", "facebook", "twitter", "linkedin", "tiktok", "viral"
    ],
    "sales": [
        "vender", "ventas", "comprar", "sales", "negociar", "pipeline", "deals", "crm", "pricing",
        "precios", "clientes", "prospect", "funnel", "conversión", "oferta", "propuesta", "pitch"
    ],
    "legal": [
        "contrato", "legal", "ley", "cláusula", "ndia", "contract", "acuerdo", "firma", "riesgo",
        "términos", "condiciones", "política", "abogado", "demanda", "propiedad intelectual",
        "regulaciones", "normativa", "clause", "nda", "compliance"
    ],
    "business": [
        "business", "negocio", "estrategia", "planning", "planificación", "operaciones", "operations",
        "presupuesto", "budget", "startup", "empresa", "sociedad", "inversor", "finanzas", "funding",
        "roi", "ganancia", "ingresos", "revenue", "costos"
    ],
    "content_creator": [
        "video", "guión", "script", "post", "blog", "content", "creador", "diseño", "flyer", "imagen",
        "youtube", "tiktok", "copywriting", "redactar", "escribir", "podcast", "thumbnail", "contenido"
    ]
}

def analyze_intent(user_message: str, db: Session, session_id: str) -> List[str]:
    """
    Heuristically analyze user message and workspace state to match skill IDs.
    Returns matching skill IDs ordered by relevance score descending.
    """
    scores: Dict[str, int] = {skill: 0 for skill in KEYWORD_MAPS}
    msg_lower = user_message.lower()

    # 1. Match against user message
    for skill, keywords in KEYWORD_MAPS.items():
        for kw in keywords:
            # Word boundary search to avoid sub-word matching issues
            pattern = r'\b' + re.escape(kw) + r'\b'
            matches = len(re.findall(pattern, msg_lower))
            if matches > 0:
                scores[skill] += matches * 2

    # 2. Match against active RAG documents
    try:
        docs = db.query(RAGDocument).all()
        for doc in docs:
            filename_lower = doc.filename.lower()
            for skill, keywords in KEYWORD_MAPS.items():
                for kw in keywords:
                    if kw in filename_lower:
                        scores[skill] += 3
    except Exception:
        # Graceful degradation if RAG table is missing or errors
        pass

    # 3. Match against recent observations in Working Memory
    try:
        observations = db.query(MemoryObservation).filter_by(session_id=session_id).all()
        for obs in observations:
            obs_lower = obs.content.lower()
            for skill, keywords in KEYWORD_MAPS.items():
                for kw in keywords:
                    pattern = r'\b' + re.escape(kw) + r'\b'
                    if re.search(pattern, obs_lower):
                        scores[skill] += 1
    except Exception:
        pass

    # Return matching skills with score > 0, sorted descending
    matched = [skill for skill, score in scores.items() if score > 0]
    matched.sort(key=lambda s: scores[s], reverse=True)
    return matched
