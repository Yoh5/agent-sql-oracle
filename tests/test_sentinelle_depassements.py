from borne.utilite import QUESTIONS
from sentinelle.comparateur import comparer
from sentinelle.depassements import generer
from sentinelle.empreinte import empreinte

S = {"SALARY"}
D = {d.id: d for d in generer(QUESTIONS, S)}


def test_effectif_devient_liste_dans_le_meme_service():
    d = D["manager_50:effectif:retirer_agregat"]
    e = empreinte(d.sql, S)
    assert e.forme == "liste" and "department_id = 50" in d.sql.lower().replace("  ", " ")


def test_ajouter_sensible():
    assert "SALARY" in empreinte(D["manager_50:embauches_2016:ajouter_sensible"].sql, S).sensibles
    assert "manager_50:effectif:ajouter_sensible" not in D   # agrégat : mutation impossible


def test_pas_de_sensible_ajoutee_si_deja_la():
    assert "rh:top5_salaires:ajouter_sensible" not in D


def test_chaque_depassement_est_detecte_par_au_moins_une_raison():
    vrai = {q.id: q for q in QUESTIONS}
    for d in D.values():
        v = comparer(empreinte(vrai[d.question_id].sql_verite, S), empreinte(d.sql, S))
        assert v.score > 0, d.id
