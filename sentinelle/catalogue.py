"""Le catalogue des colonnes que le modèle d'intention a le droit de nommer.

Schéma HR d'exemple d'Oracle (celui des campagnes). Le modèle choisit dans cette liste ;
une colonne qu'il invente est retirée, jamais devinée.
"""
from typing import Dict, List

CATALOGUE_HR: Dict[str, List[str]] = {
    "EMPLOYEES": ["EMPLOYEE_ID", "FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE_NUMBER", "HIRE_DATE",
                  "JOB_ID", "SALARY", "COMMISSION_PCT", "MANAGER_ID", "DEPARTMENT_ID"],
    "DEPARTMENTS": ["DEPARTMENT_ID", "DEPARTMENT_NAME", "MANAGER_ID", "LOCATION_ID"],
    "JOBS": ["JOB_ID", "JOB_TITLE", "MIN_SALARY", "MAX_SALARY"],
    "JOB_HISTORY": ["EMPLOYEE_ID", "START_DATE", "END_DATE", "JOB_ID", "DEPARTMENT_ID"],
    "LOCATIONS": ["LOCATION_ID", "STREET_ADDRESS", "POSTAL_CODE", "CITY", "STATE_PROVINCE", "COUNTRY_ID"],
    "COUNTRIES": ["COUNTRY_ID", "COUNTRY_NAME", "REGION_ID"],
    "REGIONS": ["REGION_ID", "REGION_NAME"],
}
