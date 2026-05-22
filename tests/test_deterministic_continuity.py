import sys
import os
import time
# Add root workspace to PYTHONPATH
sys.path.append("c:/as-code")

from api.database import init_db, get_session
from api.memory_models import MemoryVariable, MemoryTask, MemoryObservation
from runtime.coordinator.models import RuntimeContract, WorkflowState, SessionSnapshot
from runtime.coordinator.manager import PureCoordinator
from runtime.coordinator.mutator import RuntimeStateMutator
from runtime.coordinator.language_detection import DeterministicLanguageDetector, LanguageCode
from runtime.coordinator.continuity_resolver import DeterministicContinuityResolver
from runtime.coordinator.state_store import LightweightStateStore

def test_deterministic_language_detection():
    detector = DeterministicLanguageDetector()
    
    # English keywords
    lang, conf = detector.detect("the quick brown fox jumped over the lazy dog", fallback_language="ES")
    assert lang == LanguageCode.EN
    assert conf >= 2
    
    # Spanish keywords & accents
    lang, conf = detector.detect("esta es una pregunta de prueba en español", fallback_language="EN")
    assert lang == LanguageCode.ES
    assert conf >= 2
    
    # Tie / Empty text fallback
    lang, conf = detector.detect("", fallback_language="EN")
    assert lang == LanguageCode.EN
    assert conf == 0

def test_continuity_resolver():
    resolver = DeterministicContinuityResolver()
    
    # Case 1: Short query without symbols/technical references -> should carry over key terms
    snapshot = SessionSnapshot(
        session_id="test_session",
        turn_number=1,
        rag_query_stack=["cuales son los dolores de los prospectos"],
        language_history=[("ES", 1)]
    )
    contract = RuntimeContract(
        request_id="req_001",
        session_id="test_session",
        turn_number=2,
        snapshot=snapshot,
        user_message="y los otros?",
        model_id="gemma-chat",
        timestamp=time.time()
    )
    
    decision = resolver.resolve(contract)
    assert decision.reset_triggered is False
    assert decision.detected_language == "ES"
    # Should extract key terms (excluding stopwords, len > 4) from previous: "dolores", "prospectos"
    assert "dolores" in decision.final_rag_query
    assert "prospectos" in decision.final_rag_query
    assert "y los otros?" in decision.final_rag_query
    
    # Case 2: Short query but contains symbols -> should NOT carry over (self-sufficient)
    contract.user_message = "db.commit()"
    decision = resolver.resolve(contract)
    assert decision.reset_triggered is True
    assert decision.reset_reason.value == "topic_change"
    assert decision.final_rag_query == "db.commit()"
    
    # Case 3: Long query (>= 6 words) -> should NOT carry over (self-sufficient)
    contract.user_message = "hola quiero analizar el nuevo flujo de ventas en la web"
    decision = resolver.resolve(contract)
    assert decision.reset_triggered is True
    assert decision.reset_reason.value == "word_threshold"
    assert decision.final_rag_query == "hola quiero analizar el nuevo flujo de ventas en la web"

def test_lightweight_state_store():
    # Setup test DB
    db_path = "data/test_continuity.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
            
    init_db(db_path)
    db = get_session()
    
    try:
        store = LightweightStateStore(db)
        session_id = "test_store_session"
        
        # Load initially clean state
        snapshot = store.load_session_state(session_id)
        assert snapshot.turn_number == 0
        assert len(snapshot.rag_query_stack) == 0
        assert len(snapshot.language_history) == 0
        
        # Persist a decision
        resolver = DeterministicContinuityResolver()
        contract = RuntimeContract(
            request_id="req_101",
            session_id=session_id,
            turn_number=1,
            snapshot=snapshot,
            user_message="cuales son los dolores de los prospectos",
            model_id="gemma-chat",
            timestamp=time.time()
        )
        decision = resolver.resolve(contract)
        
        ok = store.persist_decision(
            session_id=session_id,
            turn_number=1,
            final_rag_query=decision.final_rag_query,
            language=decision.detected_language,
            decision=decision,
            request_id="req_101"
        )
        assert ok is True
        
        # Reload state and verify
        snapshot_2 = store.load_session_state(session_id)
        assert snapshot_2.turn_number == 1
        assert snapshot_2.last_rag_query == "cuales son los dolores de los prospectos"
        assert snapshot_2.last_language == "ES"
        
    finally:
        # Cleanup
        bind = db.bind
        db.close()
        if bind:
            bind.dispose()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_full_assembly_and_mutation():
    db_path = "data/test_full_continuity.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
            
    init_db(db_path)
    db = get_session()
    
    try:
        session_id = "test_full_session"
        store = LightweightStateStore(db)
        snapshot = store.load_session_state(session_id)
        snapshot.turn_number += 1
        
        contract = RuntimeContract(
            request_id="req_201",
            session_id=session_id,
            turn_number=snapshot.turn_number,
            snapshot=snapshot,
            user_message="cuales son los dolores de los prospectos",
            model_id="gemma-chat",
            timestamp=time.time()
        )
        
        # Pure coordinator assembly
        coordinator = PureCoordinator()
        manifest = coordinator.assemble(
            db=db,
            contract=contract,
            skill_service=None,
            rag_service=None,
            memory_service=None,
            enable_rag=False
        )
        
        assert manifest.continuity_decision is not None
        assert manifest.continuity_decision.final_rag_query == "cuales son los dolores de los prospectos"
        assert manifest.continuity_decision.detected_language == "ES"
        
        # Apply state mutations (calls state store persistence internally)
        RuntimeStateMutator.apply_state_mutations(db, contract, manifest)
        
        # Verify it was persisted correctly in DB
        snapshot_after = store.load_session_state(session_id)
        assert snapshot_after.turn_number == 1
        assert snapshot_after.last_rag_query == "cuales son los dolores de los prospectos"
        assert snapshot_after.last_language == "ES"
        
    finally:
        # Cleanup
        bind = db.bind
        db.close()
        if bind:
            bind.dispose()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

if __name__ == "__main__":
    test_deterministic_language_detection()
    test_continuity_resolver()
    test_lightweight_state_store()
    test_full_assembly_and_mutation()
    print("ALL TESTS PASSED SUCCESSFULLY!")
