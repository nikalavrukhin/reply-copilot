from redact import redact, unmask

def test_labels():
    t = redact("mail me: a.b@x.com, +1 415 555 0100, card 4111 1111 1111 1111, password: hunter2")
    assert "a.b@x.com" not in t and "415" not in t and "4111" not in t and "hunter2" not in t

def test_roundtrip():
    v = {}
    src = "write to a.b@x.com or call +1 415 555 0100"
    assert unmask(redact(src, v), v) == src
