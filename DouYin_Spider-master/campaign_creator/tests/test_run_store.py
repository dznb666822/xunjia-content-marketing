"""Unit tests for RunStore and RunID/RunMetadata models."""

import json
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.campaign_models import (
    CampaignRequest,
    CampaignChannel,
    CopyTone,
    RunID,
    RunMetadata,
)


class TestRunID:
    """Tests for RunID generation and validation."""
    
    def test_generate_creates_valid_format(self):
        """RunID.generate() creates properly formatted ID."""
        run_id = RunID.generate()
        
        # Check format: YYYYMMDDTHHMMSS-xxxxx
        # 8 + 1 + 6 + 1 + 5 = 21 (seconds are 2 digits)
        assert len(str(run_id)) == 21
        assert str(run_id).count("-") == 1
        parts = str(run_id).split("-")
        assert len(parts[0]) == 15  # YYYYMMDDTHHMMSS
        assert len(parts[1]) == 5   # xxxxx
    
    def test_validate_accepts_valid_value(self):
        """Valid RunID values are accepted."""
        valid_id = "20260415T093045-a7x2m"
        run_id = RunID(value=valid_id)
        assert run_id.value == valid_id
    
    def test_validate_rejects_invalid_format(self):
        """Invalid RunID formats are rejected."""
        with pytest.raises(ValueError, match="Invalid RunID format"):
            RunID(value="invalid")
        
        with pytest.raises(ValueError, match="Invalid RunID format"):
            RunID(value="20260415-noformat")
        
        with pytest.raises(ValueError, match="Invalid RunID format"):
            RunID(value="20260415T093045-abcde-fextra")
    
    def test_hash_allows_dict_usage(self):
        """RunID can be used as dict key."""
        run_id = RunID.generate()
        d = {run_id: "test_value"}
        assert d[run_id] == "test_value"
    
    def test_str_returns_value(self):
        """str(RunID) returns the value."""
        run_id = RunID(value="20260415T093045-a7x2m")
        assert str(run_id) == "20260415T093045-a7x2m"


class TestRunMetadata:
    """Tests for RunMetadata model."""
    
    def test_default_values(self):
        """RunMetadata has correct defaults."""
        run_id = RunID.generate()
        metadata = RunMetadata(run_id=run_id)
        
        assert metadata.status == "pending"
        assert metadata.retry_count == 0
        assert metadata.end_time is None
        assert metadata.terminal_failure_reason is None
        assert metadata.parent_run_id is None
        assert metadata.config_snapshot == {}
        assert metadata.artifacts == []
    
    def test_validate_status_rejects_invalid(self):
        """Invalid status values are rejected."""
        run_id = RunID.generate()
        
        with pytest.raises(ValueError, match="Invalid status"):
            RunMetadata(run_id=run_id, status="invalid")
    
    def test_accepts_valid_statuses(self):
        """Valid status values are accepted."""
        run_id = RunID.generate()
        
        for status in ["pending", "running", "success", "failed"]:
            metadata = RunMetadata(run_id=run_id, status=status)
            assert metadata.status == status


