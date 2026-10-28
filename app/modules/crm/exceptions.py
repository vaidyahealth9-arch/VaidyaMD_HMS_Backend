"""
VaidyaMD HMS — CRM Custom Exceptions
Adheres to Clean Architecture error handling specifications.
"""

from fastapi import HTTPException, status


class LeadNotFoundException(HTTPException):
    def __init__(self, detail: str = "Lead not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class CallLogNotFoundException(HTTPException):
    def __init__(self, detail: str = "Call record not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class LeadAlreadyConvertedException(HTTPException):
    def __init__(self, detail: str = "Lead is already marked as converted"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidFileFormatException(HTTPException):
    def __init__(self, detail: str = "Unsupported audio or CSV file format"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class TelecallerSessionNotFoundException(HTTPException):
    def __init__(self, detail: str = "Telecaller session not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
