from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser


def test_web_click_transforms_to_uppercase_enum():
    parser = HybridSyntaxParser()
    source = """
def foo():
    web.click("button")
"""
    transformed = parser.transform(source)
    assert "WebActionType.CLICK" in transformed


