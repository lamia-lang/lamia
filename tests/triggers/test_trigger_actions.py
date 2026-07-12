"""Tests for trigger actions and AST transformation."""

import ast
import json
from pathlib import Path

import pytest

from lamia.actions.trigger import TriggerActions, TriggerRejectError
from lamia.triggers.cli import extract_all_triggers
from lamia.interpreter.transformers.syntax_transformer import HybridSyntaxTransformer


class TestTriggerResolve:
    """Test TriggerActions._resolve() reads from LAMIA_TRIGGER_EVENT env var."""

    def test_resolve_returns_event_data(self, monkeypatch):
        payload = json.dumps({"sender": "alice@x.com", "subject": "Hello"})
        monkeypatch.setenv("LAMIA_TRIGGER_EVENT", payload)
        actions = TriggerActions()
        data = actions._resolve("email_received")
        assert data["sender"] == "alice@x.com"
        assert data["subject"] == "Hello"

    def test_resolve_no_env_returns_empty_dict(self, monkeypatch):
        monkeypatch.delenv("LAMIA_TRIGGER_EVENT", raising=False)
        actions = TriggerActions()
        data = actions._resolve("email_received")
        assert data == {}

    def test_resolve_file_event(self, monkeypatch):
        payload = json.dumps({"name": "report.csv", "size": 1024, "content_type": "text/csv"})
        monkeypatch.setenv("LAMIA_TRIGGER_EVENT", payload)
        actions = TriggerActions()
        data = actions._resolve("file_created")
        assert data["name"] == "report.csv"
        assert data["size"] == 1024


class TestTriggerASTTransformation:
    """Test that trigger.method(params) is transformed into variable assignments."""

    def _transform(self, source: str) -> str:
        tree = ast.parse(source)
        transformer = HybridSyntaxTransformer(lamia_var_name="lamia")
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)

    def test_email_received_bare_names(self):
        source = 'trigger.email_received(sender, subject, body)'
        result = self._transform(source)
        assert "_trigger_data = trigger._resolve('email_received')" in result
        assert "sender = _trigger_data['sender']" in result
        assert "subject = _trigger_data['subject']" in result
        assert "body = _trigger_data['body']" in result

    def test_file_created_with_config_param(self):
        source = 'trigger.file_created(name, size, path="my-bucket")'
        result = self._transform(source)
        assert "_trigger_data = trigger._resolve('file_created')" in result
        assert "name = _trigger_data['name']" in result
        assert "size = _trigger_data['size']" in result
        assert "path = _trigger_data" not in result

    def test_config_param_not_assigned(self):
        source = 'trigger.file_created(name, size, content_type, path="invoices-bucket")'
        result = self._transform(source)
        lines = result.strip().split('\n')
        assigned_vars = [l.split(' = _trigger_data')[0].strip() for l in lines if '_trigger_data[' in l]
        assert "name" in assigned_vars
        assert "size" in assigned_vars
        assert "content_type" in assigned_vars
        assert "path" not in assigned_vars

    def test_no_params_no_assignments(self):
        source = 'trigger.email_received()'
        result = self._transform(source)
        assert "_trigger_data = trigger._resolve('email_received')" in result
        assert "_trigger_data[" not in result

    def test_non_trigger_code_unchanged(self):
        source = 'print("hello")'
        result = self._transform(source)
        assert "print('hello')" in result
        assert "trigger" not in result


class TestTriggerEndToEnd:
    """Test full flow: env var -> _resolve -> variable access."""

    def test_email_full_flow(self, monkeypatch):
        payload = json.dumps({
            "sender": "bob@example.com",
            "subject": "Invoice #42",
            "body": "Please find attached.",
        })
        monkeypatch.setenv("LAMIA_TRIGGER_EVENT", payload)
        actions = TriggerActions()
        data = actions._resolve("email_received")
        sender = data["sender"]
        subject = data["subject"]
        body = data["body"]
        assert sender == "bob@example.com"
        assert subject == "Invoice #42"
        assert body == "Please find attached."


class TestExtractAllTriggers:
    """Test AST extraction of trigger calls from scripts."""

    def test_extracts_email_received(self, tmp_path):
        script = tmp_path / "email_handler.lm"
        script.write_text("trigger.email_received(sender, subject, body)\nprint(sender)")
        stages = extract_all_triggers(script)
        assert len(stages) == 1
        assert stages[0].trigger_method == "email_received"
        assert stages[0].output_bindings == ["sender", "subject", "body"]

    def test_extracts_file_created_with_path(self, tmp_path):
        script = tmp_path / "file_handler.lm"
        script.write_text('trigger.file_created(name, size, path="my-bucket")\nprint(name)')
        stages = extract_all_triggers(script)
        assert len(stages) == 1
        assert stages[0].trigger_method == "file_created"
        assert stages[0].trigger_config == {"path": "my-bucket"}
        assert stages[0].output_bindings == ["name", "size"]

    def test_no_trigger_returns_empty(self, tmp_path):
        script = tmp_path / "no_trigger.lm"
        script.write_text('print("hello")')
        stages = extract_all_triggers(script)
        assert stages == []

    def test_syntax_error_returns_empty(self, tmp_path):
        script = tmp_path / "broken.lm"
        script.write_text("def foo(:\n  pass")
        stages = extract_all_triggers(script)
        assert stages == []

    def test_multi_trigger_script(self, tmp_path):
        script = tmp_path / "multi.lm"
        script.write_text(
            'trigger.email_received(sender, subject)\n'
            'result = classify(sender)\n'
            'trigger.file_created(name, path="bucket")\n'
            'process(name)\n'
        )
        stages = extract_all_triggers(script)
        assert len(stages) == 2
        assert stages[0].trigger_method == "email_received"
        assert stages[0].stage_index == 0
        assert stages[1].trigger_method == "file_created"
        assert stages[1].stage_index == 1
        assert stages[1].trigger_config == {"path": "bucket"}


class TestTriggerReject:
    """Test trigger.reject() raises TriggerRejectError."""

    def test_reject_raises_trigger_reject_error(self):
        actions = TriggerActions()
        with pytest.raises(TriggerRejectError):
            actions.reject()

    def test_reject_error_is_not_generic_exception(self):
        assert not issubclass(TriggerRejectError, (ValueError, RuntimeError))
