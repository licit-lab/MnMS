class DemandManager(object):
    def __init__(self):
        self.users = []

    def register_user(self, user):
        self.users.append(user)

    @classmethod
    def fromCSV(cls):
        pass