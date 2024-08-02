import re
from re import Match, Pattern
import logging
from lxml import etree

NAME_REGEX = re.compile(r"\*?[nN]ame\*?:? ?(\xa0)?(?P<name>.*)")
CATEGORY_REGEX = re.compile(r"\*?[cC]ategory\*?:? ?(\xa0)?(?P<category>.*)$")
DESCRIPTION_REGEX = re.compile(
    r"^[\s*]*[Ss]hort\s[Dd]escription[\s*]{0,4}(\(80 char limit\)\*?)?:?\s?(?P<description>.*)$"
)
VALUE_REGEX = re.compile(r"\*?[Vv]alue ?\*?:? ?(\xa0)?(?P<value>.*)$")
TEMPLATE = (
    "<labels>"
    "<-><fullName>{0}</fullName>"
    "<-><categories>{1}</categories>"
    "<-><language>en_US</language>"
    "<-><protected>true</protected>"
    "<-><shortDescription>{2}</shortDescription>"
    "<-><value>{3}</value>"
    "<-></labels>"
)


class NoLabelsFoundError(Exception):
    pass


class Label(object):
    def __init__(self):
        self.name = ""
        self.category = ""
        self.description = ""
        self.value = ""
        self.valid = False

    def set_name(self, new_name):
        name_parts = [
            f"{part[0].upper()}{part[:-1]}"
            for part in new_name.split(" ")
            if part != ""
        ]

        self.name = "_".join(name_parts)

    def get_pattern_for_next_needed_attribute(self) -> Pattern | str:
        if self.name == "":
            return NAME_REGEX
        elif self.category == "":
            return CATEGORY_REGEX
        elif self.description == "":
            return DESCRIPTION_REGEX
        elif self.value == "":
            return VALUE_REGEX
        else:
            return "VALID"

    def extract_value_from_response(self, match: Match):
        if match is None:
            return
        if self.name == "":
            self.name = match.group("name")
        elif self.category == "":
            self.category = match.group("category")
        elif self.description == "":
            self.description = match.group("description")
        elif self.value == "":
            self.value = match.group("value")

    def get_label_as_xml(self) -> str:
        raw_str = TEMPLATE.format(
            self.name, self.category, self.description, self.value
        )
        parts = raw_str.split("<->")
        interior_parts = [f"\t{part}\n" for part in parts[1:-1]]
        new_str = f'{parts[0]}\n{''.join(interior_parts)}{parts[-1]}\n'
        return new_str

    def __str__(self):
        return f"{self.name} - {self.category}"

    def __repr__(self):
        return self.__str__()


def find_labels_in_section(split_labels: str) -> list[Label]:
    current_label = Label()
    valid_labels = []

    for line in split_labels:
        logging.debug(line)
        pattern = current_label.get_pattern_for_next_needed_attribute()
        logging.debug(f"{pattern}")

        if pattern == "VALID":
            logging.info("Valid")
            valid_labels.append(current_label)
            current_label = Label()
            current_label.extract_value_from_response(NAME_REGEX.search(line))
        else:
            logging.debug(current_label)
            current_label.extract_value_from_response(pattern.search(line))

    if current_label.get_pattern_for_next_needed_attribute() == "VALID":
        valid_labels.append(current_label)

    if len(valid_labels) == 0:
        raise NoLabelsFoundError

    return valid_labels
