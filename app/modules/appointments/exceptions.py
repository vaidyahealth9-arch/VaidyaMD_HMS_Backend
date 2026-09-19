class AppointmentNotFoundError(Exception):
    """Raised when an appointment is not found."""
    pass

class InvalidAppointmentDateError(Exception):
    """Raised when an appointment is scheduled in the past or invalid."""
    pass

class ActiveAppointmentExistsError(Exception):
    """Raised when a patient already has an active appointment today."""
    pass
