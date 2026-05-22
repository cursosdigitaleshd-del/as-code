import logging
from typing import Tuple, Optional
from runtime.coordinator.models import (
    RuntimeContract, ContinuityDecision, ResetReason, SessionSnapshot
)
from runtime.coordinator.language_detection import (
    DeterministicLanguageDetector, LanguageCode
)

logger = logging.getLogger("as-code.runtime.coordinator.resolver")

class DeterministicContinuityResolver:
    """
    Resolver de continuidad 100% determinístico y ultra-rápido, libre de ML y NLP pesado.
    Evalúa la suficiencia de la consulta actual e inyecta palabras clave del tema anterior.
    """
    
    def __init__(self):
        self.language_detector = DeterministicLanguageDetector()
        
    def resolve(self, contract: RuntimeContract) -> ContinuityDecision:
        """
        Resuelve continuidad temática e idioma de manera determinista.
        """
        current_message = contract.user_message.strip()
        snapshot = contract.snapshot or SessionSnapshot(
            session_id=contract.session_id,
            turn_number=contract.turn_number
        )
        
        # === PASO 1: Resolver Idioma ===
        detected_lang, lang_confidence = self.language_detector.detect(
            current_message,
            fallback_language=snapshot.last_language
        )
        
        is_lang_confident = self.language_detector.is_confident(
            lang_confidence,
            threshold=contract.language_confidence_threshold
        )
        
        if not is_lang_confident:
            detected_lang = LanguageCode(snapshot.last_language)
            
        # === PASO 2: Evaluar Auto-suficiencia ===
        is_self_sufficient, reset_reason = self._is_self_sufficient(
            current_message,
            contract.explicit_reset
        )
        
        # === PASO 3: Fusión o Reseteo ===
        if is_self_sufficient or reset_reason != ResetReason.NONE:
            final_rag_query = current_message
            merge_ratio = 0.0
            reset_triggered = True
        else:
            final_rag_query, merge_ratio = self._merge_queries(
                previous=snapshot.last_rag_query,
                current=current_message,
                max_ratio=snapshot.merge_max_ratio
            )
            reset_triggered = False
            reset_reason = ResetReason.NONE
            
        # === PASO 4: Validar Límites ===
        query_word_count = len(final_rag_query.split())
        query_char_count = len(final_rag_query)
        
        if query_char_count > snapshot.max_query_chars:
            final_rag_query = current_message
            reset_triggered = True
            reset_reason = ResetReason.LENGTH_OVERFLOW
            merge_ratio = 0.0
        elif query_word_count > snapshot.max_query_words:
            final_rag_query = current_message
            reset_triggered = True
            reset_reason = ResetReason.WORD_THRESHOLD
            merge_ratio = 0.0
            
        return ContinuityDecision(
            final_rag_query=final_rag_query,
            detected_language=detected_lang.value,
            reset_triggered=reset_triggered,
            reset_reason=reset_reason,
            merge_ratio=merge_ratio,
            query_word_count=len(final_rag_query.split()),
            query_char_count=len(final_rag_query),
            language_confidence=lang_confidence
        )
        
    def _is_self_sufficient(
        self,
        message: str,
        explicit_reset: bool
    ) -> Tuple[bool, ResetReason]:
        """
        Determina si una consulta es auto-suficiente y no requiere carryover conversacional.
        """
        if explicit_reset:
            return True, ResetReason.EXPLICIT
            
        message_lower = message.lower()
        if any(message_lower.startswith(cmd) for cmd in ['/reset', '/new', '/clear', '/context']):
            return True, ResetReason.EXPLICIT
            
        # Criterio 2: Longitud >= 6 palabras (indica pregunta nueva/descriptiva)
        words = message.split()
        word_count = len(words)
        if word_count >= 6:
            return True, ResetReason.WORD_THRESHOLD
            
        # Criterio 3: Densidad técnica (presencia de símbolos especiales o código)
        technical_chars = sum(1 for c in message if c in '@#$%^&*[]{}()_-+=./\\')
        if technical_chars >= 3:
            return True, ResetReason.TOPIC_CHANGE
            
        return False, ResetReason.NONE
        
    def _merge_queries(
        self,
        previous: Optional[str],
        current: str,
        max_ratio: float = 0.7
    ) -> Tuple[str, float]:
        """
        Fusiona la consulta anterior con la actual eliminando palabras vacías y
        conservando términos conceptuales de alta entropía. Sin heurísticas posicionales.
        """
        if not previous:
            return current, 0.0
            
        # Conjunto de stopwords combinado de ambos idiomas
        stop_words = self.language_detector.SPANISH_KEYWORDS | self.language_detector.ENGLISH_KEYWORDS
        
        # Limpiar y tokenizar consulta previa
        prev_words = previous.lower().split()
        
        # Extraer términos clave: palabras que no sean stopwords, de longitud > 4, o con caracteres técnicos
        key_terms = []
        for w in prev_words:
            # Limpiar puntuación común
            w_clean = w.strip("?,.!-()\"'¿¡")
            if w_clean not in stop_words and (len(w_clean) > 4 or any(c in w_clean for c in ['.', '_', '/'])):
                if w_clean not in key_terms:
                    key_terms.append(w_clean)
                    
        if not key_terms:
            return current, 0.0
            
        # Preponer las palabras clave únicas de la query previa a la query actual
        merged = f"{' '.join(key_terms)} {current}"
        
        # Calcular ratio de mezcla
        merge_ratio = len(' '.join(key_terms)) / (len(merged) + 1)
        
        # Evitar carryover excesivo
        if merge_ratio > max_ratio:
            return current, 0.0
            
        return merged, merge_ratio
