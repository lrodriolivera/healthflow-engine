"""Tests para el transformation engine."""

import pytest

from backend.app.core.hl7.parser import HL7Message
from backend.app.core.transform.engine import TransformRegistry
from backend.app.core.transform.sandbox import (
    compile_transform,
    execute_transform,
    CompilationError,
    ExecutionError,
)
from backend.app.core.transform.samples import SAMPLES


ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR||GONZALEZ^MARIA||19800115|F|||AV LIBERTADOR^^SANTIAGO||+56912345678|+56228889999||||12345678-9\r"
    "NK1|1|GONZALEZ^PEDRO|SPO|AV LIBERTADOR^^SANTIAGO||+56911111111\r"
    "PV1|1|I|SALA301^CAMA1"
)

OML_O21 = (
    "MSH|^~\\&|MODULAB|LAB|IRIS|UCCHRISTUS|20260408130000||OML^O21|MSG002|P|2.5\r"
    "PID|1||PAC456^^^MPI^MR||PEREZ^CARLOS||19750320|M\r"
    "ORC|NW|ORD001|SOL001||CM\r"
    "OBR|1|ORD001|SOL001|HEMO^Hemograma completo\r"
    "ORC|NW|ORD002|SOL002||CM\r"
    "OBR|2|ORD002|SOL002|GLUC^Glicemia"
)


class TestCompileTransform:
    """Tests de compilación en sandbox."""

    def test_compile_simple(self):
        code = "def transform(msg, lookup):\n    return msg.clone()"
        fn = compile_transform(code)
        assert callable(fn)

    def test_compile_missing_transform_func(self):
        code = "def process(msg, lookup):\n    return msg"
        with pytest.raises(CompilationError, match="must define"):
            compile_transform(code)

    def test_compile_syntax_error(self):
        code = "def transform(msg lookup):\n    return msg"
        with pytest.raises(CompilationError, match="Syntax error"):
            compile_transform(code)

    def test_compile_blocks_import(self):
        code = "import os\ndef transform(msg, lookup):\n    return msg"
        with pytest.raises(CompilationError, match="import"):
            compile_transform(code)

    def test_compile_blocks_from_import(self):
        code = "from pathlib import Path\ndef transform(msg, lookup):\n    return msg"
        with pytest.raises(CompilationError, match="import"):
            compile_transform(code)

    def test_compile_blocks_dunder_builtins(self):
        code = "def transform(msg, lookup):\n    return __builtins__"
        with pytest.raises(CompilationError, match="__builtins__"):
            compile_transform(code)

    def test_compile_blocks_eval(self):
        code = "def transform(msg, lookup):\n    return eval('1+1')"
        with pytest.raises(CompilationError, match="eval"):
            compile_transform(code)

    def test_compile_blocks_exec(self):
        code = "def transform(msg, lookup):\n    exec('pass')\n    return msg"
        with pytest.raises(CompilationError, match="exec"):
            compile_transform(code)

    def test_compile_blocks_open(self):
        code = "def transform(msg, lookup):\n    f = open('/etc/passwd')\n    return msg"
        with pytest.raises(CompilationError, match="open"):
            compile_transform(code)

    def test_compile_blocks_subprocess(self):
        code = "def transform(msg, lookup):\n    subprocess.run('ls')\n    return msg"
        with pytest.raises(CompilationError, match="subprocess"):
            compile_transform(code)

    def test_compile_blocks_os(self):
        code = "def transform(msg, lookup):\n    x = os.system('ls')\n    return msg"
        with pytest.raises(CompilationError, match="os module"):
            compile_transform(code)


class TestExecuteTransform:
    """Tests de ejecución en sandbox."""

    def test_execute_passthrough(self):
        code = "def transform(msg, lookup):\n    return msg.clone()"
        fn = compile_transform(code)
        msg = HL7Message.parse(ADT_A08)
        result = execute_transform(fn, msg)
        assert result.message_type == msg.message_type
        assert result.message_control_id == msg.message_control_id

    def test_execute_modify_field(self):
        code = (
            "def transform(msg, lookup):\n"
            "    msg = msg.clone()\n"
            "    msg.set('MSH-5', 'NEW_APP')\n"
            "    return msg"
        )
        fn = compile_transform(code)
        msg = HL7Message.parse(ADT_A08)
        result = execute_transform(fn, msg)
        assert result.get("MSH-5") == "NEW_APP"
        assert msg.get("MSH-5") == "IRIS"  # Original unchanged

    def test_execute_with_lookup(self):
        code = (
            "def transform(msg, lookup):\n"
            "    msg = msg.clone()\n"
            "    mapped = lookup('apps', msg.get('MSH-3'))\n"
            "    if mapped:\n"
            "        msg.set('MSH-3', mapped)\n"
            "    return msg"
        )
        fn = compile_transform(code)
        msg = HL7Message.parse(ADT_A08)

        def test_lookup(table, key):
            if table == "apps" and key == "SAP":
                return "SAP-ENTERPRISE"
            return ""

        result = execute_transform(fn, msg, lookup=test_lookup)
        assert result.get("MSH-3") == "SAP-ENTERPRISE"

    def test_execute_wrong_return_type(self):
        code = "def transform(msg, lookup):\n    return 'not a message'"
        fn = compile_transform(code)
        msg = HL7Message.parse(ADT_A08)
        with pytest.raises(ExecutionError, match="must return HL7Message"):
            execute_transform(fn, msg)

    def test_execute_runtime_error(self):
        code = "def transform(msg, lookup):\n    raise ValueError('test error')"
        fn = compile_transform(code)
        msg = HL7Message.parse(ADT_A08)
        with pytest.raises(ExecutionError, match="test error"):
            execute_transform(fn, msg)


