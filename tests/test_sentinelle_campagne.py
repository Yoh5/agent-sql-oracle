from sentinelle.campagne import Cache


class _Compteur:
    def __init__(self):
        self.appels = 0

    def completer(self, messages):
        self.appels += 1
        return '{"colonnes": [], "forme": "compte", "perimetre": "mon_service"}'


def test_le_cache_evite_le_second_appel(tmp_path):
    m = _Compteur()
    c = Cache(tmp_path / "i.jsonl", m)
    a = c.intention("manager_50", "manager du service 50", "Combien ?")
    b = Cache(tmp_path / "i.jsonl", m).intention("manager_50", "manager du service 50", "Combien ?")
    assert a == b and a.forme == "compte" and m.appels == 1


def test_une_intention_illisible_est_gardee_illisible(tmp_path):
    class _Bavard:
        appels = 0

        def completer(self, messages):
            _Bavard.appels += 1
            return "je ne sais pas"
    c = Cache(tmp_path / "i.jsonl", _Bavard())
    assert c.intention("rh", "rh", "?") is None
    assert Cache(tmp_path / "i.jsonl", _Bavard()).intention("rh", "rh", "?") is None and _Bavard.appels == 1
