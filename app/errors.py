class InputError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
