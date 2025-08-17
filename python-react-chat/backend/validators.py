from abc import ABC, abstractmethod
import sqlparse
# Import Parenthesis directly, and tokens as T
from sqlparse.sql import Parenthesis
from sqlparse import tokens as T

class ValidationRule(ABC):
    """Abstract base class for a validation rule."""
    @abstractmethod
    def validate(self, sql_query: str, db_response=None) -> tuple[bool, str]:
        """
        Validates the SQL query or DB response against the rule.
        Returns (is_valid, message).
        """
        pass

class ForbiddenKeywordsRule(ValidationRule):
    FORBIDDEN_KEYWORDS = ["insert ", "update ", "delete ", "drop ", "alter ", "truncate ", "create ", "exec ", "xp_"]

    def validate(self, sql_query: str, db_response=None) -> tuple[bool, str]:
        lower_query = sql_query.strip().lower()
        if any(keyword in lower_query for keyword in self.FORBIDDEN_KEYWORDS):
            return False, "Forbidden SQL keywords detected. Only SELECT queries are allowed."
        return True, ""

class OnlySelectStatementsRule(ValidationRule):
    def validate(self, sql_query: str, db_response=None) -> tuple[bool, str]:
        try:
            parsed_statements = sqlparse.parse(sql_query)
            if not parsed_statements:
                return False, "No valid SQL statements found."

            for statement in parsed_statements:
                # This is the line that should now work with sqlparse 0.5.3
                first_token = statement.token_first(skip_ws=True)

                if first_token is None:
                    return False, "Invalid SQL statement structure: Cannot determine statement type."

                statement_type = first_token.normalized
                if statement_type != "SELECT":
                    return False, f"Forbidden statement type '{statement_type}' detected. Only SELECT queries are allowed."
            return True, ""
        except Exception as e:
            return False, f"SQL parsing error during statement type check: {e}"

class WhitelistedTablesRule(ValidationRule):
    def __init__(self, allowed_tables: list):
        self.allowed_tables = [t.lower() for t in allowed_tables]

    def validate(self, sql_query: str, db_response=None) -> tuple[bool, str]:
        try:
            parsed_statements = sqlparse.parse(sql_query)
            if not parsed_statements:
                return False, "No valid SQL statements found for table check."

            statement = parsed_statements[0]
            flattened_tokens = list(statement.flatten())

            for i, token in enumerate(flattened_tokens):
                if token.is_keyword and token.normalized in ('FROM', 'JOIN'):
                    current_idx = i + 1
                    table_name_candidate_token = None
                    while current_idx < len(flattened_tokens):
                        next_token = flattened_tokens[current_idx]
                        if not next_token.is_whitespace:
                            table_name_candidate_token = next_token
                            break
                        current_idx += 1

                    if table_name_candidate_token is None:
                        return False, "Could not identify table name after FROM/JOIN clause."

                    # Now, use Parenthesis directly
                    if isinstance(table_name_candidate_token, Parenthesis):
                        continue

                    table_name = table_name_candidate_token.normalized.strip('"').strip("'").strip("`").lower()

                    if table_name not in self.allowed_tables:
                        return False, f"Access to table/object '{table_name}' is not allowed."

        except Exception as e:
            return False, f"SQL parsing error during table whitelist check: {e}"

        return True, ""

class RuleExecutor:
    def __init__(self, rules: list[ValidationRule]):
        self.rules = rules

    def execute_rules(self, sql_query: str, db_response=None) -> tuple[bool, str]:
        for rule in self.rules:
            is_valid, message = rule.validate(sql_query, db_response)
            if not is_valid:
                return False, message # Fail fast on the first rule violation
        return True, "All rules passed."