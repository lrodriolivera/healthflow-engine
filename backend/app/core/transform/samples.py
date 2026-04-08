"""
Transformaciones de ejemplo que ejercitan el engine.

Estas sirven para testing y como referencia para el TransformDesigner agent.
"""

# 1. Remap de aplicación emisora/receptora
REMAP_SENDING_APP = '''
def transform(msg, lookup):
    """Remapear MSH-3 (sending app) y MSH-5 (receiving app) para un destino."""
    msg = msg.clone()
    original_app = msg.get("MSH-3")
    mapped_app = lookup("app_mapping", original_app)
    if mapped_app:
        msg.set("MSH-3", mapped_app)
    msg.set("MSH-5", "HEALTHFLOW")
    return msg
'''

# 2. Traducción de códigos de procedimiento via lookup
TRANSLATE_PROCEDURE_CODES = '''
def transform(msg, lookup):
    """Traducir códigos de procedimiento en OBR-4 usando lookup table."""
    msg = msg.clone()
    segments = msg.get_all_segments("OBR")
    for seg in segments:
        code = seg.get_component(4, 1)
        if code:
            translated = lookup("procedure_codes", code)
            if translated:
                current = seg.get_field(4)
                parts = current.split("^")
                if len(parts) >= 2:
                    parts[1] = translated
                    seg.set_field(4, "^".join(parts))
    return msg
'''

# 3. Agregar segmento ZHF (custom HealthFlow metadata)
ADD_ZHF_SEGMENT = '''
def transform(msg, lookup):
    """Agregar Z-segment con metadata de HealthFlow."""
    msg = msg.clone()
    zhf = HL7Segment(
        name="ZHF",
        fields=["HEALTHFLOW", "1.0", msg.get("MSH-10")],
    )
    msg.add_segment(zhf, after="MSH")
    return msg
'''

# 4. Filtrar campos sensibles (PII stripping)
STRIP_PII = '''
def transform(msg, lookup):
    """Remover datos sensibles del paciente para destinos externos."""
    msg = msg.clone()
    pid = msg.get_segment("PID")
    if pid:
        pid.set_field(13, "")  # Phone
        pid.set_field(14, "")  # Business phone
        pid.set_field(19, "")  # SSN
    nk1_count = msg.count_segments("NK1")
    for i in range(nk1_count - 1, -1, -1):
        msg.remove_segment("NK1", i)
    return msg
'''

# Registry de samples para testing
SAMPLES = {
    "remap_sending_app": REMAP_SENDING_APP,
    "translate_procedure_codes": TRANSLATE_PROCEDURE_CODES,
    "add_zhf_segment": ADD_ZHF_SEGMENT,
    "strip_pii": STRIP_PII,
}
