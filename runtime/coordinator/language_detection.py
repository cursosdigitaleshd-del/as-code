from typing import Tuple
from enum import Enum

class LanguageCode(str, Enum):
    ES = "ES"
    EN = "EN"

class DeterministicLanguageDetector:
    """
    Detector de idioma 100% determinístico, sin ML ni modelos pesados.
    Basado en conteo de palabras clave congeladas y caracteres especiales.
    
    CRITICAL RULE:
    The keyword sets are FROZEN and minimal. Do NOT add verbs, nouns, or domain-specific terminology.
    Only add core structural prepositions, conjunctions, and articles if absolutely necessary.
    """
    
    # Palabras clave españolas
    SPANISH_KEYWORDS = {
        'de', 'para', 'con', 'que', 'por', 'los', 'la', 'el', 'este',
        'ese', 'esto', 'eso', 'como', 'si', 'en', 'a', 'o', 'y', 'pero',
        'aunque', 'porque', 'cuando', 'donde', 'quien', 'cual', 'cuanto',
        'qué', 'está', 'están', 'es', 'son', 'tengo', 'tiene', 'tenemos',
        'tienes', 'tienen', 'puedo', 'puede', 'podemos', 'pueden',
        'debo', 'debe', 'debemos', 'deben', 'hago', 'hace', 'hacemos'
    }
    
    # Palabras clave inglesas
    ENGLISH_KEYWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'for', 'with', 'to', 'of',
        'in', 'on', 'at', 'by', 'from', 'is', 'are', 'was', 'were', 'be',
        'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'will',
        'would', 'should', 'may', 'might', 'must', 'that', 'this', 'which',
        'who', 'what', 'where', 'when', 'why', 'how'
    }
    
    # Caracteres españoles exclusivos (acentos, puntuación)
    SPANISH_CHARS = {'á', 'é', 'í', 'ó', 'ú', 'ñ', '¿', '¡'}
    
    def detect(
        self,
        text: str,
        fallback_language: str = LanguageCode.ES
    ) -> Tuple[LanguageCode, int]:
        """
        Detecta idioma de manera determinista.
        Retorna: (language_code, confidence_score)
        """
        if not text or len(text.strip()) == 0:
            return LanguageCode(fallback_language), 0
        
        words = text.lower().split()
        
        # Contar palabras clave
        es_keywords_found = sum(1 for w in words if w in self.SPANISH_KEYWORDS)
        en_keywords_found = sum(1 for w in words if w in self.ENGLISH_KEYWORDS)
        
        # Bonus por caracteres especiales españoles
        if any(c in text for c in self.SPANISH_CHARS):
            es_keywords_found += 1
            
        # Decisión
        if es_keywords_found > en_keywords_found:
            return LanguageCode.ES, es_keywords_found
        elif en_keywords_found > es_keywords_found:
            return LanguageCode.EN, en_keywords_found
        else:
            return LanguageCode(fallback_language), 0
            
    def is_confident(self, confidence_score: int, threshold: int = 2) -> bool:
        """Determina si la detección supera el umbral de confianza establecido."""
        return confidence_score >= threshold
