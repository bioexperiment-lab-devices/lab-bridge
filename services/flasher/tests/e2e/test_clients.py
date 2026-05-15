def test_clients_lists_online_clients(http) -> None:
    """GET /flash/api/clients probes each rostered client via probe_tcp.
    With stub-serialhop running on its port-9000 alias, the probe to
    chisel_host=stub-serialhop:9000 succeeds → client appears online.
    """
    r = http.get("/flash/api/clients")
    assert r.status_code == 200
    body = r.json()
    names = [c["name"] for c in body["clients"]]
    assert "alice_machine" in names


def test_ports_returns_stub_ports(http) -> None:
    r = http.get("/flash/api/clients/alice_machine/ports")
    assert r.status_code == 200
    body = r.json()
    assert "ports" in body
    assert body["ports"][0]["name"] == "COM3"
    assert body["ports"][0]["product"] == "Arduino Uno (stub)"


def test_unknown_client_returns_404(http) -> None:
    r = http.get("/flash/api/clients/nobody/ports")
    assert r.status_code == 404
