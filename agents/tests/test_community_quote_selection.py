import re

from agents.communities import find_quote


def test_descriptive_condition_mention_is_not_silently_dropped():
    # No organization words, and far from the scorer's preferred line length.
    # It must reach review, which can still reject insufficient membership proof.
    text = "Navigation\nNF1 is one of the genetic conditions described on this page.\nOther text"
    start, end = find_quote(text, [re.compile(r"\bNF1\b")])
    assert text[start:end] == "NF1 is one of the genetic conditions described on this page."
    assert find_quote(text, [re.compile(r"\bNF2\b")]) is None
