class InvoiceNotFoundError(Exception):
    """Raised when an invoice is not found."""
    pass

class InsufficientWalletBalanceError(Exception):
    """Raised when the wallet balance is less than the requested deduction."""
    pass
