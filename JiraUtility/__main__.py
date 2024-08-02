import os
import subprocess
import logging
import argparse
from argparse import Namespace
import sys
from rich import print
import webbrowser
import json
import pathlib

from JiraConnector import (
    getTicket,
    getCurrentlyAssignedTickets,
    credentialsAreInvalid,
    JiraTicket,
    UnauthorizedActionException,
    ForbiddenActionException,
    TicketNotFoundException,
    getCurrentSprintInfo,
    getBoardInfo,
)
from LabelMaker import find_labels_in_section, Label, NoLabelsFoundError


def _configure_logging(level: int = logging.ERROR):
    log_file_directory = os.path.join(
        os.path.expanduser("~"), "Library/Logs/JiraUtility"
    )
    log_file_path = os.path.join(log_file_directory, "util.log")

    if os.path.exists(log_file_directory) is not True:
        os.makedirs(log_file_directory)

    logging.basicConfig(filename=log_file_path, encoding="utf-8", level=level)


def getTicketNumber() -> str:
    waiting_for_valid_ticket = True
    ticket_number = input("👋 What ticket would you like to work with? [PROD-1234]: ")
    attempts = 0

    while waiting_for_valid_ticket:
        attempts += 1
        if attempts == 5:
            print("\n🫣 My dude, let me help you out")
            print(
                "https://www.youtube.com/watch?v=vXsutlz0GIQ&pp=ygULSG93IHRvIHR5cGU%3D"
            )
            sys.exit(1)
        ticket_parts = ticket_number.split("-")

        if (
            len(ticket_parts) == 2
            and ticket_parts[0].isalpha()
            and ticket_parts[1].isnumeric()
        ):
            return ticket_number
        else:
            print(
                "\n⚠️ Oh No! That ticket doesn't seem to follow the standard format of {PROJECT}-{NUMBER}!"
            )
            ticket_number = input(
                "🤔 What ticket would you like to work with? [PROD-1234]: "
            )


def getBoardId():
    board_id = input("👋 What board would you like to work with? [1234]: ")
    return board_id


def getJiraTicket(ticket_number: str) -> JiraTicket:
    return getTicket(ticket_number=ticket_number)


def generateLabelsFromTicket(ticket: JiraTicket) -> list[Label]:
    logging.debug(ticket.product_copy)
    return find_labels_in_section(ticket.product_copy)


def handleLabelCreation(args: Namespace):
    ticket_number = args.ticket if args.ticket is not None else getTicketNumber()
    format = args.format if args.format is not None else "xml"
    copy_to_clipboard = args.copy_to_clipboard

    ticket = None
    labels = None
    label_str = None

    try:
        ticket = getJiraTicket(ticket_number)
    except TicketNotFoundException:
        error_message = (
            f"❌ Unable to find a ticket with the following identifier: {ticket_number}"
        )
        print(error_message)
        logging.error(error_message)
        sys.exit(1)
    except UnauthorizedActionException:
        error_message = "❌ Unable to authenticate with your provided credentials. Please check them again"
        print(error_message)
        logging.error(error_message)
        sys.exit(1)
    except ForbiddenActionException:
        error_message = "❌ These credentials don't seem to have permission to perform this action. Please check them again."
        print(error_message)
        logging.error(error_message)
        sys.exit(1)

    try:
        labels = generateLabelsFromTicket(ticket)
    except NoLabelsFoundError:
        print("🤔 Hmmmm, we weren't able to find any labels attached to that ticket.")
        print(
            "\tMake sure the labels are following the product copy section and in the correct format."
        )
        sys.exit(1)

    if format.lower() == "xml":
        label_str = "".join([label.get_label_as_xml() for label in labels])

    if copy_to_clipboard:
        subprocess.run("pbcopy", text=True, input=label_str)
    else:
        print(label_str)

    print(f"🎊 {len(labels)} labels generated!")


def iterate_over_tickets(tickets: list[JiraTicket]):
    for ticket in tickets:
        webbrowser.open_new_tab(ticket.url)
        print(ticket.get_ticket_details())
        early_exit = input("Next Ticket? [Q to quit]: ")
        if early_exit.lower() == "q":
            sys.exit(0)


def getSprintInfo(boardId):
    boardResponse = getBoardInfo(boardId)
    print(boardResponse.json())
    response = getCurrentSprintInfo(boardId)
    print(response.status_code)
    results = response.json()
    path = pathlib.Path(__file__).parent.resolve()
    with open(f"{path}/data/current-sprints.json", "w") as ofile:
        json.dump(results, ofile)


def verifyEnvironment():
    if credentialsAreInvalid():
        print("🛑 Oh No! It looks like there are no Jira Credentials available! ❌")
        print("This utility expects that the following environment variables are set:")
        print("\tJIRA_API_KEY -> Set to an API key for your account")
        print("\tJIRA_EMAIL -> Set to your corporate email address")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="JiraUtility",
        description="A helper utility for accomplishing monotonous tasks in Jira",
        epilog="For support, reach out to Seth Angell (@seth on slack)",
    )
    subparsers = parser.add_subparsers(help="sub-command help")
    create_labels_parser = subparsers.add_parser(
        "create-labels",
        help="Generate salesforce labels from a tickets Product Copy section",
    )
    create_labels_parser.set_defaults(which="create-labels")
    create_labels_parser.add_argument(
        "--ticket", type=str, help="Ticket number to generate from"
    )
    create_labels_parser.add_argument(
        "--format",
        type=str,
        choices=["XML"],
        default="XML",
        help="The format to generate your labels in",
    )
    create_labels_parser.add_argument(
        "--copy-to-clipboard",
        action="store_true",
        help="Whether or not to copy the generated labels to your clipboard. When provided, labels are NOT printed to stdout.",
    )

    current_tickets_parser = subparsers.add_parser(
        "current-tickets",
        help="Get all tickets assigned to the current user",
    )
    current_tickets_parser.set_defaults(which="current-tickets")
    current_tickets_parser.add_argument(
        "--iterate",
        action="store_true",
        help="Whether or not to iterate over each ticket assigned to the current user.",
    )
    sprints_parser = subparsers.add_parser(
        "current-sprint", help="Get all current sprints"
    )
    sprints_parser.set_defaults(which="current-sprint")

    _configure_logging()

    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    if args.which == "create-labels":
        verifyEnvironment()
        handleLabelCreation(args)
    elif args.which == "current-tickets":
        verifyEnvironment()
        tickets = getCurrentlyAssignedTickets()
        if args.iterate:
            iterate_over_tickets(tickets)
        else:
            for ticket in tickets:
                print(ticket.get_ticket_details())
    elif args.which == "current-sprint":
        verifyEnvironment()
        boardId = getBoardId()
        getSprintInfo(boardId)
