import requests
import os
from requests.auth import HTTPBasicAuth
import pprint
from rich import print
import json
import re

API_KEY = os.getenv("JIRA_API_KEY", "NULL")
API_EMAIL = os.getenv("JIRA_EMAIL", None)
BASE_URL = os.getenv("JIRA_BASE_URL", "https://ncinodev.atlassian.net/")
AUTH = HTTPBasicAuth(API_EMAIL, API_KEY)
pretty_printer = pprint.PrettyPrinter(indent=4)
DEFAULT_HEADERS = {"Accept": "application/json"}

# REGEX
COLOR_REGEX = re.compile(r"{color(:#[a-fA-F0-9]{3,6})?}")


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
        self.product_copy = self.sanitize_copy(ticket_fields["customfield_13332"])
        self.url = f'{BASE_URL}browse/{rest_api_response["key"]}'
        self.status = ticket_fields["status"]["name"]

    def get_ticket_details(self):
        truncated_name = self.name if len(self.name) < 128 else f"{self.name[:128]}..."
        ticket_info = [
            f":ticket: [bold green]{self.number.upper()}: {truncated_name}[/bold green]",
            f":link: {self.url}",
        ]

        return "\n".join(ticket_info)

    def sanitize_copy(self, content: str) -> list[str]:
        if content is None:
            return []
        split_labels = [part for part in content.split("\n") if part != ""]
        sanitized_labels = []
        for label in split_labels:
            sanitized_label = re.sub(COLOR_REGEX, "", label)
            sanitized_labels.append(sanitized_label)

        return sanitized_labels

    def __str__(self):
        return f"{self.number.upper()}: {self.name}"


def credentialsAreInvalid() -> bool:
    return API_KEY in ["NULL", "", " "] or API_EMAIL is None


def getCurrentUserInfo():
    user_url = f"{BASE_URL}rest/api/3/myself"
    user_info = makeJiraRequest(url=user_url)
    return user_info.json()


def getCurrentlyAssignedTickets() -> list[JiraTicket]:
    user_info = getCurrentUserInfo()
    account_id = user_info["accountId"]
    assignee_filter_jql = f"assignee%20IN%20({account_id})"
    status_filter_jql = (
        f'status%20in%20("In%20Development",%20"In%20Review",%20Ready,%20"To%20Do")'
    )
    issues_by_assignee_url = f"{BASE_URL}rest/api/2/search?jql={assignee_filter_jql}%20and%20{status_filter_jql}"
    response = makeJiraRequest(issues_by_assignee_url)
    if response.status_code != 200:
        print(response.json())

    else:
        issues = response.json()["issues"]
        return [JiraTicket(raw_ticket) for raw_ticket in issues]


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


def getBoardInfo(boardId):
    url = f"{BASE_URL}/rest/agile/1.0/board/{boardId}"
    response = makeJiraRequest(url)

    return response


def getCurrentSprintInfo(boardId):
    url = f"{BASE_URL}/rest/agile/1.0/board/{boardId}/sprint"
    params = {"startAt": "50"}
    response = makeJiraRequest(url, params)

    return response
