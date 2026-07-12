class XMLTVMerger:

    def __init__(self):
        self.programme = {}

    def add(self, programme):

        key = (
            programme.get("channel"),
            programme.get("start")
        )

        if key not in self.programme:
            self.programme[key] = programme

    def get_programmes(self):

        return list(self.programme.values())