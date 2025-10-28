import requests
import pandas as pd


def fetch_employee_roster():
    roster_url = 'https://datagate.dc.gov/ess/v1.0/employees'
    response = requests.get(
        roster_url,
        headers={"Origin": "https://dchr.dc.gov"}
    )
    response.raise_for_status()
    return response.json()


if __name__ == '__main__':
    employee_roster = fetch_employee_roster()
    assert employee_roster['success']
    out = pd.DataFrame(employee_roster['data'])
    out.to_csv('output/dc-employee-roster-raw.csv', index=False)
