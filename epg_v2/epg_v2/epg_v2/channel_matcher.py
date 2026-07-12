class ChannelMatcher:

    def __init__(self):
        self.mapping = {}

    def add(self, xmltv_name, eigener_name):
        self.mapping[xmltv_name.lower()] = eigener_name

    def match(self, sender):

        name = sender.lower().strip()

        if name in self.mapping:
            return self.mapping[name]

        return sender