from __future__ import annotations
import socket
from trenton_offline_maps import countries,svg_map

def test_offline(monkeypatch):
    def blocked(*args,**kwargs): raise AssertionError('network access attempted')
    monkeypatch.setattr(socket,'socket',blocked)
    monkeypatch.setattr(socket,'getaddrinfo',blocked)
    assert len(countries())>150
    svg=svg_map(stations=[(-86.59,34.73)])
    assert svg.startswith('<svg') and '<polygon' in svg and '<circle' in svg
