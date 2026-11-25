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


def test_le_cache_d_une_consigne_v2_est_un_autre_fichier():
    from sentinelle.campagne import chemin_cache
    assert chemin_cache("openai/gpt-oss-20b").name == "intentions-openai_gpt-oss-20b.jsonl"
    assert chemin_cache("openai/gpt-oss-20b@v2").name == "intentions-openai_gpt-oss-20b-v2.jsonl"


def test_le_cache_passe_la_consigne_au_modele(tmp_path):
    class _Lit:
        def completer(self, messages):
            self.consigne = messages[0]["content"]
            return '{"colonnes": [], "forme": "compte", "perimetre": "mon_service"}'
    m = _Lit()
    Cache(tmp_path / "i.jsonl", m, consigne="v2").intention("rh", "rh", "Combien ?")
    from sentinelle.intention import CONSIGNES
    assert m.consigne.startswith(CONSIGNES["v2"][:40])
