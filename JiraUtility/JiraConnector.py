import requests
import os
from requests.auth import HTTPBasicAuth
import pprint
from rich import print
import json

API_KEY = os.getenv("JIRA_API_KEY", "NULL")
API_EMAIL = os.getenv("JIRA_EMAIL", None)
BASE_URL = os.getenv("JIRA_BASE_URL", "https://ncinodev.atlassian.net/")
AUTH = HTTPBasicAuth(API_EMAIL, API_KEY)
pretty_printer = pprint.PrettyPrinter(indent=4)
DEFAULT_HEADERS = {"Accept": "application/json"}


class TicketNotFoundException(Exception):
    pass


class UnauthorizedActionException(Exception):
    pass


class ForbiddenActionException(Exception):
    pass


class JiraTicket(object):
    def __init__(self, rest_api_response: dict):
        ticket_fields = rest_api_response["fields"]
        self.number = rest_api_response["key"]
        self.id = rest_api_response["id"]
        self.component = ",".join(
            [component["name"] for component in ticket_fields["components"]]
        )
        self.name = ticket_fields["summary"]
        self.product_copy = ticket_fields["customfield_13332"]
        self.url = f'{BASE_URL}{rest_api_response['key']}'
        self.status = ticket_fields["status"]["name"]

    def display_ticket_details(self):
        truncated_name = self.name if len(self.name) < 128 else f"{self.name[:128]}..."
        ticket_info = [
            f":ticket: [bold green]{self.number.upper()}: {truncated_name}[/bold green]"
        ]

        print("\n".join(ticket_info))

    def __str__(self):
        return f"{self.number.upper()}: {self.name}"


def credentialsAreInvalid() -> bool:
    return API_KEY in ["NULL", "", " "] or API_EMAIL is None


def getCurrentUserInfo():
    user_url = f"{BASE_URL}rest/api/3/myself"
    user_info = makeJiraRequest(url=user_url)
    return user_info.json()


def getCurrentlyAssignedTickets():
    user_info = getCurrentUserInfo()
    account_id = user_info["accountId"]
    assignee_filter_jql = f"assignee%20IN%20({account_id})"
    issues_by_assignee_url = f"{BASE_URL}rest/api/3/search?jql={assignee_filter_jql}"
    response = makeJiraRequest(issues_by_assignee_url)
    if response.status_code != 200:
        print(response.json())

    else:
        issues = response.json()["issues"]
        pretty_printer.pprint(issues[0])
        tickets = [JiraTicket(raw_ticket) for raw_ticket in issues]
        for ticket in tickets:
            ticket.display_ticket_details()


def makeJiraRequest(
    url: str,
    parameters: dict = {},
    verb: str = "GET",
    auth: HTTPBasicAuth = AUTH,
    headers: dict = DEFAULT_HEADERS,
):
    response = requests.request(
        verb, url, headers=headers, params=parameters, auth=auth
    )

    return response


def getTicket(
    ticket_number: str, fields_to_expand: list[str] = ["renderedFields"]
) -> JiraTicket:
    url = f"{BASE_URL}rest/api/latest/issue/{ticket_number}"
    if len(fields_to_expand) > 0:
        fields = ",".join(fields_to_expand)
        url = f"{url}?expand={fields}"
    response = requests.get(url, auth=AUTH)

    if response.status_code == 404:
        raise TicketNotFoundException
    elif response.status_code == 403:
        raise ForbiddenActionException
    elif response.status_code == 401:
        raise UnauthorizedActionException

    return JiraTicket(response.json())
