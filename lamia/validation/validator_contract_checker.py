class ValidatorContractChecker:
    def __init__(self, validator_class: Type[BaseValidator]):
        self.validator_class = validator_class

    def check(self):
        pass