# Integration tests need actual RunStore
class TestRunStoreIntegration:
    """Integration tests for RunStore with SQLite."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_runs.db"
            yield db_path
            # Cleanup happens automatically
    
    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        from src.runtime.run_store import RunStore
        store = RunStore(db_path=temp_db)
        yield store
        store.close()
    
    @pytest.fixture
    def sample_request(self):
        """Create sample CampaignRequest."""
        return CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
    
    def test_init_db_creates_tables(self, store):
        """init_db creates runs and artifacts tables."""
        conn = store._get_connection()
        cursor = conn.cursor()
        
        # Check runs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
        assert cursor.fetchone() is not None
        
        # Check artifacts table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
        assert cursor.fetchone() is not None
    
    def test_init_db_idempotent(self, store):
        """init_db can be called multiple times."""
        store.init_db()
        store.init_db()  # Should not raise
    
    def test_create_run(self, store, sample_request):
        """create_run inserts a new run record."""
        run_id = RunID.generate()
        metadata = store.create_run(run_id, sample_request)
        
        assert metadata.status == "pending"
        assert metadata.retry_count == 0
        assert metadata.run_id == run_id
    
    def test_get_run_retrieves_record(self, store, sample_request):
        """get_run retrieves the created run."""
        run_id = RunID.generate()
        store.create_run(run_id, sample_request)
        
        retrieved = store.get_run(run_id)
        
        assert retrieved is not None
        assert retrieved.run_id.value == run_id.value  # Compare values, not objects (microseconds differ)
        assert retrieved.status == "pending"
    
    def test_get_run_returns_none_if_not_found(self, store):
        """get_run returns None for non-existent run."""
        run_id = RunID.generate()
        result = store.get_run(run_id)
        assert result is None
    
    def test_update_run_status(self, store, sample_request):
        """update_run_status updates the status."""
        run_id = RunID.generate()
        store.create_run(run_id, sample_request)
        
        updated = store.update_run_status(
            run_id,
            status="success",
            end_time=datetime.utcnow()
        )
        
        assert updated.status == "success"
        assert updated.end_time is not None
    
    def test_record_artifact(self, store, sample_request):
        """record_artifact links artifact to run."""
        run_id = RunID.generate()
        store.create_run(run_id, sample_request)
        
        artifact_hash = hashlib.sha256(b"test content").hexdigest()
        store.record_artifact(run_id, "output/test.md", artifact_hash)
        
        retrieved = store.get_run(run_id)
        assert len(retrieved.artifacts) == 1
        assert retrieved.artifacts[0]["path"] == "output/test.md"
        assert retrieved.artifacts[0]["content_hash"] == artifact_hash
    
    def test_config_snapshot_excludes_api_keys(self, store):
        """Config snapshot excludes API keys for security."""
        request = CampaignRequest(
            product_name="Test",
            product_description="Test",
            target_audience="Test",
            campaign_goals="Test",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        
        run_id = RunID.generate()
        store.create_run(run_id, request)
        
        retrieved = store.get_run(run_id)
        
        # Should not contain actual API keys
        config = retrieved.config_snapshot
        assert "groq_api_key" not in str(config)
        assert "serper_api_key" not in str(config)
    
    def test_parent_child_run_chain(self, store, sample_request):
        """Parent run ID creates child run linkage."""
        parent_id = RunID.generate()
        store.create_run(parent_id, sample_request)
        
        child_id = RunID.generate()
        store.create_run(child_id, sample_request, parent_run_id=parent_id)
        
        children = store.get_runs_by_parent(parent_id)
        
        assert len(children) == 1
        assert children[0].run_id.value == child_id.value  # Compare values


class TestCampaignCrewIntegration:
    """Integration tests for CampaignCrew with RunStore."""
    
    @pytest.fixture
    def mock_store(self):
        """Create mocked RunStore."""
        store = MagicMock()
        store.create_run = MagicMock(return_value=RunMetadata(
            run_id=RunID.generate(),
            status="pending"
        ))
        store.update_run_status = MagicMock()
        store.record_artifact = MagicMock()
        return store
    
    def test_crew_generates_run_id(self, mock_store):
        """CampaignCrew generates a valid RunID on initialization."""
        from src.workflow.crew_workflow import CampaignCrew

        request = CampaignRequest(
            product_name="Test",
            product_description="Test",
            target_audience="Test",
            campaign_goals="Test",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )

        # Real construction (no LLM call until .run()); store is mocked.
        crew = CampaignCrew(request, store=mock_store)

        assert isinstance(crew.run_id, RunID)
        assert crew.run_id.value  # format-validated by the RunID model
    
    def test_crew_accepts_store_parameter(self, mock_store):
        """CampaignCrew accepts optional store parameter."""
        from src.workflow.crew_workflow import CampaignCrew
        
        request = CampaignRequest(
            product_name="Test",
            product_description="Test",
            target_audience="Test",
            campaign_goals="Test",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        
        # Verify signature accepts store parameter
        import inspect
        sig = inspect.signature(CampaignCrew.__init__)
        params = list(sig.parameters.keys())

        assert 'store' in params  # Signature must expose the store parameter

    def test_crew_records_parent_run_id(self, mock_store):
        """CampaignCrew stores the parent_run_id for rerun linkage (D-08)."""
        from src.workflow.crew_workflow import CampaignCrew

        request = CampaignRequest(
            product_name="Test",
            product_description="Test",
            target_audience="Test",
            campaign_goals="Test",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        parent = RunID.generate()

        crew = CampaignCrew(request, store=mock_store, parent_run_id=parent)

        assert crew.parent_run_id == parent
        # And it defaults to None when omitted (top-level run).
        assert CampaignCrew(request, store=mock_store).parent_run_id is None


class TestRunIDEquality:
    """RunID hash/equality contract."""

    def test_equal_when_value_matches_regardless_of_created_at(self):
        from datetime import datetime

        a = RunID(value="20260415T093045-a7x2m",
                  created_at=datetime(2026, 4, 15, 9, 30, 45))
        b = RunID(value="20260415T093045-a7x2m",
                  created_at=datetime(2026, 4, 15, 9, 30, 46))

        assert a == b                       # equality keys on value only
        assert hash(a) == hash(b)           # consistent with __hash__
        assert {a, b} == {a}                # usable as set/dict keys

    def test_not_equal_when_value_differs(self):
        a = RunID.generate()
        b = RunID.generate()
        assert a != b
        assert a != "not-a-runid"