class TestTransformRegistry:
    """Tests del registry de transforms."""

    def test_register_and_get(self):
        registry = TransformRegistry()
        code = "def transform(msg, lookup):\n    return msg.clone()"
        ct = registry.register("passthrough", code)
        assert ct.name == "passthrough"
        assert ct.version == 1
        assert registry.count == 1

    def test_get_missing(self):
        registry = TransformRegistry()
        assert registry.get("nonexistent") is None

    def test_execute_by_name(self):
        registry = TransformRegistry()
        code = (
            "def transform(msg, lookup):\n"
            "    msg = msg.clone()\n"
            "    msg.set('MSH-5', 'REGISTRY_TEST')\n"
            "    return msg"
        )
        registry.register("test_transform", code)
        msg = HL7Message.parse(ADT_A08)
        result = registry.execute("test_transform", msg)
        assert result.get("MSH-5") == "REGISTRY_TEST"

    def test_execute_missing_raises(self):
        registry = TransformRegistry()
        msg = HL7Message.parse(ADT_A08)
        with pytest.raises(ValueError, match="not found"):
            registry.execute("nonexistent", msg)

    def test_unregister(self):
        registry = TransformRegistry()
        code = "def transform(msg, lookup):\n    return msg.clone()"
        registry.register("temp", code)
        assert registry.unregister("temp") is True
        assert registry.count == 0

    def test_list_names(self):
        registry = TransformRegistry()
        code = "def transform(msg, lookup):\n    return msg.clone()"
        registry.register("a", code)
        registry.register("b", code)
        assert set(registry.list_names()) == {"a", "b"}


class TestSampleTransforms:
    """Tests para las transformaciones de ejemplo."""

    def test_remap_sending_app(self):
        registry = TransformRegistry()
        registry.register("remap", SAMPLES["remap_sending_app"])
        msg = HL7Message.parse(ADT_A08)

        def lookup(table, key):
            if table == "app_mapping" and key == "SAP":
                return "SAP-HF"
            return ""

        result = registry.execute("remap", msg, lookup=lookup)
        assert result.get("MSH-3") == "SAP-HF"
        assert result.get("MSH-5") == "HEALTHFLOW"

    def test_add_zhf_segment(self):
        registry = TransformRegistry()
        registry.register("add_zhf", SAMPLES["add_zhf_segment"])
        msg = HL7Message.parse(ADT_A08)
        result = registry.execute("add_zhf", msg)

        zhf = result.get_segment("ZHF")
        assert zhf is not None
        assert zhf.get_field(1) == "HEALTHFLOW"
        assert zhf.get_field(3) == "MSG001"
        # ZHF debe estar después de MSH
        assert result.segments[1].name == "ZHF"

    def test_strip_pii(self):
        registry = TransformRegistry()
        registry.register("strip_pii", SAMPLES["strip_pii"])
        msg = HL7Message.parse(ADT_A08)

        # Verify PII exists before
        assert msg.get("PID-13") != ""
        assert msg.count_segments("NK1") == 1

        result = registry.execute("strip_pii", msg)

        # PII stripped
        assert result.get("PID-13") == ""
        assert result.get("PID-14") == ""
        assert result.get("PID-19") == ""
        assert result.count_segments("NK1") == 0

        # Original unchanged
        assert msg.get("PID-13") != ""
        assert msg.count_segments("NK1") == 1

    def test_translate_procedure_codes(self):
        registry = TransformRegistry()
        registry.register("translate", SAMPLES["translate_procedure_codes"])
        msg = HL7Message.parse(OML_O21)

        def lookup(table, key):
            codes = {"HEMO": "Complete Blood Count", "GLUC": "Blood Glucose"}
            if table == "procedure_codes":
                return codes.get(key, "")
            return ""

        result = registry.execute("translate", msg, lookup=lookup)
        assert "Complete Blood Count" in result.get("OBR-4", segment_index=0)
        assert "Blood Glucose" in result.get("OBR-4", segment_index=1)

    def test_all_samples_compile(self):
        """Todos los samples deben compilar sin error."""
        registry = TransformRegistry()
        for name, code in SAMPLES.items():
            ct = registry.register(name, code)
            assert ct.name == name
