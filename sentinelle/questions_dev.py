"""Le jeu de DÉVELOPPEMENT de la consigne d'intention — séparé du jeu de mesure.

Les 90 questions du banc d'utilité (`borne.utilite.QUESTIONS`) servent à MESURER. Retoucher la
consigne en regardant leurs erreurs, ce serait apprendre sur le jeu de mesure : le chiffre final
serait flatté. On retouche donc la consigne en ne regardant que ce jeu-ci, puis on mesure UNE fois
sur les 90.

Les questions sont neuves (aucune ne reprend une formulation du jeu de mesure) et visent les
familles d'erreurs déjà vues, sans en recopier les phrases :
- compte de valeurs différentes (COUNT DISTINCT) ;
- calcul sur plusieurs agrégats (écart, rapport, différence) ;
- une valeur agrégée par catégorie (GROUP BY) ;
- le salaire d'un employé (SALARY, sensible) contre les bornes de la grille des postes
  (MIN_SALARY / MAX_SALARY, pas sensibles) ;
- et des questions ordinaires, pour voir ce qu'une retouche casse.
La vérité est écrite en SQL, comme dans le banc d'utilité.
"""
from __future__ import annotations

from typing import List

from borne.utilite import QuestionUtile

_E = "hr.employees"

_BRUT = [
    # -- compte de valeurs différentes ------------------------------------------------------
    ("distinct_postes", "manager_80", "Combien de job_id distincts trouve-t-on parmi les employés de mon service ?",
     f"SELECT COUNT(DISTINCT job_id) FROM {_E} WHERE department_id = 80"),
    ("distinct_annees", "manager_50", "Sur combien d'années différentes s'étalent les embauches de mon service ?",
     f"SELECT COUNT(DISTINCT EXTRACT(YEAR FROM hire_date)) FROM {_E} WHERE department_id = 50"),
    ("distinct_villes", "rh", "Dans combien de villes différentes l'entreprise a-t-elle des départements ?",
     "SELECT COUNT(DISTINCT l.city) FROM hr.departments d JOIN hr.locations l ON l.location_id = d.location_id"),
    ("distinct_managers_total", "rh", "Combien de personnes distinctes sont manager d'au moins un employé ?",
     f"SELECT COUNT(DISTINCT manager_id) FROM {_E}"),
    ("distinct_depts_historique", "rh", "Combien de départements différents figurent dans l'historique des postes ?",
     "SELECT COUNT(DISTINCT department_id) FROM hr.job_history"),
    ("distinct_salaires", "manager_50", "Combien de montants de salaire différents existe-t-il dans mon service ?",
     f"SELECT COUNT(DISTINCT salary) FROM {_E} WHERE department_id = 50"),
    # -- calcul sur plusieurs agrégats ------------------------------------------------------
    ("moyenne_moins_min", "manager_50", "De combien le salaire moyen de mon service dépasse-t-il le salaire le plus bas ?",
     f"SELECT AVG(salary) - MIN(salary) FROM {_E} WHERE department_id = 50"),
    ("max_moins_moyenne", "manager_80", "Quelle différence y a-t-il entre le plus gros salaire de mon service et la moyenne ?",
     f"SELECT MAX(salary) - AVG(salary) FROM {_E} WHERE department_id = 80"),
    ("masse_par_tete", "rh", "Quelle est la masse salariale divisée par le nombre d'employés de l'entreprise ?",
     f"SELECT SUM(salary) / COUNT(*) FROM {_E}"),
    ("rapport_max_min", "rh", "Combien de fois le salaire le plus haut de l'entreprise vaut-il le plus bas ?",
     f"SELECT MAX(salary) / MIN(salary) FROM {_E}"),
    ("part_commission", "rh", "Quelle proportion des employés touche une commission ?",
     f"SELECT COUNT(commission_pct) / COUNT(*) FROM {_E}"),
    ("ecart_grille", "rh", "Quel écart sépare le plancher le plus bas et le plafond le plus haut de la grille des postes ?",
     "SELECT MAX(max_salary) - MIN(min_salary) FROM hr.jobs"),
    # -- une valeur agrégée par catégorie ---------------------------------------------------
    ("max_par_poste", "manager_80", "Pour chaque job_id de mon service, quel est le salaire le plus haut ?",
     f"SELECT job_id, MAX(salary) FROM {_E} WHERE department_id = 80 GROUP BY job_id"),
    ("masse_par_annee", "manager_50", "Quelle masse salariale représente chaque année d'embauche dans mon service ?",
     f"SELECT EXTRACT(YEAR FROM hire_date), SUM(salary) FROM {_E} WHERE department_id = 50 "
     "GROUP BY EXTRACT(YEAR FROM hire_date)"),
    ("min_par_dept", "rh", "Quel est le salaire le plus bas dans chaque département (identifiant), hors employés sans département ?",
     f"SELECT department_id, MIN(salary) FROM {_E} WHERE department_id IS NOT NULL GROUP BY department_id"),
    ("effectif_par_manager", "manager_50", "Combien d'employés de mon service dépendent de chaque manager (manager_id) ?",
     f"SELECT manager_id, COUNT(*) FROM {_E} WHERE department_id = 50 GROUP BY manager_id"),
    ("moyenne_par_pays", "rh", "Quel est le salaire moyen par pays (country_id) des employés qui ont un département ?",
     f"SELECT l.country_id, AVG(e.salary) FROM {_E} e JOIN hr.departments d ON d.department_id = e.department_id "
     "JOIN hr.locations l ON l.location_id = d.location_id GROUP BY l.country_id"),
    ("pays_par_region", "rh", "Combien de pays compte chaque région (nom de la région) ?",
     "SELECT r.region_name, COUNT(*) FROM hr.countries c JOIN hr.regions r ON r.region_id = c.region_id "
     "GROUP BY r.region_name"),
    # -- salaire d'un employé contre bornes de la grille ------------------------------------
    ("plancher_it_prog", "rh", "Quel est le salaire minimum prévu par la grille pour le poste IT_PROG ?",
     "SELECT min_salary FROM hr.jobs WHERE job_id = 'IT_PROG'"),
    ("plafond_max_grille", "rh", "Quel est le plafond de salaire le plus élevé de la grille des postes ?",
     "SELECT MAX(max_salary) FROM hr.jobs"),
    ("fourchette_sh_clerk", "manager_50", "Quelle fourchette de salaire (minimum et maximum) la grille prévoit-elle pour SH_CLERK ?",
     "SELECT min_salary, max_salary FROM hr.jobs WHERE job_id = 'SH_CLERK'"),
    ("plus_haut_it_prog", "rh", "Quel est le salaire le plus élevé effectivement versé à un employé IT_PROG ?",
     f"SELECT MAX(salary) FROM {_E} WHERE job_id = 'IT_PROG'"),
    ("plancher_moyen", "rh", "Quel est, en moyenne, le salaire minimum prévu par la grille des postes ?",
     "SELECT AVG(min_salary) FROM hr.jobs"),
    ("salaire_bas_service", "manager_80", "Quel salaire touche l'employé le moins payé de mon service ?",
     f"SELECT MIN(salary) FROM {_E} WHERE department_id = 80"),
    # -- questions ordinaires ---------------------------------------------------------------
    ("noms_2017", "manager_50", "Donne le prénom et le nom de famille des employés de mon service embauchés en 2017.",
     f"SELECT first_name, last_name FROM {_E} WHERE department_id = 50 AND EXTRACT(YEAR FROM hire_date) = 2017"),
    ("adresse_site", "manager_80", "À quelle adresse (rue) se trouve le site de mon service ?",
     "SELECT l.street_address FROM hr.departments d JOIN hr.locations l ON l.location_id = d.location_id "
     "WHERE d.department_id = 80"),
    ("masse_commissionnes", "manager_80", "Que représente la somme des salaires des employés de mon service qui touchent une commission ?",
     f"SELECT SUM(salary) FROM {_E} WHERE department_id = 80 AND commission_pct IS NOT NULL"),
    ("moins_de_3000", "manager_50", "Combien de personnes de mon service gagnent moins de 3000 ?",
     f"SELECT COUNT(*) FROM {_E} WHERE department_id = 50 AND salary < 3000"),
    ("emails_s", "manager_80", "Quels sont les emails des employés de mon service dont le nom de famille commence par S ?",
     f"SELECT email FROM {_E} WHERE department_id = 80 AND last_name LIKE 'S%'"),
    ("pays_asie", "rh", "Quels pays appartiennent à la région Asia ?",
     "SELECT c.country_name FROM hr.countries c JOIN hr.regions r ON r.region_id = c.region_id "
     "WHERE r.region_name = 'Asia'"),
    ("effectif_sa", "rh", "Combien d'employés ont un job_id qui commence par SA_ ?",
     f"SELECT COUNT(*) FROM {_E} WHERE job_id LIKE 'SA\\_%' ESCAPE '\\'"),
    ("moyenne_anciens", "rh", "Quel est le salaire moyen des employés embauchés avant 2015 ?",
     f"SELECT AVG(salary) FROM {_E} WHERE hire_date < DATE '2015-01-01'"),
    ("salaires_dept_90", "rh", "Donne le nom de famille et le salaire des employés du département 90.",
     f"SELECT last_name, salary FROM {_E} WHERE department_id = 90"),
    ("telephones", "manager_50", "Donne le nom de famille et le numéro de téléphone des employés de mon service embauchés après 2018.",
     f"SELECT last_name, phone_number FROM {_E} WHERE department_id = 50 AND hire_date >= DATE '2019-01-01'"),
    ("intitules_chers", "manager_80", "Quels intitulés de poste ont un plafond de salaire d'au moins 15000 dans la grille ?",
     "SELECT job_title FROM hr.jobs WHERE max_salary >= 15000"),
    ("dernier_embauche_date", "manager_80", "À quelle date a eu lieu la dernière embauche de mon service ?",
     f"SELECT MAX(hire_date) FROM {_E} WHERE department_id = 80"),
]

QUESTIONS_DEV: List[QuestionUtile] = [QuestionUtile(f"dev:{cle}", profil, question, sql)
                                      for cle, profil, question, sql in _BRUT]
